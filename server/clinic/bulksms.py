import base64
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone

from .models import AuditEvent, CommunicationConsent, MessageOutbox


class ProviderNotConfigured(Exception):
    pass


class MessageNotSendable(Exception):
    pass


def _destination(phone):
    digits = re.sub(r"\D", "", phone or "")
    if len(digits) == 10:
        digits = "91" + digits
    if len(digits) == 12 and digits.startswith("91"):
        return "+" + digits
    raise MessageNotSendable("Patient phone must be a valid Indian mobile number.")


def _message_text(outbox):
    if outbox.purpose == CommunicationConsent.Purpose.THANK_YOU:
        return "Thank you for visiting us. We wish you well."
    if outbox.purpose == CommunicationConsent.Purpose.REPORT_READY:
        return "Your report is ready. Please contact the hospital."
    raise MessageNotSendable("This message purpose is not supported.")


def _set_state(message_id, status, *, error="", provider_id=""):
    MessageOutbox.objects.filter(pk=message_id, status=MessageOutbox.Status.SENDING).update(
        status=status, last_error=error[:300], provider_message_id=provider_id[:120]
    )


def send_outbox_message(message_id, actor):
    token_id = os.environ.get("BULKSMS_TOKEN_ID", "").strip()
    token_secret = os.environ.get("BULKSMS_TOKEN_SECRET", "").strip()
    if not token_id or not token_secret:
        raise ProviderNotConfigured("BulkSMS credentials are not configured in the server environment.")

    with transaction.atomic():
        message = MessageOutbox.objects.select_for_update().select_related("patient").get(pk=message_id)
        consent = CommunicationConsent.objects.filter(
            patient=message.patient, purpose=message.purpose,
            channel="sms_or_whatsapp", consented=True,
        ).exists()
        if not consent or not message.consent_confirmed:
            raise MessageNotSendable("Recorded patient permission is required before sending.")
        if not message.patient.phone:
            raise MessageNotSendable("The patient has no phone number on file.")
        if message.status != MessageOutbox.Status.REVIEW:
            raise MessageNotSendable("This message has already been attempted or cancelled.")
        to_number = _destination(message.patient.phone)
        body = _message_text(message)
        message.status = MessageOutbox.Status.SENDING
        message.attempted_at = timezone.now()
        message.save(update_fields=["status", "attempted_at"])
        AuditEvent.objects.create(actor=actor, action="message_send_attempted", object_type="MessageOutbox",
                                  object_id=str(message.pk), details={"provider": "BulkSMS", "purpose": message.purpose})
        outbox_id = str(message.pk)

    raw_auth = f"{token_id}:{token_secret}".encode("utf-8")
    auth = base64.b64encode(raw_auth).decode("ascii")
    payload = {"to": to_number, "body": body}
    sender = os.environ.get("BULKSMS_SENDER", "").strip()
    if sender:
        payload["from"] = sender
    request = Request(
        "https://api.bulksms.com/v1/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            response_text = response.read(64 * 1024).decode("utf-8", errors="replace")
            if response.status < 200 or response.status >= 300:
                state = MessageOutbox.Status.FAILED if response.status < 500 else MessageOutbox.Status.UNKNOWN
                _set_state(outbox_id, state, error=f"BulkSMS returned HTTP {response.status}.")
                return state
    except HTTPError as exc:
        state = MessageOutbox.Status.FAILED if exc.code < 500 else MessageOutbox.Status.UNKNOWN
        _set_state(outbox_id, state, error=f"BulkSMS returned HTTP {exc.code}.")
        return state
    except (URLError, TimeoutError, OSError):
        _set_state(outbox_id, MessageOutbox.Status.UNKNOWN, error="No definitive response; check provider status before any resend.")
        return MessageOutbox.Status.UNKNOWN

    provider_id = ""
    try:
        parsed = json.loads(response_text)
        first = parsed[0] if isinstance(parsed, list) and parsed else parsed
        if isinstance(first, dict):
            provider_id = str(first.get("id") or first.get("messageId") or "")
            submission = first.get("submission")
            if not provider_id and isinstance(submission, dict):
                provider_id = str(submission.get("id") or "")
    except (json.JSONDecodeError, TypeError):
        pass
    _set_state(outbox_id, MessageOutbox.Status.SUBMITTED, provider_id=provider_id)
    return MessageOutbox.Status.SUBMITTED

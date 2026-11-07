from django.contrib import admin
from .models import AuditEvent, CommunicationConsent, MessageOutbox, Patient, UltrasoundReport, Visit

admin.site.register(Patient)
admin.site.register(Visit)
admin.site.register(UltrasoundReport)
admin.site.register(CommunicationConsent)
admin.site.register(MessageOutbox)
admin.site.register(AuditEvent)

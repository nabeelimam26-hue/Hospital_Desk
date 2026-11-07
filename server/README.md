# Hospital Desk backend

This folder contains the first persistent backend for the Hospital Desk prototype.

## Current scope

- Django 5.2 LTS application with session login and CSRF protection.
- SQLite for local development. PostgreSQL can be selected with environment variables for the hospital server.
- Patient, OPD visit, ultrasound report, communication consent, message outbox, and audit-event records.
- OPD storage retains only the three newest visits across the desk; older OPD visit rows are deleted when another visit is saved. Ultrasound reports remain archived without an application-level retention limit.
- Ultrasound report text is stored as lightweight key-value plain text in the PostgreSQL row; no PDF, Word file, browser download, or server filesystem write is generated.
- Draft reports can be edited; finalized reports cannot be overwritten.
- SMS uses the BulkSMS JSON API. Messages enter a review queue; the app never sends automatically.
- The existing `../index.html` interface is served by Django at `/`.

## Local development on Windows or Linux

Use a supported 64-bit computer and Python 3.11 or newer. From this folder:

```text
python -m venv .venv
```

Activate the environment, then install the pinned application dependencies:

```text
# Windows PowerShell
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt

# Ubuntu/Linux
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Create the local development database and the first account:

```text
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/` on that same PC and sign in with the account created above. The admin area is at `/admin/`.

The development server is for trying the workflow on the host PC only. Do not expose it to the hospital network or the internet, and do not enter real patient information in this development build.

## Deploy to GitHub and Vercel

The repository root includes a Vercel Python WSGI entry point and routes requests to Django. In GitHub, create an empty private repository. From this project folder run `git init`, `git add .`, `git commit -m "Prepare Hospital Desk for Vercel"`, `git branch -M main`, `git remote add origin https://github.com/OWNER/REPOSITORY.git`, then `git push -u origin main`. Replace OWNER/REPOSITORY with the actual repository path.

In Vercel choose **Add New → Project**, import that GitHub repository, leave the project root as `./`, then add a PostgreSQL database and set `DATABASE_URL`, `HOSPITAL_SECRET_KEY`, `HOSPITAL_DEBUG=0`, `HOSPITAL_ALLOWED_HOSTS=.vercel.app`, and `CSRF_TRUSTED_ORIGINS=https://YOUR-APP.vercel.app`. Also set any BulkSMS credentials only in Vercel Environment Variables. Redeploy after setting variables. Run `python server/manage.py migrate` against the production `DATABASE_URL` once before first use, then create the login account with `python server/manage.py createsuperuser` using a one-time trusted terminal with the same database URL.

Never use SQLite or local file writes for production persistence on Vercel. The ultrasound plain-text representation is kept in PostgreSQL, not as an independent `.txt` file; this preserves it across serverless instances while avoiding per-report downloads. Counters are database-backed. PostgreSQL adds a service cost and requires backups; do not store real patient records until access control, backup, privacy, and hosting decisions have been reviewed.

## BulkSMS credentials

The app reads `BULKSMS_TOKEN_ID` and `BULKSMS_TOKEN_SECRET` from the server process environment. Do not paste credentials into Python files, `index.html`, or GitHub. The credentials text file should stay outside the repository. In PowerShell, set the two values in the same terminal that will run Django, then start/restart the server:

```powershell
$env:BULKSMS_TOKEN_ID = "paste the token ID locally"
$env:BULKSMS_TOKEN_SECRET = "paste the token secret locally"
```

An optional `BULKSMS_SENDER` can be set if BulkSMS has configured a sender for the account. Leave it unset otherwise. The API request uses HTTPS and HTTP Basic authentication, as specified by [BulkSMS's JSON API](https://www.bulksms.com/developer/json/v1/).

Messages are queued only when the relevant permission checkbox is selected. To submit one, a signed-in user must click **Send SMS** and confirm the chargeable action. The app does not automatically retry uncertain submissions, because a timeout can happen after a provider accepted the SMS and retrying might send it twice. “Submitted to provider” is not a handset delivery receipt.

## Database selection

SQLite is the default for local development. To select PostgreSQL, set `DB_ENGINE=postgresql` and configure `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT` before running migrations. Switching an existing SQLite database to PostgreSQL requires a planned data migration and verification; changing the environment setting alone does not copy records.

## Before a hospital LAN rollout

Do not deploy this prototype with real patient records yet. A LAN rollout needs a maintained 64-bit Linux host, PostgreSQL, encrypted backups with a restore drill, production secret values, host firewall rules, a production WSGI server and reverse proxy, authentication rate limits, monitoring, and an agreed retention/restore process. Keep the application and database off the public internet. Set allowed hosts and HTTPS/secure-cookie settings for the chosen LAN deployment before staff use it.

The ultrasound fields and visual report templates are still placeholders pending the hospital's final report formats. The SMS provider integration is available, but credentials must be supplied at runtime and sending remains manual.

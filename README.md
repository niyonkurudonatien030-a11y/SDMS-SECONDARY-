# UR-CST Library Portal

A complete Python web application for managing a university library catalogue and loans.

## Features

- Browser-based online catalogue with search and sorting (A–Z, Z–A, author, publication year, subject, book code).
- Librarian and student accounts; librarians create student accounts.
- Password hashing, signed sessions, CSRF checks, role-based access control.
- Book inventory with metadata, unique book code, copies, cost and optional e-book link.
- Borrowing for 14 days, five active-loan limit, returns and immediate availability updates.
- Late fine: 500 RWF for each day after the due date.
- Outstanding debt records for late returns and lost books.
- Scheduled SMS reminders two days before due date.
- Twilio SMS integration, retrying failed reminders on later checks.
- Guest donation-offer form; librarian reviews offers.
- SQLite database; records remain after server restarts.

## Requirements

- Python 3.10 or newer
- Flask (installed from requirements.txt)
- Internet access and a Twilio account only if you want real SMS delivery.

## Run locally

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
python app.py --create-admin
python app.py
```

Open `http://127.0.0.1:5000` in your browser.

On Android, use a Python environment that supports installing Flask (for example, Pydroid 3 with its pip support or Termux). Keep the server running while testing.

## Enable real SMS reminders

Create a Twilio account, obtain an Account SID, Auth Token and an SMS-enabled sender number. Set these environment variables before starting the server:

```bash
export TWILIO_ACCOUNT_SID="your_account_sid"
export TWILIO_AUTH_TOKEN="your_auth_token"
export TWILIO_FROM_NUMBER="+1..."
```

For each student, the librarian must enter a valid phone number in international format, e.g. `+2507XXXXXXXX`.

The scheduler checks once per hour. It sends a reminder when the loan due date is exactly two calendar days away. A successful send is recorded and will not be sent again for that loan. Failed attempts are retried on the next hourly check.

**Do not put SMS credentials in the source code or share them.** SMS provider charges and country/number restrictions may apply. Verify local Rwanda SMS delivery and sender-ID requirements with the provider before relying on it.

## Make the catalogue accessible online

The application is a web portal, but `127.0.0.1` makes it accessible only on the same device. To let students access it over the internet, deploy it to a university server or VPS with:

- A domain name and HTTPS certificate.
- A production WSGI server (e.g. Gunicorn) and reverse proxy.
- A persistent disk for `library.db`, regular encrypted backups and restricted server access.
- A stable `SECRET_KEY` environment variable.
- `HOST=127.0.0.1` when behind a reverse proxy, or an appropriately protected network binding.
- `COOKIE_SECURE=1` when HTTPS is enabled.
- One scheduler process only. For multiple web workers, run the scheduler as a separate service and set `DISABLE_REMINDER_SCHEDULER=1` on web workers.

Example production environment:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export COOKIE_SECURE=1
export PORT=8000
pip install gunicorn
gunicorn -w 2 -b 127.0.0.1:8000 app:app
```

Run the scheduler as a separate process with the same database and Twilio environment:

```bash
python -c "from app import reminder_worker; reminder_worker()"
```

## Important project rules and assumptions

- Borrowing begins on the date the librarian/student records the loan; due date is 14 days later.
- A student may borrow the same book again after returning it, subject to availability and the active-loan limit.
- The reminder is sent two days before the due date.
- A late fine is calculated on return using completed calendar days after the due date: one day late = 500 RWF.
- Lost books are recorded as a debt equal to the book's recorded cost. The portal records this debt; it does not connect directly to the university finance system.
- A donation form records an offer. A librarian must review and add the accepted book to inventory.
- E-book links are supplied by the librarian. Only add links the library is authorized to share.
- Student accounts are created by librarians; there is no public student self-registration.

## Before real deployment

This is a working project foundation, not a security certification. Have the university IT team review it before handling real student records. Configure backups, HTTPS, access policies, SMS consent, privacy notices, data retention and a production database. For multiple application servers, replace SQLite with PostgreSQL and use a dedicated task queue/scheduler.

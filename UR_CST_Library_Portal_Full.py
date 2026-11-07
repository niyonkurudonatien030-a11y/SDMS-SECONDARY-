"""
UR-CST LIBRARY PORTAL
A web-based library management system.

Run:
    python -m venv .venv
    # Windows: .venv\Scripts\activate
    # Linux/macOS/Android terminal: source .venv/bin/activate
    pip install -r requirements.txt
    python app.py

Then open http://127.0.0.1:5000

Create the first librarian:
    python app.py --create-admin

Production:
    Set SECRET_KEY, DATABASE_PATH, PUBLIC_BASE_URL and (optionally) Twilio
    environment variables. Run behind HTTPS using a production WSGI server.
"""

from __future__ import annotations

import argparse
import hmac
import os
import secrets
import sqlite3
import threading
import time
from datetime import date, datetime, timedelta
from functools import wraps
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

from flask import (
    Flask, abort, flash, g, redirect, render_template_string,
    request, session, url_for
)
from werkzeug.security import generate_password_hash, check_password_hash

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(APP_DIR, "library.db"))
SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    # Convenient for local testing. Set a stable random SECRET_KEY in production.
    SECRET_KEY = secrets.token_hex(32)

BORROW_DAYS = 14
REMINDER_DAYS_BEFORE = 2
FINE_PER_DAY_RWF = 500
REMINDER_CHECK_SECONDS = 60 * 60
PORT = int(os.environ.get("PORT", "5000"))

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
    MAX_CONTENT_LENGTH=2 * 1024 * 1024,
)

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reg_no TEXT UNIQUE,
    full_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    department TEXT,
    year_level TEXT,
    age INTEGER,
    role TEXT NOT NULL CHECK(role IN ('librarian','student')),
    password_hash TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    publisher TEXT,
    publication_year INTEGER,
    edition TEXT,
    isbn TEXT,
    book_code TEXT NOT NULL UNIQUE,
    affiliation TEXT,
    cost_rwf INTEGER NOT NULL DEFAULT 0,
    total_copies INTEGER NOT NULL DEFAULT 1,
    available_copies INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    ebook_url TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL REFERENCES books(id),
    student_id INTEGER NOT NULL REFERENCES users(id),
    borrowed_on TEXT NOT NULL,
    due_on TEXT NOT NULL,
    returned_on TEXT,
    fine_rwf INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'borrowed'
        CHECK(status IN ('borrowed','returned','lost')),
    reminder_sent_at TEXT,
    reminder_status TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS donations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_name TEXT NOT NULL,
    donor_email TEXT,
    book_title TEXT NOT NULL,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS debts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES users(id),
    loan_id INTEGER REFERENCES loans(id),
    amount_rwf INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    settled INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS message_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    loan_id INTEGER NOT NULL REFERENCES loans(id),
    channel TEXT NOT NULL,
    destination TEXT,
    message TEXT NOT NULL,
    status TEXT NOT NULL,
    provider_response TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_loans_due ON loans(status, due_on);
CREATE INDEX IF NOT EXISTS idx_loans_student ON loans(student_id, status);
CREATE INDEX IF NOT EXISTS idx_books_title ON books(title);
"""

def now_iso():
    return datetime.now().isoformat(timespec="seconds")

def today():
    return date.today()

def db():
    if "db" not in g:
        conn = sqlite3.connect(DB_PATH, timeout=20)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        g.db = conn
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]

@app.context_processor
def inject_globals():
    return {
        "csrf_token": csrf_token,
        "current_user": getattr(g, "user", None),
        "fine_per_day": FINE_PER_DAY_RWF,
        "borrow_days": BORROW_DAYS,
    }

@app.before_request
def load_user_and_check_csrf():
    user_id = session.get("user_id")
    g.user = None
    if user_id:
        g.user = db().execute(
            "SELECT * FROM users WHERE id=? AND active=1", (user_id,)
        ).fetchone()
        if g.user is None:
            session.clear()
    if request.method == "POST":
        supplied = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")
        if not supplied or not expected or not hmac.compare_digest(supplied, expected):
            abort(400, "Security check failed. Reload the page and try again.")

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not g.user:
            flash("Please sign in first.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def role_required(*roles):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if g.user["role"] not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator

def clean(value):
    return (value or "").strip()

def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

def get_book(book_id):
    return db().execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()

def get_student(student_id):
    return db().execute(
        "SELECT * FROM users WHERE id=? AND role='student'", (student_id,)
    ).fetchone()

def fine_for(due_on, as_of=None):
    due = date.fromisoformat(due_on)
    check_date = as_of or today()
    late_days = max(0, (check_date - due).days)
    return late_days * FINE_PER_DAY_RWF

def sms_send(phone, message):
    """Send an SMS using Twilio's REST API; returns (success, provider detail)."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = os.environ.get("TWILIO_FROM_NUMBER", "")
    if not (sid and token and from_number and phone):
        return False, "SMS not configured or student phone number missing"
    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    data = urlencode({"To": phone, "From": from_number, "Body": message}).encode()
    import base64
    auth = base64.b64encode(f"{sid}:{token}".encode()).decode()
    req = Request(endpoint, data=data, headers={
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded",
    })
    try:
        with urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
            return 200 <= response.status < 300, body[:1000]
    except (HTTPError, URLError, TimeoutError) as exc:
        return False, str(exc)[:1000]

def send_due_reminders():
    """Send one reminder per active loan, on its due date minus two days."""
    init_db()
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    target = (today() + timedelta(days=REMINDER_DAYS_BEFORE)).isoformat()
    rows = conn.execute("""
        SELECT l.*, b.title, b.book_code, u.full_name, u.phone, u.email
        FROM loans l
        JOIN books b ON b.id=l.book_id
        JOIN users u ON u.id=l.student_id
        WHERE l.status='borrowed' AND l.due_on=? AND l.reminder_sent_at IS NULL
    """, (target,)).fetchall()
    for loan in rows:
        message = (
            f"UR-CST Library reminder: '{loan['title']}' "
            f"(code {loan['book_code']}) is due on {loan['due_on']}. "
            "Please return it on time. You may borrow it again after returning it."
        )
        ok, detail = sms_send(loan["phone"], message)
        status = "sent" if ok else "not_sent"
        conn.execute("""
            INSERT INTO message_log(loan_id,channel,destination,message,status,
                                    provider_response,created_at)
            VALUES(?,?,?,?,?,?,?)
        """, (loan["id"], "SMS", loan["phone"], message, status, detail, now_iso()))
        if ok:
            conn.execute(
                "UPDATE loans SET reminder_sent_at=?, reminder_status='sent' WHERE id=?",
                (now_iso(), loan["id"])
            )
        else:
            # Do not mark as sent. It can be retried by the next scheduler pass.
            conn.execute(
                "UPDATE loans SET reminder_status='failed' WHERE id=?", (loan["id"],)
            )
    conn.commit()
    conn.close()
    return len(rows)

def reminder_worker():
    """Background scheduler. For multi-worker production, use one separate scheduler."""
    while True:
        try:
            send_due_reminders()
        except Exception as exc:
            app.logger.exception("Reminder scheduler error: %s", exc)
        time.sleep(REMINDER_CHECK_SECONDS)

def start_scheduler():
    if os.environ.get("DISABLE_REMINDER_SCHEDULER") == "1":
        return
    thread = threading.Thread(target=reminder_worker, daemon=True, name="library-reminders")
    thread.start()

def render_page(title, body, **context):
    return render_template_string(BASE, title=title, body=body, **context)

BASE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ title }} | UR-CST Library</title>
<style>
:root{--navy:#102a43;--blue:#176b87;--teal:#2a9d8f;--paper:#f4f7fa;--ink:#243447;--muted:#64748b;--line:#dbe4ec;--red:#b42318}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 "Segoe UI",Arial,sans-serif}
header{background:var(--navy);color:white;padding:16px max(20px,calc((100% - 1120px)/2));display:flex;gap:18px;align-items:center;justify-content:space-between;flex-wrap:wrap}
.brand{font-size:20px;font-weight:750;letter-spacing:.2px}nav{display:flex;gap:14px;flex-wrap:wrap}nav a{color:#e8f4f8;text-decoration:none;font-size:14px}
main{max-width:1120px;margin:28px auto;padding:0 18px}.panel{background:white;border:1px solid var(--line);border-radius:12px;padding:22px;margin:16px 0;box-shadow:0 3px 12px #102a430b}
h1{font-size:28px;color:var(--navy);margin:0 0 12px}h2{font-size:20px;color:var(--navy);margin:0 0 12px}h3{font-size:17px;color:var(--navy)}
p{margin:8px 0}.muted{color:var(--muted);font-size:14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}
label{display:block;font-weight:650;font-size:14px;margin:12px 0 5px}input,select,textarea{width:100%;padding:11px;border:1px solid #bdcbd8;border-radius:7px;font:inherit;background:white}
textarea{min-height:85px}button,.btn{display:inline-block;background:var(--blue);color:white;border:0;border-radius:7px;padding:10px 15px;font:600 14px inherit;text-decoration:none;cursor:pointer}
button:hover,.btn:hover{background:var(--navy)}.btn.secondary{background:#64748b}.btn.danger{background:var(--red)}.actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:10px;border-bottom:1px solid var(--line);vertical-align:top}th{background:#eef4f8;color:var(--navy)}
.table-wrap{overflow-x:auto}.notice{padding:11px 14px;border-radius:8px;margin:10px 0;background:#e8f4f8}.notice.warning{background:#fff4db}.notice.error{background:#feeceb}.notice.success{background:#e8f7ef}
.badge{display:inline-block;border-radius:20px;padding:2px 9px;background:#e7eef5;font-size:12px;font-weight:700}.cards .panel{margin:0}
footer{text-align:center;padding:28px;color:var(--muted);font-size:13px}
@media(max-width:600px){header{padding:14px 16px}main{margin:16px auto}h1{font-size:23px}.panel{padding:16px}table{min-width:720px}}
</style></head>
<body>
<header><div class="brand">UR-CST · Library Portal</div><nav>
<a href="{{ url_for('catalogue') }}">Catalogue</a>
{% if current_user %}
<a href="{{ url_for('dashboard') }}">Dashboard</a>
{% if current_user['role']=='librarian' %}<a href="{{ url_for('librarian') }}">Librarian</a>{% endif %}
<a href="{{ url_for('logout') }}">Sign out</a>
{% else %}<a href="{{ url_for('login') }}">Sign in</a>{% endif %}
<a href="{{ url_for('donate') }}">Donate a book</a>
</nav></header>
<main>
{% with messages=get_flashed_messages(with_categories=true) %}{% for category,message in messages %}
<div class="notice {{ category }}">{{ message }}</div>{% endfor %}{% endwith %}
{{ body|safe }}
</main><footer>UR-CST Library Portal · Borrowing period: {{ borrow_days }} days · Late fine: {{ fine_per_day }} RWF/day</footer>
</body></html>
"""

@app.route("/")
def home():
    return redirect(url_for("catalogue"))

@app.route("/catalogue")
def catalogue():
    q = clean(request.args.get("q"))
    affiliation = clean(request.args.get("affiliation"))
    sort = request.args.get("sort", "title")
    allowed = {
        "title": "title COLLATE NOCASE ASC", "za": "title COLLATE NOCASE DESC",
        "author": "author COLLATE NOCASE ASC", "year_new": "publication_year DESC",
        "year_old": "publication_year ASC", "code": "book_code ASC",
        "affiliation": "affiliation COLLATE NOCASE ASC",
    }
    sql = "SELECT * FROM books WHERE available_copies > 0"
    params = []
    if q:
        sql += " AND (title LIKE ? OR author LIKE ? OR book_code LIKE ? OR isbn LIKE ?)"
        params += [f"%{q}%"] * 4
    if affiliation:
        sql += " AND affiliation=?"
        params.append(affiliation)
    sql += " ORDER BY " + allowed.get(sort, allowed["title"])
    books = db().execute(sql, params).fetchall()
    subjects = db().execute(
        "SELECT DISTINCT affiliation FROM books WHERE affiliation IS NOT NULL AND affiliation<>'' ORDER BY affiliation"
    ).fetchall()
    body = """
    <h1>Library catalogue</h1><p class="muted">Search books currently available for borrowing.</p>
    <section class="panel"><form method="get" class="grid">
    <div><label>Search title, author, code or ISBN</label><input name="q" value="{{ q }}"></div>
    <div><label>Subject / affiliation</label><select name="affiliation"><option value="">All subjects</option>
    {% for s in subjects %}<option {{ 'selected' if affiliation==s['affiliation'] else '' }}>{{ s['affiliation'] }}</option>{% endfor %}</select></div>
    <div><label>Sort by</label><select name="sort">
    {% for val,label in [('title','A–Z'),('za','Z–A'),('author','Author'),('year_new','Newest publication'),('year_old','Oldest publication'),('code','Book code'),('affiliation','Subject')] %}
    <option value="{{val}}" {{'selected' if sort==val else ''}}>{{label}}</option>{% endfor %}
    </select></div><div style="align-self:end"><button>Search catalogue</button></div></form></section>
    <section class="panel"><div class="table-wrap"><table><thead><tr><th>Book</th><th>Author</th><th>Subject</th><th>Year</th><th>Code</th><th>Copies</th><th>Action</th></tr></thead><tbody>
    {% for b in books %}<tr><td><b>{{b['title']}}</b><br><span class="muted">{{b['publisher'] or ''}} {{b['edition'] or ''}}</span></td>
    <td>{{b['author']}}</td><td>{{b['affiliation'] or '—'}}</td><td>{{b['publication_year'] or '—'}}</td><td>{{b['book_code']}}</td><td>{{b['available_copies']}} / {{b['total_copies']}}</td>
    <td>{% if b['ebook_url'] %}<a href="{{b['ebook_url']}}" target="_blank" rel="noopener">Read e-book</a>{% endif %}
    {% if current_user and current_user['role']=='student' %}<form method="post" action="{{url_for('borrow',book_id=b['id'])}}"><input type="hidden" name="_csrf" value="{{csrf_token()}}"><button>Borrow</button></form>{% elif not current_user %}<a href="{{url_for('login')}}">Sign in to borrow</a>{% endif %}</td></tr>
    {% else %}<tr><td colspan="7">No available books match your search.</td></tr>{% endfor %}
    </tbody></table></div></section>
    """
    return render_page("Catalogue", body, books=books, q=q, subjects=subjects,
                       affiliation=affiliation, sort=sort)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = clean(request.form.get("username"))
        password = request.form.get("password", "")
        user = db().execute(
            "SELECT * FROM users WHERE (reg_no=? OR email=?) AND active=1",
            (username, username)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            csrf_token()
            flash("Welcome back.", "success")
            return redirect(url_for("dashboard"))
        flash("Incorrect login details or inactive account.", "error")
    body = """
    <h1>Sign in</h1><section class="panel" style="max-width:520px">
    <form method="post"><input type="hidden" name="_csrf" value="{{csrf_token()}}">
    <label>Registration number or email</label><input name="username" required autocomplete="username">
    <label>Password</label><input type="password" name="password" required autocomplete="current-password">
    <div class="actions"><button>Sign in</button></div></form>
    <p class="muted">Student accounts are created by the librarian. Contact the library if you do not yet have an account.</p></section>
    """
    return render_page("Sign in", body)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have signed out.", "success")
    return redirect(url_for("catalogue"))

@app.route("/dashboard")
@login_required
def dashboard():
    if g.user["role"] == "librarian":
        return redirect(url_for("librarian"))
    loans = db().execute("""
        SELECT l.*,b.title,b.book_code FROM loans l JOIN books b ON b.id=l.book_id
        WHERE l.student_id=? ORDER BY l.borrowed_on DESC
    """, (g.user["id"],)).fetchall()
    debts = db().execute(
        "SELECT COALESCE(SUM(amount_rwf),0) AS total FROM debts WHERE student_id=? AND settled=0",
        (g.user["id"],)
    ).fetchone()["total"]
    body = """
    <h1>Student dashboard</h1><p>Welcome, <b>{{current_user['full_name']}}</b>.</p>
    <section class="panel"><h2>My borrowed books</h2><div class="table-wrap"><table>
    <tr><th>Book</th><th>Borrowed</th><th>Due date</th><th>Current fine</th><th>Status</th><th>Action</th></tr>
    {% for l in loans %}<tr><td>{{l['title']}} ({{l['book_code']}})</td><td>{{l['borrowed_on']}}</td><td>{{l['due_on']}}</td>
    <td>{{ (l['fine_rwf'] if l['status']=='returned' else ((today_date - date_parse(l['due_on'])).days|int if false else 0)) }}</td>
    <td><span class="badge">{{l['status']}}</span></td><td>{% if l['status']=='borrowed' %}
    <form method="post" action="{{url_for('return_book',loan_id=l['id'])}}"><input type="hidden" name="_csrf" value="{{csrf_token()}}"><button>Return</button></form>
    {% endif %}</td></tr>{% endfor %}
    {% if not loans %}<tr><td colspan="6">You have no loan records yet.</td></tr>{% endif %}
    </table></div></section>
    <section class="panel"><h2>Outstanding debt</h2><p><b>{{debts}} RWF</b></p>
    <p class="muted">Late fines are calculated at 500 RWF for each day after the due date. A returned book can be borrowed again if a copy is available.</p>
    <a class="btn" href="{{url_for('catalogue')}}">Browse available books</a></section>
    """
    # Remove a display-only placeholder expression from the template; actual fine is passed below.
    loan_rows = []
    for l in loans:
        item = dict(l)
        item["current_fine"] = fine_for(l["due_on"]) if l["status"] == "borrowed" else l["fine_rwf"]
        loan_rows.append(item)
    body = body.replace("{{ (l['fine_rwf'] if l['status']=='returned' else ((today_date - date_parse(l['due_on'])).days|int if false else 0)) }}", "{{l['current_fine']}}")
    return render_page("Student dashboard", body, loans=loan_rows, debts=debts)

@app.route("/borrow/<int:book_id>", methods=["POST"])
@role_required("student")
def borrow(book_id):
    conn = db()
    book = conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
    if not book or book["available_copies"] < 1:
        flash("That book is not currently available.", "warning")
        return redirect(url_for("catalogue"))
    active = conn.execute(
        "SELECT COUNT(*) FROM loans WHERE student_id=? AND status='borrowed'",
        (g.user["id"],)
    ).fetchone()[0]
    if active >= 5:
        flash("You have reached the limit of five active borrowed books.", "warning")
        return redirect(url_for("catalogue"))
    conn.execute("""
        INSERT INTO loans(book_id,student_id,borrowed_on,due_on,created_at)
        VALUES(?,?,?,?,?)
    """, (book_id, g.user["id"], today().isoformat(),
          (today()+timedelta(days=BORROW_DAYS)).isoformat(), now_iso()))
    conn.execute("UPDATE books SET available_copies=available_copies-1 WHERE id=?", (book_id,))
    conn.commit()
    flash(f"Book borrowed. Return by {(today()+timedelta(days=BORROW_DAYS)).isoformat()}.", "success")
    return redirect(url_for("dashboard"))

@app.route("/return/<int:loan_id>", methods=["POST"])
@role_required("student", "librarian")
def return_book(loan_id):
    conn = db()
    loan = conn.execute("SELECT * FROM loans WHERE id=?", (loan_id,)).fetchone()
    if not loan or loan["status"] != "borrowed":
        flash("Active loan not found.", "warning")
        return redirect(url_for("dashboard"))
    if g.user["role"] == "student" and loan["student_id"] != g.user["id"]:
        abort(403)
    fine = fine_for(loan["due_on"])
    conn.execute("""
        UPDATE loans SET status='returned',returned_on=?,fine_rwf=? WHERE id=?
    """, (today().isoformat(), fine, loan_id))
    conn.execute("UPDATE books SET available_copies=MIN(total_copies,available_copies+1) WHERE id=?",
                 (loan["book_id"],))
    if fine:
        conn.execute("""
            INSERT INTO debts(student_id,loan_id,amount_rwf,reason,created_at)
            VALUES(?,?,?,?,?)
        """, (loan["student_id"], loan_id, fine, "Late return fine", now_iso()))
    conn.commit()
    flash(f"Book returned. Late fine: {fine:,} RWF.", "success")
    return redirect(url_for("dashboard") if g.user["role"] == "student" else url_for("librarian"))

@app.route("/donate", methods=["GET", "POST"])
def donate():
    if request.method == "POST":
        name = clean(request.form.get("donor_name"))
        title = clean(request.form.get("book_title"))
        if not name or not title:
            flash("Donor name and book title are required.", "warning")
        else:
            db().execute("""
                INSERT INTO donations(donor_name,donor_email,book_title,notes,created_at)
                VALUES(?,?,?,?,?)
            """, (name, clean(request.form.get("donor_email")), title,
                  clean(request.form.get("notes")), now_iso()))
            db().commit()
            flash("Thank you. The library has received your donation offer for review.", "success")
            return redirect(url_for("donate"))
    body = """
    <h1>Donate a book</h1><section class="panel" style="max-width:650px">
    <p>Submit a book donation offer. A librarian will review it before adding it to the catalogue.</p>
    <form method="post"><input type="hidden" name="_csrf" value="{{csrf_token()}}">
    <label>Your name</label><input name="donor_name" required>
    <label>Email (optional)</label><input type="email" name="donor_email">
    <label>Book title</label><input name="book_title" required>
    <label>Additional information</label><textarea name="notes"></textarea>
    <div class="actions"><button>Submit donation offer</button></div></form></section>
    """
    return render_page("Donate a book", body)

@app.route("/librarian")
@role_required("librarian")
def librarian():
    conn = db()
    stats = {
        "books": conn.execute("SELECT COUNT(*) FROM books").fetchone()[0],
        "students": conn.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0],
        "active": conn.execute("SELECT COUNT(*) FROM loans WHERE status='borrowed'").fetchone()[0],
        "available": conn.execute("SELECT COALESCE(SUM(available_copies),0) FROM books").fetchone()[0],
    }
    loans = conn.execute("""
        SELECT l.*,b.title,b.book_code,u.full_name,u.reg_no,u.phone
        FROM loans l JOIN books b ON b.id=l.book_id JOIN users u ON u.id=l.student_id
        WHERE l.status='borrowed' ORDER BY l.due_on
    """).fetchall()
    students = conn.execute("SELECT * FROM users WHERE role='student' ORDER BY full_name").fetchall()
    donations = conn.execute("SELECT * FROM donations WHERE status='pending' ORDER BY created_at").fetchall()
    books = conn.execute("SELECT * FROM books ORDER BY title").fetchall()
    body = """
    <h1>Librarian dashboard</h1><div class="grid cards">
    {% for label,value in [('Book titles',stats.books),('Registered students',stats.students),('Active loans',stats.active),('Available copies',stats.available)] %}
    <section class="panel"><div class="muted">{{label}}</div><h2>{{value}}</h2></section>{% endfor %}</div>
    <section class="panel"><h2>Add a book</h2><form method="post" action="{{url_for('add_book')}}" class="grid">
    <input type="hidden" name="_csrf" value="{{csrf_token()}}">
    {% for name,label,required in [('title','Title',true),('author','Author',true),('publisher','Publisher',false),('publication_year','Publication year',false),('edition','Edition',false),('isbn','ISBN',false),('book_code','Unique book code',true),('affiliation','Subject / affiliation',false),('cost_rwf','Cost (RWF)',false),('total_copies','Number of copies',true),('ebook_url','E-book URL (optional)',false)] %}
    <div><label>{{label}}</label><input name="{{name}}" {{'required' if required else ''}}></div>{% endfor %}
    <div style="grid-column:1/-1"><label>Description</label><textarea name="description"></textarea></div>
    <div><button>Add book to catalogue</button></div></form></section>
    <section class="panel"><h2>Register a student</h2><form method="post" action="{{url_for('add_student')}}" class="grid">
    <input type="hidden" name="_csrf" value="{{csrf_token()}}">
    {% for name,label,typ in [('reg_no','Registration number','text'),('full_name','Full name','text'),('email','Email','email'),('phone','Phone (international format, e.g. +250...)','text'),('department','Department','text'),('year_level','Year / grade','text'),('age','Age','number'),('password','Initial password','password')] %}
    <div><label>{{label}}</label><input type="{{typ}}" name="{{name}}" {{'required' if name in ['reg_no','full_name','password'] else ''}}></div>{% endfor %}
    <div><button>Create student account</button></div></form></section>
    <section class="panel"><h2>Active borrowed books</h2><div class="table-wrap"><table>
    <tr><th>Student</th><th>Registration</th><th>Book</th><th>Borrowed</th><th>Due</th><th>Fine today</th><th>Action</th></tr>
    {% for l in loans %}<tr><td>{{l['full_name']}}</td><td>{{l['reg_no']}}</td><td>{{l['title']}} ({{l['book_code']}})</td>
    <td>{{l['borrowed_on']}}</td><td>{{l['due_on']}}</td><td>{{fine_for_template(l['due_on'])}} RWF</td>
    <td><form method="post" action="{{url_for('return_book',loan_id=l['id'])}}"><input type="hidden" name="_csrf" value="{{csrf_token()}}"><button>Record return</button></form>
    <form method="post" action="{{url_for('mark_lost',loan_id=l['id'])}}"><input type="hidden" name="_csrf" value="{{csrf_token()}}"><button class="danger">Mark lost</button></form></td></tr>{% else %}<tr><td colspan="7">No active loans.</td></tr>{% endfor %}
    </table></div></section>
    <section class="panel"><h2>Book inventory</h2><div class="table-wrap"><table><tr><th>Title</th><th>Code</th><th>Copies</th><th>Cost</th><th>Action</th></tr>
    {% for b in books %}<tr><td>{{b['title']}}</td><td>{{b['book_code']}}</td><td>{{b['available_copies']}} / {{b['total_copies']}}</td><td>{{b['cost_rwf']}} RWF</td>
    <td><form method="post" action="{{url_for('delete_book',book_id=b['id'])}}" onsubmit="return confirm('Delete this book record?')"><input type="hidden" name="_csrf" value="{{csrf_token()}}"><button class="danger">Delete</button></form></td></tr>{% endfor %}</table></div></section>
    <section class="panel"><h2>Registered students</h2><div class="table-wrap"><table><tr><th>Name</th><th>Reg. no.</th><th>Email</th><th>Phone</th><th>Department</th><th>Action</th></tr>
    {% for s in students %}<tr><td>{{s['full_name']}}</td><td>{{s['reg_no']}}</td><td>{{s['email'] or '—'}}</td><td>{{s['phone'] or '—'}}</td><td>{{s['department'] or '—'}}</td>
    <td><form method="post" action="{{url_for('deactivate_student',student_id=s['id'])}}"><input type="hidden" name="_csrf" value="{{csrf_token()}}"><button class="danger">Deactivate</button></form></td></tr>{% endfor %}</table></div></section>
    <section class="panel"><h2>Pending book donations</h2>{% for d in donations %}<p><b>{{d['book_title']}}</b> — {{d['donor_name']}} · {{d['notes']}}</p>
    <form method="post" action="{{url_for('review_donation',donation_id=d['id'])}}"><input type="hidden" name="_csrf" value="{{csrf_token()}}"><button name="decision" value="accepted">Accept</button> <button class="secondary" name="decision" value="declined">Decline</button></form><hr>{% else %}<p>No pending donations.</p>{% endfor %}</section>
    <section class="panel"><h2>Reminder message log</h2><p class="muted">The background service checks hourly. A reminder is due exactly two days before the book's due date. Failed SMS attempts are retried on later checks.</p>
    <p>SMS status is visible in the message log database table. Configure Twilio environment variables to deliver real SMS.</p>
    <form method="post" action="{{url_for('run_reminders')}}"><input type="hidden" name="_csrf" value="{{csrf_token()}}"><button class="secondary">Run reminder check now</button></form></section>
    """
    return render_page("Librarian dashboard", body, stats=stats, loans=loans,
                       students=students, donations=donations, books=books,
                       fine_for_template=fine_for)

@app.route("/librarian/book/add", methods=["POST"])
@role_required("librarian")
def add_book():
    f = request.form
    title, author, code = clean(f.get("title")), clean(f.get("author")), clean(f.get("book_code"))
    copies = max(1, parse_int(f.get("total_copies"), 1))
    if not title or not author or not code:
        flash("Title, author and book code are required.", "warning")
    else:
        try:
            db().execute("""
                INSERT INTO books(title,author,publisher,publication_year,edition,isbn,book_code,
                    affiliation,cost_rwf,total_copies,available_copies,description,ebook_url,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (title, author, clean(f.get("publisher")), parse_int(f.get("publication_year"), None),
                  clean(f.get("edition")), clean(f.get("isbn")), code, clean(f.get("affiliation")),
                  max(0,parse_int(f.get("cost_rwf"))), copies, copies, clean(f.get("description")),
                  clean(f.get("ebook_url")), now_iso()))
            db().commit()
            flash("Book added to the online catalogue.", "success")
        except sqlite3.IntegrityError:
            flash("That book code already exists. Use a unique code.", "error")
    return redirect(url_for("librarian"))

@app.route("/librarian/student/add", methods=["POST"])
@role_required("librarian")
def add_student():
    f = request.form
    reg, name, password = clean(f.get("reg_no")), clean(f.get("full_name")), f.get("password","")
    if not reg or not name or len(password) < 8:
        flash("Registration number and name are required; initial password must be at least 8 characters.", "warning")
    else:
        try:
            db().execute("""
                INSERT INTO users(reg_no,full_name,email,phone,department,year_level,age,role,password_hash,created_at)
                VALUES(?,?,?,?,?,?,?,'student',?,?)
            """, (reg, name, clean(f.get("email")), clean(f.get("phone")), clean(f.get("department")),
                  clean(f.get("year_level")), parse_int(f.get("age"), None),
                  generate_password_hash(password), now_iso()))
            db().commit()
            flash("Student account created. Give the student their registration number and initial password securely.", "success")
        except sqlite3.IntegrityError:
            flash("That registration number is already registered.", "error")
    return redirect(url_for("librarian"))

@app.route("/librarian/book/<int:book_id>/delete", methods=["POST"])
@role_required("librarian")
def delete_book(book_id):
    active = db().execute(
        "SELECT COUNT(*) FROM loans WHERE book_id=? AND status='borrowed'", (book_id,)
    ).fetchone()[0]
    if active:
        flash("Cannot delete a book while it has active loans.", "warning")
    else:
        db().execute("DELETE FROM books WHERE id=?", (book_id,))
        db().commit()
        flash("Book record deleted.", "success")
    return redirect(url_for("librarian"))

@app.route("/librarian/student/<int:student_id>/deactivate", methods=["POST"])
@role_required("librarian")
def deactivate_student(student_id):
    active = db().execute(
        "SELECT COUNT(*) FROM loans WHERE student_id=? AND status='borrowed'", (student_id,)
    ).fetchone()[0]
    if active:
        flash("Student has active loans. Record returns before deactivation.", "warning")
    else:
        db().execute("UPDATE users SET active=0 WHERE id=? AND role='student'", (student_id,))
        db().commit()
        flash("Student account deactivated.", "success")
    return redirect(url_for("librarian"))

@app.route("/librarian/loan/<int:loan_id>/lost", methods=["POST"])
@role_required("librarian")
def mark_lost(loan_id):
    conn = db()
    loan = conn.execute("""
        SELECT l.*,b.cost_rwf,b.title FROM loans l JOIN books b ON b.id=l.book_id
        WHERE l.id=? AND l.status='borrowed'
    """, (loan_id,)).fetchone()
    if not loan:
        flash("Active loan not found.", "warning")
    else:
        conn.execute("UPDATE loans SET status='lost' WHERE id=?", (loan_id,))
        conn.execute("INSERT INTO debts(student_id,loan_id,amount_rwf,reason,created_at) VALUES(?,?,?,?,?)",
                     (loan["student_id"], loan_id, loan["cost_rwf"], f"Lost book: {loan['title']}", now_iso()))
        # Lost copy is not returned to available inventory.
        conn.commit()
        flash(f"Book marked lost. {loan['cost_rwf']} RWF recorded as a debt for the university system.", "success")
    return redirect(url_for("librarian"))

@app.route("/librarian/donation/<int:donation_id>", methods=["POST"])
@role_required("librarian")
def review_donation(donation_id):
    decision = request.form.get("decision")
    if decision not in ("accepted", "declined"):
        abort(400)
    db().execute("UPDATE donations SET status=? WHERE id=?", (decision, donation_id))
    db().commit()
    flash("Donation decision recorded. Add accepted books through the book form.", "success")
    return redirect(url_for("librarian"))

@app.route("/librarian/reminders/run", methods=["POST"])
@role_required("librarian")
def run_reminders():
    count = send_due_reminders()
    flash(f"Reminder check completed. {count} due reminder record(s) were processed.", "success")
    return redirect(url_for("librarian"))

@app.errorhandler(403)
def forbidden(_error):
    return render_page("Access denied", "<h1>Access denied</h1><p>You do not have permission to view this page.</p>"), 403

@app.errorhandler(404)
def not_found(_error):
    return render_page("Not found", "<h1>Page not found</h1><p>The requested page does not exist.</p>"), 404

def create_admin_interactive():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM users WHERE role='librarian'").fetchone()[0]
    if count:
        print("A librarian account already exists. Use the existing account.")
        conn.close()
        return
    print("Create the first UR-CST library administrator.")
    reg = input("Staff ID / username: ").strip()
    name = input("Full name: ").strip()
    email = input("Email (optional): ").strip()
    import getpass
    password = getpass.getpass("Password (minimum 12 characters): ")
    confirm = getpass.getpass("Confirm password: ")
    if not reg or not name or len(password) < 12 or password != confirm:
        print("Invalid details. No account created.")
        conn.close()
        return
    conn.execute("""
        INSERT INTO users(reg_no,full_name,email,role,password_hash,created_at)
        VALUES(?,?,?,'librarian',?,?)
    """, (reg, name, email, generate_password_hash(password), now_iso()))
    conn.commit()
    conn.close()
    print("Librarian created. Start the server with: python app.py")

def main():
    parser = argparse.ArgumentParser(description="UR-CST Library Portal")
    parser.add_argument("--create-admin", action="store_true",
                        help="Create the first librarian account interactively")
    args = parser.parse_args()
    init_db()
    if args.create_admin:
        create_admin_interactive()
        return
    # Avoid duplicate background schedulers under Flask's development reloader.
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
        start_scheduler()
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=PORT,
            debug=os.environ.get("FLASK_DEBUG", "0") == "1", use_reloader=False)

if __name__ == "__main__":
    main()

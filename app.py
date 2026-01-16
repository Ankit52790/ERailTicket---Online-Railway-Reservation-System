# app.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import date, datetime, timedelta
import hashlib
import binascii
import secrets
import smtplib
from email.message import EmailMessage
import random
import time
from PIL import Image
import base64
import io
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import os

def send_verification_email(to_email, verification_code):
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Railway Reservation - Email Verification"
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email

        html = f"""
        <html>
        <body>
            <h2>Welcome to Railway Reservation System 🚆</h2>
            <p>Your verification code is:</p>
            <h3 style='color: #2E86C1;'>{verification_code}</h3>
            <p>Please enter this code in the app to activate your account.</p>
            <p>Thank you,<br>Railway Reservation Team</p>
        </body>
        </html>
        """

        msg.attach(MIMEText(html, "html"))

        # Send email
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)

        return True
    except Exception as e:
        print("Email sending failed:", e)
        return False


# ---------------------------
# MUST be the very first Streamlit command
# ---------------------------
st.set_page_config(page_title="ERailTicket - Railway Reservation System",
                   page_icon="🚆", layout="wide")

# =========================
# THEME / CSS (IRCTC-like)
# =========================
PRIMARY = "#213d77"  # IRCTC modern blue
ACCENT = "#fcb040"   # orange accent
BG = "#f7f9fc"
CARD = "#ffffff"

st.markdown(f"""
<style>
:root {{
  --primary: {PRIMARY};
  --accent: {ACCENT};
  --bg: {BG};
  --card: {CARD};
}}
body {{
  background-color: var(--bg);
}}
/* Header */
.header-container {{
  text-align: center;
  background: linear-gradient(90deg, rgba(33,61,119,0.95), rgba(33,61,119,0.95));
  color: white;
  padding: 18px 12px;
  border-radius: 8px;
  margin-bottom: 12px;
}}
.header-subtitle {{
  color: {ACCENT};
  margin-top:6px;
  font-size:16px;
  font-weight:600;
}}

/* Card */
.app-card {{
  background: var(--card);
  border-radius: 10px;
  padding: 16px;
  box-shadow: 0 3px 14px rgba(0,0,0,0.06);
  margin-bottom: 12px;
}}

/* Buttons */
.stButton>button {{
  background-color: var(--primary);
  color: white;
  border-radius: 8px;
  padding: 8px 14px;
  font-weight: 600;
  border: none;
}}
.stButton>button:hover {{
  filter: brightness(0.95);
}}

/* Inputs rounding */
div[data-baseweb="input"] > div, .stTextInput, .stNumberInput, .stSelectbox, .stDateInput, .stRadio, .stMultiSelect {{
    border-radius: 8px !important;
}}

/* Table hover */
[data-testid="stDataFrameWrapper"] tbody tr:hover {{
    background: #fff6f3;
}}
</style>
""", unsafe_allow_html=True)

# =========================
# Sidebar branding (logo + title)
# =========================
# Expect logo.png to be in same folder as app.py
LOGO_FILENAME = "logo.png"

try:
    logo_image = Image.open(LOGO_FILENAME)
    st.sidebar.image(logo_image, width=80)
    st.sidebar.markdown("<h4 style='text-align:center;margin-top:6px;margin-bottom:6px'>ERailTicket</h4>", unsafe_allow_html=True)
except Exception:
    # if logo missing, don't break app
    st.sidebar.write(" ")

# =========================
# Center header (H2 style) with logo above title
# =========================
def img_to_base64_str(img_path):
    try:
        with open(img_path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except Exception:
        return None

logo_b64 = img_to_base64_str(LOGO_FILENAME)
if logo_b64:
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" width="80" style="display:block;margin-left:auto;margin-right:auto;" />'
else:
    logo_html = ""

st.markdown(f"""
<div class="header-container">
  {logo_html}
  <h1 style="margin:8px 0 0 0; font-size:28px;">ERailTicket</h1>
  <div class="header-subtitle">Book your journey, the smart way!</div>
</div>
""", unsafe_allow_html=True)

# =========================
# Database setup
# =========================
conn = sqlite3.connect('railway_system.db', check_same_thread=False)
c = conn.cursor()

def create_DB_if_Not_available():
    c.execute('''CREATE TABLE IF NOT EXISTS users
                (username TEXT PRIMARY KEY, password TEXT, email TEXT, email_verified INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS employees
                (employee_id TEXT PRIMARY KEY, password TEXT, designation TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS trains
                (train_number TEXT, train_name TEXT, departure_date TEXT, starting_destination TEXT, ending_destination TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS email_codes
                (username TEXT, code TEXT, purpose TEXT, expiry_ts INTEGER)''')
    conn.commit()

create_DB_if_Not_available()

# Ensure users table has email & email_verified (safe migration)
try:
    cols = [r[1] for r in c.execute("PRAGMA table_info(users)")]
    if "email" not in cols or "email_verified" not in cols:
        # Recreate table to ensure columns exist could be heavy; try ALTER
        if "email" not in cols:
            try:
                c.execute("ALTER TABLE users ADD COLUMN email TEXT")
            except sqlite3.OperationalError:
                pass
        if "email_verified" not in cols:
            try:
                c.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
        conn.commit()
except Exception:
    # ignore if users not present
    pass

# =========================
# Password utilities (PBKDF2)
# =========================
def hash_password(password: str, iterations: int = 100_000) -> str:
    salt = secrets.token_bytes(16)
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, iterations)
    return f"{binascii.hexlify(salt).decode()}${binascii.hexlify(hash_bytes).decode()}"

def verify_password(stored: str, provided_password: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split("$")
        salt = binascii.unhexlify(salt_hex)
        stored_hash = binascii.unhexlify(hash_hex)
        test_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode(), salt, 100_000)
        return secrets.compare_digest(stored_hash, test_hash)
    except Exception:
        return False

# =========================
# Seat / train utilities
# =========================
def to_date_text(d: date) -> str:
    if isinstance(d, date):
        return d.isoformat()
    return str(d)

def categorize_seat(seat_number: int) -> str:
    if (seat_number % 10) in [0, 4, 5, 9]:
        return "Window"
    elif (seat_number % 10) in [2, 3, 6, 7]:
        return "Aisle"
    else:
        return "Middle"

def create_seat_table(train_number: str):
    # safe table name: remove spaces / dangerous chars
    tname = "".join(ch for ch in train_number if ch.isalnum() or ch in ("_", "-"))
    c.execute(f'''
        CREATE TABLE IF NOT EXISTS seats_{tname} (
            seat_number INTEGER PRIMARY KEY,
            seat_type TEXT,
            booked INTEGER,
            passenger_name TEXT,
            passenger_age INTEGER,
            passenger_gender TEXT
        )
    ''')
    try:
        cur = c.execute(f"SELECT COUNT(*) FROM seats_{tname}")
        count = cur.fetchone()[0]
    except sqlite3.OperationalError:
        count = 0
    if count == 0:
        rows = []
        for i in range(1, 51):
            rows.append((i, categorize_seat(i), 0, "", None, ""))
        c.executemany(
            f"INSERT INTO seats_{tname} (seat_number, seat_type, booked, passenger_name, passenger_age, passenger_gender) VALUES (?,?,?,?,?,?)",
            rows
        )
        conn.commit()

def add_train(train_number, train_name, departure_date, starting_destination, ending_destination):
    departure_text = to_date_text(departure_date)
    c.execute("INSERT INTO trains (train_number, train_name, departure_date, starting_destination, ending_destination) VALUES (?, ?, ?, ?, ?)",
              (train_number, train_name, departure_text, starting_destination, ending_destination))
    conn.commit()
    create_seat_table(train_number)

def delete_train(train_number, departure_date):
    departure_text = to_date_text(departure_date)
    train_query = c.execute(
        "SELECT * FROM trains WHERE train_number = ? AND departure_date = ?",
        (train_number, departure_text))
    train_data = train_query.fetchone()
    if train_data:
        c.execute("DELETE FROM trains WHERE train_number = ? AND departure_date = ?",
                  (train_number, departure_text))
        tname = "".join(ch for ch in train_number if ch.isalnum() or ch in ("_", "-"))
        c.execute(f"DROP TABLE IF EXISTS seats_{tname}")
        conn.commit()
        st.success(f"✅ Train {train_number} on {departure_text} has been deleted.")
    else:
        st.error(f"❌ No such Train {train_number} on {departure_text}.")

def allocate_next_available_seat(train_number, seat_type):
    tname = "".join(ch for ch in train_number if ch.isalnum() or ch in ("_", "-"))
    try:
        seat_query = c.execute(
            f"SELECT seat_number FROM seats_{tname} WHERE booked=0 AND seat_type=? ORDER BY seat_number ASC",
            (seat_type,))
        result = seat_query.fetchone()
        if result:
            return result[0]
    except sqlite3.OperationalError:
        return None
    return None

def book_ticket(train_number, passenger_name, passenger_age, passenger_gender, seat_type):
    train_query = c.execute(
        "SELECT * FROM trains WHERE train_number = ?", (train_number,))
    train_data = train_query.fetchone()
    if not train_data:
        st.error(f"❌ No such Train with Number {train_number}.")
        return
    seat_number = allocate_next_available_seat(train_number, seat_type)
    if seat_number:
        tname = "".join(ch for ch in train_number if ch.isalnum() or ch in ("_", "-"))
        c.execute(
            f"UPDATE seats_{tname} SET booked=1, seat_type=?, passenger_name=?, passenger_age=?, passenger_gender=? WHERE seat_number=?",
            (seat_type, passenger_name, int(passenger_age), passenger_gender, seat_number)
        )
        conn.commit()
        st.success(f"🎉 Successfully booked seat {seat_number} ({seat_type}) for **{passenger_name}**.")
        st.balloons()
    else:
        st.error("😞 No available seats of this type in this train.")

def cancel_tickets(train_number, seat_number):
    train_query = c.execute(
        "SELECT * FROM trains WHERE train_number = ?", (train_number,))
    train_data = train_query.fetchone()
    if train_data:
        tname = "".join(ch for ch in train_number if ch.isalnum() or ch in ("_", "-"))
        c.execute(
            f"UPDATE seats_{tname} SET booked=0, passenger_name='', passenger_age=NULL, passenger_gender='' WHERE seat_number=?",
            (int(seat_number),)
        )
        conn.commit()
        st.success(f"✅ Seat {seat_number} on Train {train_number} is now **cancelled & available**.")
    else:
        st.error(f"❌ No such Train with Number {train_number}.")

def view_seats_df(train_number):
    tname = "".join(ch for ch in train_number if ch.isalnum() or ch in ("_", "-"))
    try:
        seat_query = c.execute(
            f"SELECT seat_number AS Seat, seat_type AS Type, booked AS Booked, passenger_name AS Name, passenger_age AS Age, passenger_gender AS Gender FROM seats_{tname} ORDER BY seat_number ASC")
        rows = seat_query.fetchall()
        df = pd.DataFrame(rows, columns=["Seat", "Type", "Booked", "Name", "Age", "Gender"])
        df["Booked"] = df["Booked"].map({0: "No", 1: "Yes"})
        return df
    except sqlite3.OperationalError:
        st.error("⚠️ Seat table not found. Make sure the train exists and seats are initialized.")
        return pd.DataFrame()

# ======================
# Email (SMTP) Utilities
# ======================
def smtp_configured():
    return "smtp" in st.secrets and all(k in st.secrets["smtp"] for k in ("host","port","user","password","sender"))

def send_email(to_email: str, subject: str, body: str) -> bool:
    if not smtp_configured():
        return False
    try:
        cfg = st.secrets["smtp"]
        host = cfg["host"]
        port = int(cfg["port"])
        user = cfg["user"]
        password = cfg["password"]
        sender = cfg["sender"]
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        msg.set_content(body)
        server = smtplib.SMTP(host, port, timeout=10)
        server.starttls()
        server.login(user, password)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Email sending failed: {e}")
        return False

def generate_and_store_code(username: str, purpose: str, ttl_minutes: int = 15) -> str:
    code = f"{random.randint(100000, 999999)}"
    expiry = int((datetime.utcnow() + timedelta(minutes=ttl_minutes)).timestamp())
    c.execute("INSERT INTO email_codes (username, code, purpose, expiry_ts) VALUES (?, ?, ?, ?)",
              (username, code, purpose, expiry))
    conn.commit()
    return code

def verify_code(username: str, code: str, purpose: str) -> bool:
    now_ts = int(datetime.utcnow().timestamp())
    cur = c.execute("SELECT code, expiry_ts FROM email_codes WHERE username=? AND purpose=? ORDER BY expiry_ts DESC LIMIT 1",
                    (username, purpose))
    row = cur.fetchone()
    if not row:
        return False
    stored_code, expiry_ts = row
    if now_ts > expiry_ts:
        return False
    return secrets.compare_digest(stored_code, code)

def clear_codes(username: str, purpose: str):
    c.execute("DELETE FROM email_codes WHERE username=? AND purpose=?", (username, purpose))
    conn.commit()

# ======================
# Auth state
# ======================
if "auth" not in st.session_state:
    st.session_state.auth = {"logged_in": False, "username": None, "role": "User"}

# ======================
# First-run admin creation (if no admin exists)
# ======================
c.execute("SELECT * FROM employees WHERE designation='Admin'")
admin_exists = c.fetchone() is not None

if not admin_exists:
    st.info("⚠️ No Admin account found. Create the first Admin account.")
    with st.form("first_admin_form"):
        fa_user = st.text_input("Admin Username", key="fa_user")
        fa_pass = st.text_input("Admin Password", type="password", key="fa_pass")
        fa_email = st.text_input("Admin Email (for verification & password resets)", key="fa_email")
        fa_submit = st.form_submit_button("Create Admin Account")
    if fa_submit:
        if fa_user and fa_pass and fa_email:
            hashed = hash_password(fa_pass)
            try:
                c.execute("INSERT INTO users (username, password, email, email_verified) VALUES (?, ?, ?, ?)", (fa_user, hashed, fa_email, 1))
            except sqlite3.IntegrityError:
                st.error("Username already exists in users. Choose another username.")
            else:
                c.execute("INSERT INTO employees (employee_id, password, designation) VALUES (?, ?, ?)",
                          (fa_user, hashed, "Admin"))
                conn.commit()
                st.success(f"✅ Admin account '{fa_user}' created. Please login below.")
                # update query params to trigger a reload (safe method)
                st.session_state['refresh'] = int(time.time())
                st.query_params.update({"_r": st.session_state['refresh']})
    st.stop()

# ======================
# Auth helper functions (signup/login/password reset)
# ======================
def signup_user_with_email(username: str, password: str, email: str) -> (bool, str):
    if not username or not password or not email:
        return False, "Username, password and email are required."
    cur = c.execute("SELECT username FROM users WHERE username=?", (username,))
    if cur.fetchone():
        return False, "Username already exists."
    hashed = hash_password(password)
    c.execute("INSERT INTO users (username, password, email, email_verified) VALUES (?, ?, ?, ?)", (username, hashed, email, 0))
    conn.commit()
    code = generate_and_store_code(username, "email_verification", ttl_minutes=30)
    if smtp_configured():
        subject = "Verify your ERailTicket account"
        body = f"Hello {username},\n\nYour verification code is: {code}\nIt expires in 30 minutes."
        ok = send_email(email, subject, body)
        if ok:
            return True, "Account created. Verification code sent to email."
        else:
            return True, "Account created but failed to send verification email (check SMTP settings)."
    else:
        # show code in UI if no SMTP configured (for development)
        return True, f"Account created. Verification code (dev): {code}"

def login_user(identifier: str, password: str):
    cur = c.execute("SELECT username, password, email_verified FROM users WHERE username=? OR email=?", (identifier, identifier))
    row = cur.fetchone()
    if not row:
        return False, "Invalid username or password.", None
    real_username, stored_hash, email_verified = row
    if not verify_password(stored_hash, password):
        return False, "Invalid username or password.", None
    if email_verified == 0:
        return False, "Email not verified. Please verify your email before logging in.", None
    cur2 = c.execute("SELECT designation FROM employees WHERE employee_id=?", (real_username,))
    erow = cur2.fetchone()
    if erow and erow[0] == "Admin":
        return True, "Admin", real_username
    return True, "User", real_username

def request_password_reset(username_or_email: str):
    cur = c.execute("SELECT username, email FROM users WHERE username=? OR email=?", (username_or_email, username_or_email))
    row = cur.fetchone()
    if not row:
        return False, "No account found with that username/email."
    username, email = row
    code = generate_and_store_code(username, "password_reset", ttl_minutes=15)
    if smtp_configured():
        subject = "ERailTicket password reset code"
        body = f"Hello {username},\n\nYour password reset code is: {code}\nIt expires in 15 minutes."
        ok = send_email(email, subject, body)
        if ok:
            return True, f"Password reset code sent to {email}."
        else:
            return False, "Failed to send email (check SMTP settings)."
    else:
        return True, f"Password reset code (dev): {code}"

def perform_password_reset(username: str, code: str, new_password: str):
    if not verify_code(username, code, "password_reset"):
        return False, "Invalid or expired code."
    hashed = hash_password(new_password)
    c.execute("UPDATE users SET password=? WHERE username=?", (hashed, username))
    conn.commit()
    clear_codes(username, "password_reset")
    cur = c.execute("SELECT * FROM employees WHERE employee_id=?", (username,))
    if cur.fetchone():
        c.execute("UPDATE employees SET password=? WHERE employee_id=?", (hashed, username))
        conn.commit()
    return True, "Password updated successfully."

def verify_email_code(username: str, code: str):
    if verify_code(username, code, "email_verification"):
        c.execute("UPDATE users SET email_verified=1 WHERE username=?", (username,))
        conn.commit()
        clear_codes(username, "email_verification")
        return True
    return False

# ======================
# Show auth screens if not logged in (tabs)
# ======================
if not st.session_state.auth["logged_in"]:
    auth_tabs = st.tabs(["🔐 Login", "✍️ Sign Up", "✅ Verify", "🔁 Forgot Password"])
    # Login
    with auth_tabs[0]:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("### 🔐 Login")
        with st.form("login_form"):
            login_identifier = st.text_input("Username or Email", key="login_user")
            login_password = st.text_input("Password", type="password", key="login_pass")
            login_btn = st.form_submit_button("Login")
        if login_btn:
            ok, role_or_msg, real_username = login_user(login_identifier, login_password)
            if ok:
                st.session_state.auth = {"logged_in": True, "username": real_username, "role": role_or_msg}
                st.success("✅ Logged in successfully.")
                # update query params to trigger reload
                st.session_state['refresh'] = int(time.time())
                st.query_params.update({"_r": st.session_state['refresh']})
            else:
                st.error(role_or_msg)
        st.markdown("</div>", unsafe_allow_html=True)

    # Sign Up
    with auth_tabs[1]:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("### ✍️ Sign Up")
        with st.form("signup_form"):
            s_user = st.text_input("New Username", key="su_user")
            s_pass = st.text_input("New Password", type="password", key="su_pass")
            s_email = st.text_input("Email (used for verification & reset)", key="su_email")
            create_btn = st.form_submit_button("Create Account")
        if create_btn:
            ok, msg = signup_user_with_email(s_user, s_pass, s_email)
            if ok:
                st.success("✅ " + msg)
                st.info("Check email for verification code (or use admin/DB to verify).")
            else:
                st.error("❌ " + msg)
        st.markdown("</div>", unsafe_allow_html=True)

    # Verify
    with auth_tabs[2]:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("### ✅ Verify Email")
        with st.form("verify_form"):
            v_user = st.text_input("Username to verify", key="v_user")
            v_code = st.text_input("Verification Code", key="v_code")
            v_btn = st.form_submit_button("Verify Email")
        if v_btn:
            if v_user and v_code:
                ok = verify_email_code(v_user, v_code)
                if ok:
                    st.success("✅ Email verified — you can now log in.")
                else:
                    st.error("❌ Invalid or expired code.")
            else:
                st.error("Enter username and code.")
        st.markdown("</div>", unsafe_allow_html=True)

    # Forgot Password
    with auth_tabs[3]:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("### 🔁 Forgot Password")
        with st.form("forgot_form"):
            forgot_input = st.text_input("Enter your username or email", key="forgot_input")
            forgot_btn = st.form_submit_button("Send reset code")
        if forgot_btn:
            if forgot_input:
                ok, msg = request_password_reset(forgot_input)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.error("Enter username or email.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.stop()

# =================
# Main App - Tabs
# =================
role = st.session_state.auth["role"]
is_admin = role == "Admin"

# Ordered tabs: Admin tabs (if admin) then user tabs
base_tabs = ["🏠 Home", "🎫 Book Ticket", "❌ Cancel Ticket", "🔍 Search Trains", "🚆 View Trains", "🪑 View Seats", "🔑 Reset Password"]
if is_admin:
    tabs = ["➕ Add Train", "📋 View Trains (Admin)", "❌ Delete Train", "🛠️ Admin Panel"] + base_tabs
else:
    tabs = base_tabs

tab_objs = st.tabs(tabs)

# build mapping to use safe indexing
tab_map = {name: tab_objs[i] for i, name in enumerate(tabs)}

# ----------------
# Admin tabs
# ----------------
if is_admin:
    with tab_map["➕ Add Train"]:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("### ➕ Add New Train")
        with st.form("new_train_details"):
            c1, c2 = st.columns(2)
            with c1:
                train_number = st.text_input("Train Number")
                departure_date = st.date_input("Date of Departure", value=date.today())
                starting_destination = st.text_input("Starting Destination")
            with c2:
                train_name = st.text_input("Train Name")
                ending_destination = st.text_input("Ending Destination")
            submitted = st.form_submit_button("✅ Add Train")
        if submitted:
            if all([train_number, train_name, starting_destination, ending_destination]):
                try:
                    add_train(train_number, train_name, departure_date, starting_destination, ending_destination)
                    st.success("✅ Train Added Successfully!")
                    st.balloons()
                except sqlite3.IntegrityError as e:
                    st.error(f"⚠️ Could not add train: {e}")
            else:
                st.error("Please fill all required fields.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_map["📋 View Trains (Admin)"]:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("### 📋 All Trains (Admin)")
        train_query = c.execute("SELECT * FROM trains ORDER BY departure_date ASC, train_number ASC")
        trains = train_query.fetchall()
        if trains:
            df = pd.DataFrame(trains, columns=["Train Number", "Train Name", "Departure Date", "From", "To"])
            st.dataframe(df, use_container_width=True)
        else:
            st.info("No trains available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_map["❌ Delete Train"]:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("### ❌ Delete Train")
        with st.form("delete_form"):
            tcol1, tcol2 = st.columns(2)
            with tcol1:
                del_train_number = st.text_input("Train Number to delete")
            with tcol2:
                del_departure_date = st.date_input("Departure Date", value=date.today(), key="del_date")
            del_btn = st.form_submit_button("🗑️ Delete Train")
        if del_btn:
            if del_train_number:
                delete_train(del_train_number, del_departure_date)
            else:
                st.error("Enter a train number.")
        st.markdown("</div>", unsafe_allow_html=True)

    with tab_map["🛠️ Admin Panel"]:
        st.markdown("<div class='app-card'>", unsafe_allow_html=True)
        st.markdown("### 🛠️ Admin Panel")
        st.info("Create additional Admin user (only admins can do this).")
        with st.form("create_admin_form"):
            a_user = st.text_input("New Admin Username")
            a_pass = st.text_input("New Admin Password", type="password")
            a_email = st.text_input("Admin Email", key="a_email")
            create_admin_btn = st.form_submit_button("Create Admin")
        if create_admin_btn:
            if a_user and a_pass and a_email:
                cur = c.execute("SELECT username FROM users WHERE username=?", (a_user,))
                if cur.fetchone():
                    st.error("User already exists. Choose different username.")
                else:
                    hashed = hash_password(a_pass)
                    c.execute("INSERT INTO users (username, password, email, email_verified) VALUES (?, ?, ?, ?)", (a_user, hashed, a_email, 1))
                    c.execute("INSERT INTO employees (employee_id, password, designation) VALUES (?, ?, ?)",
                              (a_user, hashed, "Admin"))
                    conn.commit()
                    st.success(f"✅ Admin '{a_user}' created.")
            else:
                st.error("Enter username, password and email.")
        st.markdown("</div>", unsafe_allow_html=True)

# ----------------
# Base tabs (for all users)
# ----------------
with tab_map["🏠 Home"]:
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)

    c1, c2 = st.columns([1.2, 1])

    # ---- LEFT: Text content ----
    with c1:
        st.markdown("### 🏠 Dashboard")
        st.markdown(
            """
            Welcome to **ERailTicket**, your smart companion for hassle-free railway
            reservations.

            - Search and compare trains across routes  
            - Reserve seats with preference-based allocation  
            - Manage bookings and cancellations in a few clicks  
            - Admins can efficiently manage trains and seat layouts  
            """
        )

        st.info(
            "💡 Tip: Use the **Book Ticket** tab to reserve seats or **Search Trains** to "
            "plan your next journey."
        )

    # ---- RIGHT: Live hero image ----
    with c2:
        try:
            hero_img = Image.open("hero_train.jpg")   # put this image next to app.py
            st.image(
                hero_img,
                caption="Plan, book, and manage journeys with ERailTicket.",
                use_container_width=True,
            )
        except Exception:
            st.markdown(
                "<p style='color: grey; font-size: 13px;'>"
                "Add <code>hero_train.jpg</code> in the project root (same folder as <code>app.py</code>) "
                "to display the dashboard banner image."
                "</p>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ---- Quick actions section ----
    st.markdown("#### 🚉 Quick actions")
    ca1, ca2, ca3 = st.columns(3)

    with ca1:
        st.markdown(
            """
            **🎫 Book Ticket**  
            Configure passenger details, seat type, and confirm reservations instantly.
            """
        )

    with ca2:
        st.markdown(
            """
            **🔍 Search Trains**  
            Look up trains by **number** or **origin–destination–date** before booking.
            """
        )

    with ca3:
        st.markdown(
            """
            **🪑 View Seats**  
            Inspect the live seat map to see which seats are booked or available.
            """
        )

    st.markdown("</div>", unsafe_allow_html=True)



with tab_map["🎫 Book Ticket"]:
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown("### 🎫 Book Ticket")
    with st.form("booking_form", clear_on_submit=False):
        bcol1, bcol2, bcol3 = st.columns(3)
        with bcol1:
            b_train_no = st.text_input("Train Number")
            b_seat_type = st.selectbox("Seat Type", ["Aisle", "Middle", "Window"], index=0)
        with bcol2:
            b_name = st.text_input("Passenger Name")
            b_age = st.number_input("Age", min_value=1, max_value=120, value=25)
        with bcol3:
            b_gender = st.selectbox("Gender", ["Male", "Female", "Other"])
        book_btn = st.form_submit_button("✅ Confirm Booking")
    if book_btn:
        if b_train_no and b_name:
            book_ticket(b_train_no, b_name, b_age, b_gender, b_seat_type)
        else:
            st.error("Please enter Train Number and Passenger Name.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab_map["❌ Cancel Ticket"]:
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown("### ❌ Cancel Ticket")
    with st.form("cancel_form"):
        ccol1, ccol2 = st.columns(2)
        with ccol1:
            c_train_no = st.text_input("Train Number")
        with ccol2:
            c_seat_no = st.number_input("Seat Number", min_value=1, max_value=50, value=1, step=1)
        cancel_btn = st.form_submit_button("❌ Cancel Seat")
    if cancel_btn:
        if c_train_no and c_seat_no:
            cancel_tickets(c_train_no, c_seat_no)
        else:
            st.error("Enter Train Number and Seat Number.")
    st.markdown("</div>", unsafe_allow_html=True)
    
    # ======================
# Train Search Utilities  (ADD THIS)
# ======================

def search_train_by_train_number(train_no: str):
    cur = c.execute(
        "SELECT train_number, train_name, departure_date, starting_destination, ending_destination "
        "FROM trains WHERE train_number LIKE ?",
        (f"%{train_no}%",)
    )
    return cur.fetchall()


def search_trains_by_destinations(src: str, dest: str, dep_date=None):
    if dep_date:
        cur = c.execute(
            "SELECT train_number, train_name, departure_date, starting_destination, ending_destination "
            "FROM trains WHERE starting_destination LIKE ? AND ending_destination LIKE ? AND departure_date=?",
            (f"%{src}%", f"%{dest}%", dep_date.isoformat())
        )
    else:
        cur = c.execute(
            "SELECT train_number, train_name, departure_date, starting_destination, ending_destination "
            "FROM trains WHERE starting_destination LIKE ? AND ending_destination LIKE ?",
            (f"%{src}%", f"%{dest}%")
        )
    return cur.fetchall()


with tab_map["🔍 Search Trains"]:
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown("### 🔍 Search Trains")
    with st.form("search_train_form"):
        s1, s2, s3 = st.columns([1,1,1])
        with s1:
            search_train_no = st.text_input("Train Number (optional)")
        with s2:
            s_from = st.text_input("From (optional)")
        with s3:
            s_to = st.text_input("To (optional)")
        s_date = st.date_input("Departure Date (optional)", value=None)
        search_btn = st.form_submit_button("🔎 Search")
    if search_btn:
        results = []
        if search_train_no:
            results = search_train_by_train_number(search_train_no)
        elif s_from and s_to:
            results = search_trains_by_destinations(s_from, s_to, s_date if s_date is not None else None)
        if results:
            df = pd.DataFrame(results, columns=["Train Number", "Train Name", "Departure Date", "From", "To"])
            st.dataframe(df, use_container_width=True)
        else:
            st.warning("No trains found with given criteria.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab_map["🚆 View Trains"]:
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown("### 🚆 View Trains")
    train_query = c.execute("SELECT * FROM trains ORDER BY departure_date ASC, train_number ASC")
    trains = train_query.fetchall()
    if trains:
        df = pd.DataFrame(trains, columns=["Train Number", "Train Name", "Departure Date", "From", "To"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No trains available.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab_map["🪑 View Seats"]:
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown("### 🪑 View Seats")
    with st.form("view_seats_form"):
        v_train_no = st.text_input("Train Number")
        v_btn = st.form_submit_button("📋 Show Seats")
    if v_btn:
        if v_train_no:
            df = view_seats_df(v_train_no)
            if not df.empty:
                st.dataframe(df, use_container_width=True, height=520)
        else:
            st.error("Enter a Train Number.")
    st.markdown("</div>", unsafe_allow_html=True)

with tab_map["🔑 Reset Password"]:
    st.markdown("<div class='app-card'>", unsafe_allow_html=True)
    st.markdown("### 🔑 Reset Password")
    with st.form("reset_password_form"):
        rp_user = st.text_input("Username or Email", key="rp_user")
        rp_code = st.text_input("Reset Code", key="rp_code")
        rp_new_pass = st.text_input("New Password", type="password", key="rp_new_pass")
        rp_confirm_pass = st.text_input("Confirm Password", type="password", key="rp_confirm_pass")
        rp_btn = st.form_submit_button("Reset Password")
    if rp_btn:
        if not (rp_user and rp_code and rp_new_pass and rp_confirm_pass):
            st.error("Fill all fields.")
        elif rp_new_pass != rp_confirm_pass:
            st.error("Passwords do not match.")
        else:
            # if user entered email, resolve to username
            if "@" in rp_user:
                cur = c.execute("SELECT username FROM users WHERE email=?", (rp_user,))
                row = cur.fetchone()
                if row:
                    rp_user_resolved = row[0]
                else:
                    rp_user_resolved = rp_user
            else:
                rp_user_resolved = rp_user
            ok, msg = perform_password_reset(rp_user_resolved, rp_code, rp_new_pass)
            if ok:
                st.success("✅ " + msg)
            else:
                st.error("❌ " + msg)
    st.markdown("</div>", unsafe_allow_html=True)

# Footer / notes
st.markdown("---")
st.caption("Theme: IRCTC-inspired. Email features require SMTP in Streamlit secrets (see sidebar note).")

# (do not close DB connection for app lifetime)

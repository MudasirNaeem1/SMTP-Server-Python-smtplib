from flask import Flask, render_template, request, redirect, session, flash, url_for
import sqlite3
import smtplib
from email.message import EmailMessage
import re
import os

app = Flask(__name__)
app.secret_key = "secretkey"

DB_PATH = "inbox.db"


# ─── Create DB if not exists ───────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        first_name TEXT,
        last_name TEXT,
        email TEXT UNIQUE,
        password TEXT
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS inbox (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        recipient TEXT,
        subject TEXT,
        body TEXT,
        is_important BOOLEAN DEFAULT 0 
    )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS sent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender TEXT,
        receiver TEXT,
        subject TEXT,
        body TEXT
    )"""
    )
    conn.commit()
    conn.close()


init_db()


# ─── Database Connection Function ───────────────────────────────────────────
def get_db_connection():
    conn = sqlite3.connect(
        DB_PATH, check_same_thread=False
    )  # Allowing multiple threads to access the DB
    return conn


# ─── Email Validation ──────────────────────────────────────────────────────
def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.(com|pk)$", email)


# ─── Routes ────────────────────────────────────────────────────────────────


@app.route("/")
def index():
    return redirect("/login")


# ─── Signup ────────────────────────────────────────────────────────────────
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        fname = request.form["fname"]
        lname = request.form["lname"]
        email = request.form["email"]
        password = request.form["password"]

        if not is_valid_email(email):
            flash("Invalid email format! Must contain @ and end with .com or .pk")
            return redirect("/signup")

        conn = get_db_connection()
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (first_name, last_name, email, password) VALUES (?, ?, ?, ?)",
                (fname, lname, email, password),
            )
            conn.commit()
            session["email"] = email
            return redirect("/home")
        except sqlite3.IntegrityError:
            flash("Email already registered.")
            return redirect("/signup")
        finally:
            conn.close()

    return render_template("signup.html")


# ─── Login ─────────────────────────────────────────────────────────────────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
        user = c.fetchone()
        conn.close()

        if user:
            session["email"] = email
            return redirect("/home")
        else:
            flash("Incorrect Gmail or password")
            return redirect("/login")

    return render_template("login.html")


# ─── Home ──────────────────────────────────────────────────────────────────
@app.route("/home")
def home():
    if "email" not in session:
        return redirect("/login")

    # Retrieve important emails
    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, sender, subject, body FROM inbox WHERE recipient=? AND is_important=1",
        (session["email"],),
    )
    important_mails = c.fetchall()

    return render_template("home.html", important_mails=important_mails)


# ─── Compose ───────────────────────────────────────────────────────────────
@app.route("/compose", methods=["GET", "POST"])
def compose():
    if "email" not in session:
        return redirect("/login")

    if request.method == "POST":
        receiver = request.form["to"]
        subject = request.form["subject"]
        body = request.form["body"]
        sender = session["email"]

        # Send using SMTP
        msg = EmailMessage()
        msg["From"] = sender
        msg["To"] = receiver
        msg["Subject"] = subject
        msg.set_content(body)

        try:
            with smtplib.SMTP("localhost", 1025) as smtp:
                smtp.send_message(msg)

            # Save to sent table
            conn = get_db_connection()
            c = conn.cursor()
            c.execute(
                "INSERT INTO sent (sender, receiver, subject, body) VALUES (?, ?, ?, ?)",
                (sender, receiver, subject, body),
            )
            conn.commit()
            conn.close()

            flash("Email sent successfully.")
            return redirect("/compose")
        except Exception as e:
            flash(f"Error sending email: {e}")
            return redirect("/compose")

    return render_template("compose.html")


# ─── Inbox ─────────────────────────────────────────────────────────────────
@app.route("/inbox")
def inbox():
    if "email" not in session:
        return redirect("/login")

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, sender, subject, body FROM inbox WHERE recipient=?",
        (session["email"],),
    )
    mails = c.fetchall()
    conn.close()
    return render_template("inbox.html", mails=mails)


# ─── Sent ──────────────────────────────────────────────────────────────────
@app.route("/sent")
def sent():
    if "email" not in session:
        return redirect("/login")

    conn = get_db_connection()
    c = conn.cursor()
    c.execute(
        "SELECT id, receiver, subject, body FROM sent WHERE sender=?",
        (session["email"],),
    )
    mails = c.fetchall()
    conn.close()
    return render_template("sent.html", mails=mails)


@app.route("/delete_inbox_email/<int:id>", methods=["POST"])
def delete_inbox_email(id):
    if "email" not in session:
        return redirect("/login")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM inbox WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Inbox email deleted successfully.")
    return redirect("/inbox")


@app.route("/delete_sent_email/<int:id>", methods=["POST"])
def delete_sent_email(id):
    if "email" not in session:
        return redirect("/login")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM sent WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Sent email deleted successfully.")
    return redirect("/sent")


@app.route("/reply", methods=["POST"])
def reply_email():
    if "email" not in session:
        return redirect("/login")

    sender = session["email"]
    receiver = request.form["to"]
    subject = request.form["subject"]
    body = request.form["body"]

    # Send using SMTP
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = receiver
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP("localhost", 1025) as smtp:
            smtp.send_message(msg)

        # Save to sent table
        conn = get_db_connection()
        c = conn.cursor()
        c.execute(
            "INSERT INTO sent (sender, receiver, subject, body) VALUES (?, ?, ?, ?)",
            (sender, receiver, subject, body),
        )
        conn.commit()
        conn.close()

        flash("Reply sent successfully.")
        return redirect("/inbox")
    except Exception as e:
        flash(f"Error sending reply: {e}")
        return redirect("/inbox")


@app.route("/mark_important/<int:id>", methods=["POST"])
def mark_important(id):
    if "email" not in session:
        return redirect("/login")
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE inbox SET is_important = 1 WHERE id=?", (id,))
    conn.commit()
    conn.close()
    flash("Email marked as important.")
    return redirect("/inbox")


# ─── Logout ────────────────────────────────────────────────────────────────
@app.route("/logout")
def logout():
    session.pop("email", None)
    return redirect("/login")


# ─── Run ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True)

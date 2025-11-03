import os
import smtplib
from email.message import EmailMessage


def send_email(to_email: str, subject: str, body_text: str) -> None:
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM", user or "no-reply@example.com")

    if not host or not user or not password:
        # Fallback: log to console if SMTP not configured
        print(f"[EMAIL_FALLBACK] To: {to_email}\nSubject: {subject}\n\n{body_text}")
        return

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)

    with smtplib.SMTP(host, port) as server:
        server.starttls()
        server.login(user, password)
        server.send_message(msg)



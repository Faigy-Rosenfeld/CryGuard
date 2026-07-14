import smtplib
from email.message import EmailMessage


def build_notification_body(label: str, phone: str | None = None) -> str:
    body = {"crying": "👶 התרעה: התינוק בוכה!"}.get(label, "🚨 התרעת CRYGUARD")
    if phone:
        body = f"{body}\n\nPhone: {phone}"
    return body


def send_email_notification(
    body: str,
    smtp_host: str | None,
    smtp_port: int,
    smtp_user: str | None,
    smtp_password: str | None,
    recipient: str | None,
) -> None:
    if not smtp_host or not smtp_user or not smtp_password or not recipient:
        raise RuntimeError("SMTP not configured")

    msg = EmailMessage()
    msg["Subject"] = "CryGuard alert"
    msg["From"] = smtp_user
    msg["To"] = recipient
    msg.set_content(body)

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)

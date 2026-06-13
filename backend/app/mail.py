import smtplib
from email.message import EmailMessage

from app.config import FRONTEND_URL, SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME, SMTP_USE_TLS


def build_password_reset_link(token: str) -> str:
    return f"{FRONTEND_URL}/?resetToken={token}"


def send_password_reset_email(email: str, token: str) -> None:
    if not SMTP_HOST:
        return

    message = EmailMessage()
    message["From"] = SMTP_FROM
    message["To"] = email
    message["Subject"] = "Reset your UmojaFunds password"
    message.set_content(
        "\n".join(
            [
                "A password reset was requested for your UmojaFunds account.",
                "",
                "Open this link to choose a new password:",
                build_password_reset_link(token),
                "",
                "This link expires soon and can only be used once.",
                "If you did not request this, ignore this email.",
            ]
        )
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        if SMTP_USE_TLS:
            smtp.starttls()
        if SMTP_USERNAME:
            smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
        smtp.send_message(message)

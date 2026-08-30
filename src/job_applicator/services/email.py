from email.message import EmailMessage

from aiosmtplib import send

from job_applicator.config import config


async def send_otp(to_email: str, otp: str) -> None:
    msg = EmailMessage()
    msg["From"] = config.smtp_from
    msg["To"] = to_email
    msg["Subject"] = "ApplyBot — your OTP"
    msg.set_content(f"Your verification code: {otp}")

    await send(
        msg,
        hostname=config.smtp_host,
        port=config.smtp_port,
        username=config.smtp_user,
        password=config.smtp_pass,
        start_tls=True,
    )

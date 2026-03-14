"""
Email service — welcome emails and OTP emails via Gmail SMTP.
Uses fastapi-mail with settings from config.
The mailer is lazy-initialized so the app starts even without email credentials.
"""

import logging
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType

from app.core.config import settings

logger = logging.getLogger(__name__)

_mailer: FastMail | None = None


def _get_mailer() -> FastMail | None:
    """Return a configured FastMail instance, or None if credentials are missing."""
    global _mailer
    if _mailer is not None:
        return _mailer

    if not settings.MAIL_USERNAME or not settings.MAIL_PASSWORD:
        logger.warning(
            "Email credentials not configured (MAIL_USERNAME / MAIL_PASSWORD). "
            "Emails will be skipped."
        )
        return None

    mail_from = settings.MAIL_FROM if settings.MAIL_FROM else settings.MAIL_USERNAME
    config = ConnectionConfig(
        MAIL_USERNAME=settings.MAIL_USERNAME,
        MAIL_PASSWORD=settings.MAIL_PASSWORD,
        MAIL_FROM=mail_from,
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
        MAIL_PORT=587,
        MAIL_SERVER="smtp.gmail.com",
        MAIL_STARTTLS=True,
        MAIL_SSL_TLS=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )
    _mailer = FastMail(config)
    return _mailer


async def send_welcome_email(to_email: str, full_name: str) -> None:
    """Send a welcome email to a newly registered user."""
    mailer = _get_mailer()
    if mailer is None:
        return

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <style>
        body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 40px auto; background: #fff;
                      border-radius: 8px; overflow: hidden;
                      box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .header {{ background: #1a56db; color: #fff; padding: 32px 40px; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .body {{ padding: 32px 40px; color: #333; }}
        .body p {{ line-height: 1.6; }}
        .highlight {{ background: #f0f5ff; border-left: 4px solid #1a56db;
                      padding: 12px 16px; border-radius: 4px; margin: 20px 0; }}
        .footer {{ background: #f8f8f8; padding: 20px 40px;
                   color: #888; font-size: 13px; text-align: center; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>Welcome to CoreInventory</h1>
        </div>
        <div class="body">
          <p>Hi <strong>{full_name}</strong>,</p>
          <p>Your account has been created successfully. You now have access to
             the CoreInventory platform.</p>
          <div class="highlight">
            <strong>What you can do:</strong><br>
            Manage warehouses, track stock movements, validate receipts and
            deliveries, and monitor inventory levels in real time.
          </div>
          <p>Log in using your username and password at any time. If you need
             help, contact your system administrator.</p>
          <p>Welcome aboard!</p>
        </div>
        <div class="footer">CoreInventory &mdash; Production-grade Inventory Management</div>
      </div>
    </body>
    </html>
    """
    message = MessageSchema(
        subject="Welcome to CoreInventory",
        recipients=[to_email],
        body=html,
        subtype=MessageType.html,
    )
    await mailer.send_message(message)


async def send_otp_email(to_email: str, full_name: str, otp_code: str) -> None:
    """Send a password-reset OTP code to the user."""
    mailer = _get_mailer()
    if mailer is None:
        return

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="UTF-8">
      <style>
        body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 0; }}
        .container {{ max-width: 600px; margin: 40px auto; background: #fff;
                      border-radius: 8px; overflow: hidden;
                      box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .header {{ background: #1a56db; color: #fff; padding: 32px 40px; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .body {{ padding: 32px 40px; color: #333; }}
        .body p {{ line-height: 1.6; }}
        .otp-box {{ background: #f0f5ff; border: 2px dashed #1a56db;
                    border-radius: 8px; text-align: center;
                    padding: 24px; margin: 24px 0; }}
        .otp-code {{ font-size: 42px; font-weight: bold; letter-spacing: 12px;
                     color: #1a56db; }}
        .warning {{ background: #fff8e1; border-left: 4px solid #f59e0b;
                    padding: 12px 16px; border-radius: 4px;
                    color: #78350f; font-size: 14px; }}
        .footer {{ background: #f8f8f8; padding: 20px 40px;
                   color: #888; font-size: 13px; text-align: center; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="header">
          <h1>Password Reset Request</h1>
        </div>
        <div class="body">
          <p>Hi <strong>{full_name}</strong>,</p>
          <p>We received a request to reset your CoreInventory password.
             Use the code below to complete the reset:</p>
          <div class="otp-box">
            <div class="otp-code">{otp_code}</div>
            <p style="margin:8px 0 0; color:#555; font-size:14px;">
              Valid for <strong>10 minutes</strong>
            </p>
          </div>
          <div class="warning">
            If you did not request a password reset, please ignore this email.
            Your password will not be changed.
          </div>
          <p>For security reasons, this code can only be used once.</p>
        </div>
        <div class="footer">CoreInventory &mdash; Production-grade Inventory Management</div>
      </div>
    </body>
    </html>
    """
    message = MessageSchema(
        subject="Your CoreInventory Password Reset Code",
        recipients=[to_email],
        body=html,
        subtype=MessageType.html,
    )
    await mailer.send_message(message)

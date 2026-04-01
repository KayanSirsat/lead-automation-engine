"""
Email sender module supporting both SMTP and SendGrid.

Reads configuration from environment variables:
- EMAIL_PROVIDER: "smtp" (default) or "sendgrid"
- SMTP: SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL
- SendGrid: SENDGRID_API_KEY, SENDGRID_FROM_EMAIL
"""

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_name: str | None = None,
) -> bool:
    """
    Send an email via SMTP or SendGrid based on EMAIL_PROVIDER env variable.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        body: Plain text email body.
        from_name: Optional sender name (e.g., "LeadFlow Team").

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    provider = os.environ.get("EMAIL_PROVIDER", "smtp").strip().lower()

    if provider == "sendgrid":
        return _send_via_sendgrid(to_email, subject, body, from_name)
    else:
        return _send_via_smtp(to_email, subject, body, from_name)


def _send_via_smtp(
    to_email: str,
    subject: str,
    body: str,
    from_name: str | None = None,
) -> bool:
    """Send email using SMTP (e.g., Gmail, Outlook)."""
    smtp_host = os.environ.get("SMTP_HOST", "").strip()
    smtp_port_str = os.environ.get("SMTP_PORT", "587").strip()
    smtp_username = os.environ.get("SMTP_USERNAME", "").strip()
    smtp_password = os.environ.get("SMTP_PASSWORD", "").strip()
    smtp_from_email = os.environ.get("SMTP_FROM_EMAIL", "").strip()

    if not all([smtp_host, smtp_username, smtp_password]):
        logger.error(
            "SMTP configuration incomplete. Required: SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD."
        )
        return False

    from_addr = smtp_from_email or smtp_username
    if from_name:
        from_header = f"{from_name} <{from_addr}>"
    else:
        from_header = from_addr

    msg = MIMEMultipart()
    msg["From"] = from_header
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        logger.error(f"Invalid SMTP_PORT: {smtp_port_str}")
        return False

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(from_addr, to_email, msg.as_string())

        logger.info(f"Email sent successfully to {to_email} via SMTP")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {to_email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email via SMTP to {to_email}: {e}")
        return False


def _send_via_sendgrid(
    to_email: str,
    subject: str,
    body: str,
    from_name: str | None = None,
) -> bool:
    """Send email using SendGrid API."""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, Content
    except ImportError:
        logger.error(
            "SendGrid library not installed. Run: pip install sendgrid"
        )
        return False

    api_key = os.environ.get("SENDGRID_API_KEY", "").strip()
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "").strip()

    if not api_key:
        logger.error("SENDGRID_API_KEY not set in environment variables.")
        return False

    if not from_email:
        logger.error("SENDGRID_FROM_EMAIL not set in environment variables.")
        return False

    try:
        sg = SendGridAPIClient(api_key)

        if from_name:
            sender = Email(from_email, from_name)
        else:
            sender = Email(from_email)

        content = Content("text/plain", body)
        mail = Mail(sender, Email(to_email), subject, content)

        response = sg.send(mail)

        if response.status_code in (200, 201, 202):
            logger.info(
                f"Email sent successfully to {to_email} via SendGrid "
                f"(status: {response.status_code})"
            )
            return True
        else:
            logger.warning(
                f"SendGrid returned non-success status {response.status_code} "
                f"for {to_email}"
            )
            return False

    except Exception as e:
        logger.error(f"Failed to send email via SendGrid to {to_email}: {e}")
        return False

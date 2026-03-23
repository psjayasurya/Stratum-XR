"""
Email Utilities
Functions for sending emails via SMTP.
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.config import config


def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Send email using SMTP
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body text
        
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = config.MAIL_USERNAME
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(config.MAIL_SERVER, config.MAIL_PORT)
        if config.MAIL_USE_TLS:
            server.starttls()
        server.login(config.MAIL_USERNAME, config.MAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


__all__ = ['send_email']

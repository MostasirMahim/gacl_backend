from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

import logging
logger = logging.getLogger("myapp")

@shared_task
def send_otp_mail_to_email(otp, email):
    try:
        logger.info(f"[EMAIL-OTP-LOG] to {email}: {otp}")
        send_mail("OTP for changing password",
                  f"Your OTP is {otp}", settings.DEFAULT_FROM_EMAIL, [email])  # Send mail
        return "Mail sent successfully"
    except Exception as E:
        logger.error(f"[EMAIL-OTP-LOG-ERROR] failed to send to {email}: {str(E)}")
        return f"Mail failed reason: {str(E)}"


@shared_task
def send_otp_email(email, otp_value):
    subject = "Your OTP Code"
    message = f"Your OTP code is {otp_value}"
    sender = settings.DEFAULT_FROM_EMAIL
    recipients = [email]

    logger.info(f"[EMAIL-OTP-LOG] to {email}: {otp_value}")
    try:
        send_mail(subject, message, sender, recipients, fail_silently=False)
    except Exception as E:
        logger.error(f"[EMAIL-OTP-LOG-ERROR] failed to send to {email}: {str(E)}")
        raise
    return f"OTP sent to {email}"

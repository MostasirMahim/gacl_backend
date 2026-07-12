from celery import shared_task
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
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
def send_member_credentials_email(email, first_name, username, temp_password):
    """
    Sends login credentials (username + temp password) to a newly
    approved member. Fired from ApproveMemberView after the CustomUser is
    created and linked. Uses the same send-and-log pattern as the OTP
    tasks above, but with an HTML template since this one has real
    content worth formatting (not just a bare code).
    """
    subject = "Your membership has been approved — login details inside"
    html_message = render_to_string("mails/member_credentials.html", {
        "first_name": first_name,
        "username": username,
        "temp_password": temp_password,
    })
    logger.info(f"[MEMBER-CREDENTIALS-LOG] to {email}: username={username}")
    try:
        msg = EmailMultiAlternatives(
            subject=subject,
            body=f"Your membership has been approved. Username: {username}, "
                 f"Temporary password: {temp_password}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email],
        )
        msg.attach_alternative(html_message, "text/html")
        msg.send(fail_silently=False)
    except Exception as e:
        logger.error(
            f"[MEMBER-CREDENTIALS-LOG-ERROR] failed to send to {email}: {str(e)}")
        raise
    return f"Credentials sent to {email}"


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

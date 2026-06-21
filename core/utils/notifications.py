"""
Centralised notification service (SMS / OTP).

Provider-agnostic: configure ANY SMS provider via environment variables and
`_dispatch_sms` will POST to it. No code change is needed when you buy SMS from
a phone company or a gateway (SSL Wireless, bulksmsbd, Twilio-style, etc.).

Environment variables (all optional; if SMS_GATEWAY_URL is unset, messages are
logged only, so the system still works in dev/testing):

    SMS_ENABLED          "true" / "false"      (default false -> log only)
    SMS_GATEWAY_URL      https://provider/api/send
    SMS_HTTP_METHOD      "POST" or "GET"       (default POST)
    SMS_API_KEY          your token/api key    (optional)
    SMS_SENDER_ID        approved sender id    (optional)
    SMS_AUTH_HEADER      e.g. "Authorization"  (optional; sends "<scheme> <key>")
    SMS_AUTH_SCHEME      e.g. "Bearer"         (default "Bearer")
    SMS_PHONE_PARAM      form field for phone  (default "to")
    SMS_MESSAGE_PARAM    form field for text   (default "message")
    SMS_SENDER_PARAM     form field for sender (default "sender_id")
    SMS_API_KEY_PARAM    form field for key    (optional; if set, key goes in body)
    SMS_EXTRA_PARAMS_JSON  '{"type":"text"}'   (optional extra static params)
"""
import json
import logging
import random

import environ
import requests

env = environ.Env()
logger = logging.getLogger("myapp")


def generate_otp(length: int = 6) -> str:
    start = 10 ** (length - 1)
    end = (10 ** length) - 1
    return str(random.randint(start, end))


def _build_payload(phone: str, message: str) -> dict:
    payload = {
        env.str("SMS_PHONE_PARAM", default="to"): phone,
        env.str("SMS_MESSAGE_PARAM", default="message"): message,
    }
    sender = env.str("SMS_SENDER_ID", default="")
    if sender:
        payload[env.str("SMS_SENDER_PARAM", default="sender_id")] = sender

    # some providers want the api key in the body rather than a header
    key_param = env.str("SMS_API_KEY_PARAM", default="")
    api_key = env.str("SMS_API_KEY", default="")
    if key_param and api_key:
        payload[key_param] = api_key

    extra = env.str("SMS_EXTRA_PARAMS_JSON", default="")
    if extra:
        try:
            payload.update(json.loads(extra))
        except json.JSONDecodeError:
            logger.warning("SMS_EXTRA_PARAMS_JSON is not valid JSON; ignored")
    return payload


def _build_headers() -> dict:
    headers = {}
    auth_header = env.str("SMS_AUTH_HEADER", default="")
    api_key = env.str("SMS_API_KEY", default="")
    if auth_header and api_key:
        scheme = env.str("SMS_AUTH_SCHEME", default="Bearer")
        headers[auth_header] = f"{scheme} {api_key}".strip()
    return headers


def _dispatch_sms(phone: str, message: str) -> bool:
    """
    Send via the configured provider. If SMS is disabled or no gateway URL is
    set, log only and return True (so dev/testing is never blocked).
    """
    enabled = env.bool("SMS_ENABLED", default=False)
    gateway_url = env.str("SMS_GATEWAY_URL", default="")

    if not enabled or not gateway_url:
        logger.info("[SMS-LOG] to %s: %s", phone, message)
        return True

    method = env.str("SMS_HTTP_METHOD", default="POST").upper()
    payload = _build_payload(phone, message)
    headers = _build_headers()

    try:
        if method == "GET":
            resp = requests.get(gateway_url, params=payload, headers=headers, timeout=15)
        else:
            resp = requests.post(gateway_url, data=payload, headers=headers, timeout=15)
        ok = resp.status_code in (200, 201, 202)
        if not ok:
            logger.warning("SMS provider returned %s: %s", resp.status_code, resp.text[:300])
        return ok
    except Exception as exc:
        logger.exception("SMS dispatch failed: %s", exc)
        return False


def send_sms(phone: str, message: str) -> bool:
    if not phone:
        logger.warning("send_sms called with empty phone; skipped")
        return False
    try:
        return _dispatch_sms(phone, message)
    except Exception as exc:  # never let notification failure break a request
        logger.exception("send_sms failed: %s", exc)
        return False


def send_order_otp(phone: str, otp: str, order_number: str) -> bool:
    return send_sms(
        phone,
        f"Your order {order_number} confirmation code is {otp}.")


def send_bill_notification(phone: str, order_number: str, amount, paid: bool) -> bool:
    state = "PAID" if paid else "billed"
    return send_sms(
        phone,
        f"Order {order_number} {state}. Amount: BDT {amount}.")

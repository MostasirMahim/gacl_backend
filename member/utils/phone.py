"""
Phone number normalization helper.

Used in two places (per master_update.md 3.3):
  (a) the contact-number serializer's duplicate check
      (member/serializers.py :: MemberContactNumberSerializer.validate)
  (b) ApproveMemberView, when turning a member's primary phone number into
      their initial login password.

Two different-looking strings like "+8801712345678" and "01712345678"
should be treated as the same number for comparison purposes. This module
does NOT rewrite what gets stored in ContactNumber.number -- it's purely a
comparison/derivation helper, so the raw value the member typed is still
what's saved to the DB.
"""
import re

try:
    import phonenumbers
except ImportError:  # pragma: no cover
    # `phonenumbers` should be present via requirements.txt. Fall back to a
    # conservative manual normalization so a missing/broken install doesn't
    # take down the whole duplicate-check / approval flow -- it just won't
    # catch every same-number-different-format case in that fallback path.
    phonenumbers = None

# The club's members are onboarded with Bangladeshi numbers today; used as
# the default region so a locally-formatted "01XXXXXXXXX" number parses
# correctly without the caller having to specify a country code.
DEFAULT_REGION = "BD"


def normalize_phone(raw):
    """
    Normalize a phone number string to E.164 format (e.g. "+8801712345678")
    for comparison. Returns the input unchanged (stripped) if it can't be
    parsed as a phone number at all.
    """
    if raw is None:
        return raw
    raw = str(raw).strip()
    if not raw:
        return raw

    if phonenumbers is not None:
        try:
            parsed = phonenumbers.parse(raw, DEFAULT_REGION)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(
                    parsed, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            pass

    # Fallback: keep only digits and a leading '+', then collapse a local
    # "0XXXXXXXXXX" prefix to "+880XXXXXXXXXX" the way phonenumbers would
    # have for a BD number, so the common case still normalizes even
    # without the library.
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("0"):
        digits = "+880" + digits[1:]
    elif not digits.startswith("+"):
        digits = "+" + digits
    return digits

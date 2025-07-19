# --- Standard libraries ---
from datetime import datetime, timezone
import re

PHONE_REGEX = re.compile(r"^\+\d{10,15}$")
API_HASH_REGEX = re.compile(r"^[a-fA-F0-9]{32}$")

def now_str() -> str:
    """
    Returns a string with the current time in UTC in the format "dd.mm.yyyy hh:mm:ss".

    :return: Time string in the format "%d.%m.%Y %H:%M:%S"
    """
    return datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M:%S")

def is_valid_profile_name(name: str) -> bool:
    """
    Checks that the profile name consists only of Russian/Latin letters and numbers, length 1-12 characters.
    """
    return bool(re.fullmatch(r"[А-Яа-яA-Za-z0-9 ()]{1,12}", name))

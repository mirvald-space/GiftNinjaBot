# --- Standard libraries ---
import json
import os
import logging
from typing import Optional

# --- Third-party libraries ---
import aiofiles

logger = logging.getLogger(__name__)

CURRENCY = 'XTR'
VERSION = '1.0.0'
CONFIG_PATH = "config.json"
DEV_MODE = False # Purchase of test gifts
MAX_PROFILES = 3 # Maximum message length is 4096 characters
PURCHASE_COOLDOWN = 0.3 # Number of purchases per second
USERBOT_UPDATE_COOLDOWN = 50 # Base waiting time in seconds for requesting gift list through userbot
ALLOWED_USER_IDS = []

def add_allowed_user(user_id):
    ALLOWED_USER_IDS.append(user_id)

def DEFAULT_PROFILE(user_id: int) -> dict:
    """Creates a profile with default settings for the specified user."""
    return {
        "NAME": None,
        "MIN_PRICE": 5000,
        "MAX_PRICE": 10000,
        "MIN_SUPPLY": 1000,
        "MAX_SUPPLY": 10000,
        "LIMIT": 1000000,
        "COUNT": 5,
        "TARGET_USER_ID": user_id,
        "TARGET_CHAT_ID": None,
        "TARGET_TYPE": None,
        "SENDER": "bot",
        "BOUGHT": 0,
        "SPENT": 0,
        "DONE": False
    }

def DEFAULT_CONFIG(user_id: int) -> dict:
    """Default configuration: global fields + list of profiles."""
    return {
        "BALANCE": 0,
        "ACTIVE": False,
        "LAST_MENU_MESSAGE_ID": None,
        "PROFILES": [DEFAULT_PROFILE(user_id)],
        "USERBOT": {
            "API_ID": None,
            "API_HASH": None,
            "PHONE": None,
            "USER_ID": None,
            "USERNAME": None,
            "BALANCE": 0,
            "ENABLED": False
        }
    }

# Types and requirements for each profile field
PROFILE_TYPES = {
    "NAME": (str, True),
    "MIN_PRICE": (int, False),
    "MAX_PRICE": (int, False),
    "MIN_SUPPLY": (int, False),
    "MAX_SUPPLY": (int, False),
    "LIMIT": (int, False),
    "COUNT": (int, False),
    "TARGET_USER_ID": (int, True),
    "TARGET_CHAT_ID": (str, True),
    "TARGET_TYPE": (str, True),
    "SENDER": (str, True),
    "BOUGHT": (int, False),
    "SPENT": (int, False),
    "DONE": (bool, False),
}

# Types and requirements for global fields
CONFIG_TYPES = {
    "BALANCE": (int, False),
    "ACTIVE": (bool, False),
    "LAST_MENU_MESSAGE_ID": (int, True),
    "PROFILES": (list, False),
    "USERBOT": (dict, False)
}


def is_valid_type(value, expected_type, allow_none=False):
    """
    Checks the type of value with None allowance.
    """
    if value is None:
        return allow_none
    return isinstance(value, expected_type)


async def ensure_config(user_id: int, path: str = CONFIG_PATH):
    """
    Ensures the existence of config.json.
    """
    if not os.path.exists(path):
        async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(DEFAULT_CONFIG(user_id), indent=2))
        logger.info(f"Configuration created: {path}")


async def load_config(path: str = CONFIG_PATH) -> dict:
    """
    Loads config from file (without validation). Ensures that the file exists.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"File {path} not found. Use ensure_config.")
    async with aiofiles.open(path, mode="r", encoding="utf-8") as f:
        data = await f.read()
        return json.loads(data)


async def save_config(config: dict, path: str = CONFIG_PATH):
    """
    Saves config to file.
    """
    async with aiofiles.open(path, mode="w", encoding="utf-8") as f:
        await f.write(json.dumps(config, indent=2))
    logger.info(f"Configuration saved.")


async def validate_profile(profile: dict, user_id: Optional[int] = None) -> dict:
    """
    Validates one profile.
    """
    valid = {}
    default = DEFAULT_PROFILE(user_id or 0)
    for key, (expected_type, allow_none) in PROFILE_TYPES.items():
        if key not in profile or not is_valid_type(profile[key], expected_type, allow_none):
            valid[key] = default[key]
        else:
            valid[key] = profile[key]
    return valid


async def validate_config(config: dict, user_id: int) -> dict:
    """
    Validates global config and all profiles.
    """
    valid = {}
    default = DEFAULT_CONFIG(user_id)
    # Top level
    for key, (expected_type, allow_none) in CONFIG_TYPES.items():
        if key == "PROFILES":
            profiles = config.get("PROFILES", [])
            # Validation of profiles
            valid_profiles = []
            for profile in profiles:
                valid_profiles.append(await validate_profile(profile, user_id))
            if not valid_profiles:
                valid_profiles = [DEFAULT_PROFILE(user_id)]
            valid["PROFILES"] = valid_profiles
        elif key == "USERBOT":
            userbot_data = config.get("USERBOT", {})
            default_userbot = default["USERBOT"]
            valid_userbot = {}
            for sub_key, default_value in default_userbot.items():
                value = userbot_data.get(sub_key, default_value)
                valid_userbot[sub_key] = value
            valid["USERBOT"] = valid_userbot
        else:
            if key not in config or not is_valid_type(config[key], expected_type, allow_none):
                valid[key] = default[key]
            else:
                valid[key] = config[key]
    return valid


async def get_valid_config(user_id: int, path: str = CONFIG_PATH) -> dict:
    """
    Loads, validates and updates config.json if necessary.
    """
    await ensure_config(user_id, path)
    config = await load_config(path)
    validated = await validate_config(config, user_id)
    # If validated version is different, save it
    if validated != config:
        await save_config(validated, path)
    return validated


async def migrate_config_if_needed(user_id: int, path: str = CONFIG_PATH):
    """
    Checks and converts config.json from old format (without PROFILES)
    to new (list of profiles). Works asynchronously.
    """
    if not os.path.exists(path):
        return

    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            data = await f.read()
            config = json.loads(data)
    except Exception:
        logger.error(f"Config {path} is corrupted.")
        os.remove(path)
        logger.error(f"Corrupted config {path} deleted.")
        return

    # If already new format, do nothing
    if "PROFILES" in config:
        return

    # Form profile from old keys
    profile_keys = [
        "MIN_PRICE", "MAX_PRICE", "MIN_SUPPLY", "MAX_SUPPLY",
        "COUNT", "LIMIT", "TARGET_USER_ID", "TARGET_CHAT_ID",
        "BOUGHT", "SPENT", "DONE"
    ]
    profile = {}
    for key in profile_keys:
        if key in config:
            profile[key] = config[key]

    profile.setdefault("LIMIT", 1000000)
    profile.setdefault("SPENT", 0)
    profile.setdefault("BOUGHT", 0)
    profile.setdefault("DONE", False)
    profile.setdefault("COUNT", 5)

    # Assemble new format
    new_config = {
        "BALANCE": config.get("BALANCE", 0),
        "ACTIVE": config.get("ACTIVE", False),
        "LAST_MENU_MESSAGE_ID": config.get("LAST_MENU_MESSAGE_ID"),
        "PROFILES": [profile],
    }

    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(new_config, ensure_ascii=False, indent=2))
    logger.info(f"Config {path} migrated to new format.")


# ------------- Working with profiles -----------------


async def get_profile(config: dict, index: int = 0) -> dict:
    """
    Get profile by index (first by default).
    """
    profiles = config.get("PROFILES", [])
    if not profiles:
        raise ValueError("No profiles in config")
    return profiles[index]


async def add_profile(config: dict, profile: dict, save: bool = True) -> dict:
    """
    Add a new profile to the config.
    """
    config["PROFILES"].append(profile)
    if save:
        await save_config(config)
    return config


async def update_profile(config: dict, index: int, new_profile: dict, save: bool = True) -> dict:
    """
    Update an existing profile by index.
    """
    if index >= len(config["PROFILES"]):
        raise IndexError(f"Profile index {index} out of range")
    config["PROFILES"][index] = new_profile
    if save:
        await save_config(config)
    return config


async def remove_profile(config: dict, index: int, user_id: int, save: bool = True) -> dict:
    """
    Remove a profile by index. If it's the last profile, replace it with a default one.
    """
    if index >= len(config["PROFILES"]):
        raise IndexError(f"Profile index {index} out of range")
    
    if len(config["PROFILES"]) == 1:
        # If it's the last profile, replace it with a default one
        config["PROFILES"][0] = DEFAULT_PROFILE(user_id)
    else:
        # Otherwise just remove it
        config["PROFILES"].pop(index)
    
    if save:
        await save_config(config)
    return config


def format_config_summary(config: dict, user_id: int) -> str:
    """
    Formats a summary of the current configuration for display in the menu.
    """
    active = config.get("ACTIVE", False)
    status = "🟢 Active" if active else "🔴 Inactive"
    balance = config.get("BALANCE", 0)
    
    # Userbot info
    userbot = config.get("USERBOT", {})
    userbot_enabled = userbot.get("ENABLED", False)
    userbot_balance = userbot.get("BALANCE", 0)
    userbot_username = userbot.get("USERNAME", None)
    
    # Format header
    header = f"<b>🥷 GiftsNinja</b> <code>v{VERSION}</code>\n\n"
    header += f"<b>Status:</b> {status}\n"
    header += f"<b>Balance:</b> {balance:,} ★\n"
    
    if userbot_enabled and userbot_username:
        header += f"<b>Userbot:</b> @{userbot_username} ({userbot_balance:,} ★)\n"
    
    # Format profiles
    profiles_text = "\n<b>📋 Profiles:</b>\n"
    
    for i, profile in enumerate(config["PROFILES"]):
        # Skip profiles beyond the limit to avoid message length issues
        if i >= MAX_PROFILES:
            profiles_text += f"\n... and {len(config['PROFILES']) - MAX_PROFILES} more profiles"
            break
            
        target_display = get_target_display(profile, user_id)
        
        name = profile.get("NAME", f"Profile {i+1}")
        count = profile.get("COUNT", 0)
        bought = profile.get("BOUGHT", 0)
        spent = profile.get("SPENT", 0)
        limit = profile.get("LIMIT", 0)
        done = profile.get("DONE", False)
        
        # Price range
        min_price = profile.get("MIN_PRICE", 0)
        max_price = profile.get("MAX_PRICE", 0)
        price_range = f"{min_price:,}–{max_price:,} ★"
        
        # Supply range
        min_supply = profile.get("MIN_SUPPLY", 0)
        max_supply = profile.get("MAX_SUPPLY", 0)
        supply_range = f"{min_supply:,}–{max_supply:,}"
        
        # Sender type
        sender = profile.get("SENDER", "bot")
        sender_icon = "🤖" if sender == "bot" else "👤"
        
        # Status icon
        status_icon = "✅" if done else ("🟢" if active else "🔴")
        
        profiles_text += (
            f"\n{status_icon} <b>{i+1}. {name}</b>\n"
            f"├👤 <b>Recipient:</b> {target_display}\n"
            f"├💰 <b>Price range:</b> {price_range}\n"
            f"├📊 <b>Supply range:</b> {supply_range}\n"
            f"├{sender_icon} <b>Sender:</b> {sender}\n"
            f"└🎁 <b>Progress:</b> {bought}/{count} ({spent:,}/{limit:,} ★)"
        )
    
    return header + profiles_text


def get_target_display(profile: dict, user_id: int) -> str:
    """
    Returns a formatted display of the target user/chat for the profile.
    """
    target_user_id = profile.get("TARGET_USER_ID")
    target_chat_id = profile.get("TARGET_CHAT_ID")
    
    return get_target_display_local(target_user_id, target_chat_id, user_id)


def get_target_display_local(target_user_id: Optional[int], target_chat_id: Optional[str], user_id: int) -> str:
    """
    Returns a formatted display of the target user/chat.
    """
    # Self
    if target_user_id == user_id:
        return f"yourself (ID: {target_user_id})"
    
    # Channel/chat
    if target_chat_id and target_chat_id.startswith("@"):
        return f"{target_chat_id}"
    
    # User by ID
    if target_user_id:
        return f"user (ID: {target_user_id})"
    
    return "not specified"

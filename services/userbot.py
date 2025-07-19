# --- Standard libraries ---
from datetime import datetime
import logging
import os
import builtins

# --- Third-party libraries ---
from pyrogram import Client
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneCodeInvalid,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    PhoneNumberInvalid,
    FloodWait,
    BadRequest,
    RPCError
)

# --- Internal modules ---
from services.config import get_valid_config, save_config
from utils.proxy import get_userbot_proxy

logger = logging.getLogger(__name__)

sessions_dir = os.path.abspath("sessions")
os.makedirs(sessions_dir, exist_ok=True)

_clients = {}  # Temporary storage of Client by user_id

def is_userbot_active(user_id: int) -> bool:
    """
    Checks if the userbot session is active (Client is already running).
    """
    info = _clients.get(user_id)
    return bool(info and info.get("client") and info.get("started"))


async def try_start_userbot_from_config(user_id: int):
    """
    Checks if there is a valid userbot session for the user and starts it.
    """
    # Prevent interactive input
    builtins.input = lambda _: (_ for _ in ()).throw(RuntimeError())

    os.makedirs(sessions_dir, exist_ok=True)

    config = await get_valid_config(user_id)
    userbot_data = config.get("USERBOT", {})
    required_fields = ("API_ID", "API_HASH", "PHONE")
    session_name = f"userbot_{user_id}"
    session_path = os.path.join(sessions_dir, f"{session_name}.session")
    
    # If config is invalid - delete the session if it exists
    if not all(userbot_data.get(k) for k in required_fields):
        logger.error("Required data missing in config.")

        if os.path.exists(session_path):
            try:
                os.remove(session_path)
                logger.info(".session file deleted due to empty config.")
            except Exception as e:
                logger.error(f"Failed to delete .session file: {e}")

        journal_path = session_path + "-journal"
        if os.path.exists(journal_path):
            try:
                os.remove(journal_path)
                logger.info("Session journal deleted.")
            except Exception as e:
                logger.error(f"Failed to delete session journal: {e}")

        await _clear_userbot_config(user_id)
        return False

    api_id = userbot_data["API_ID"]
    api_hash = userbot_data["API_HASH"]
    phone_number = userbot_data["PHONE"]

    app = await create_userbot_client(user_id, session_name, api_id, api_hash, phone_number, sessions_dir, None)

    if os.path.exists(session_path):
        if os.path.getsize(session_path) < 100:
            logger.error("Session file suspiciously small - possibly corrupted.")

        try:
            await app.start()
            me = await app.get_me()
            logger.info(f"Authorized as {me.first_name} ({me.id})")

            # Add client to _clients
            _clients[user_id] = {
                "client": app,
                "started": True,
            }

            return True

        except Exception as e:
            logger.error(f"Session is corrupted or incomplete: {e}")
            try:
                await app.stop()
            except Exception as stop_err:
                logger.error(f"Failed to stop client: {stop_err}")

            try:
                os.remove(session_path)
                logger.info("Deleted .session file.")
            except Exception as rm_err:
                logger.error(f"Failed to delete session: {rm_err}")

            journal = session_path + "-journal"
            if os.path.exists(journal):
                try:
                    os.remove(journal)
                    logger.info("Session journal deleted.")
                except Exception as j_err:
                    logger.error(f"Failed to delete session journal: {j_err}")

    else:
        logger.info("Session file not found. Authorization not performed.")

    # Clear USERBOT from config
    await _clear_userbot_config(user_id)

    return False


async def _clear_userbot_config(user_id: int):
    """
    Resets USERBOT fields in the config.
    """
    try:
        from services.database import update_user_userbot_data
        # Очищаем данные юзербота в таблице userbots
        await update_user_userbot_data(user_id, {
            "api_id": None,
            "api_hash": None,
            "phone": None,
            "username": None,
            "enabled": False
        })
        logger.info("Data in config cleared.")
    except Exception as e:
        logger.error(f"Failed to clear userbot config: {e}")


async def create_userbot_client(user_id: int, session_name: str, api_id: int, api_hash: str, phone: str, sessions_dir: str, proxy: str) -> Client:
    """
    Creates an instance of Pyrogram Client with preset parameters for userbot.
    
    :param session_name: Session name (.session file)
    :param api_id: api_id from Telegram
    :param api_hash: api_hash from Telegram
    :param phone: Phone number of the userbot account
    :param sessions_dir: Path to the folder where sessions are stored
    :return: Pyrogram Client object
    """
    # Proxy settings
    proxy_settings = await get_userbot_proxy(user_id)
    return Client(
        name=session_name,
        api_id=api_id,
        api_hash=api_hash,
        phone_number=phone,
        workdir=sessions_dir,
        device_model="Honor HONOR 70",
        system_version="SDK 35",
        app_version="Telegram Android 11.13.1",
        sleep_threshold=30,
        lang_code="en",
        skip_updates=False,
        proxy=proxy_settings
    )


async def start_userbot(message, state):
    """
    Initiates userbot connection: sends confirmation code and saves client state.
    """
    # Prevent interactive input
    builtins.input = lambda _: (_ for _ in ()).throw(RuntimeError())

    data = await state.get_data()
    user_id = message.from_user.id

    session_name = f"userbot_{user_id}"
    session_path = os.path.join(sessions_dir, f"{session_name}.session")

    api_id = data["api_id"]
    api_hash = data["api_hash"]
    phone_number = data["phone"]

    app = await create_userbot_client(user_id, session_name, api_id, api_hash, phone_number, sessions_dir, None)

    await app.connect()

    try:
        sent = await app.send_code(phone_number)
        _clients[user_id] = {
            "client": app,
            "phone_code_hash": sent.phone_code_hash,
            "phone": phone_number
        }
        return True
    except ApiIdInvalid:
        logger.error("Invalid api_id and api_hash. Check the data.")
        await message.answer("🚫 Invalid api_id and api_hash. Check the data.")
        return False
    except PhoneNumberInvalid:
        logger.error("Invalid phone number.")
        await message.answer("🚫 Invalid phone number.")
        return False
    except FloodWait as e:
        logger.error(f"Too many requests. Wait {e.value} seconds.")
        await message.answer(f"🚫 Too many requests. Wait {e.value} seconds.")
        return False
    except RPCError as e:
        logger.error(f"Telegram API error: {e.MESSAGE}")
        await message.answer(f"🚫 Telegram API error: {e.MESSAGE}")
        return False
    except BadRequest as e:
        logger.warning(f"Invalid phone number or request: {e}")
        await message.answer("🚫 Failed to send code. Check the number.")
        return False
    except Exception as e:
        logger.error(f"Unknown error: {e}")
        await message.answer(f"🚫 Unknown error: {e}")
        return False
    finally:
        if not app.is_connected:
            await app.disconnect()
            return False


async def continue_userbot_signin(message, state):
    """
    Continues userbot authorization using confirmation code.
    Returns flags: success, password needed, and retry needed.
    """
    data = await state.get_data()
    user_id = message.from_user.id
    code = data["code"]
    attempts = data.get("code_attempts", 0)

    client_info = _clients.get(user_id)
    if not client_info:
        logger.error("Client not found. Try starting over.")
        await message.answer("🚫 Client not found. Try starting over.")
        return False, False, False

    app = client_info["client"]
    phone = client_info["phone"]
    phone_code_hash = client_info["phone_code_hash"]
    api_id = data["api_id"]
    api_hash = data["api_hash"]

    if not code:
        logger.error("Code not specified.")
        await message.answer("�� Code not specified.")
        return False, False, False

    try:
        await app.sign_in(
            phone_number=phone,
            phone_code_hash=phone_code_hash,
            phone_code=code
        )

        # Check authorization via get_me()
        try:
            me = await app.get_me()
        except Exception:
            logger.error("Session not authorized even after password.")
            await message.answer("🚫 Session not authorized even after password.")
            return False, False

        await app.send_message("me", "✅ Userbot successfully authorized via Telegram-bot.")
        logger.info(f"Userbot successfully authorized: {me.first_name} ({me.id})")

        # Add client to _clients
        _clients[user_id] = {
            "client": app,
            "started": True,
        }

        # Save data
        from services.database import update_user_userbot_data
        userbot_data = {
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone,
            "user_id": me.id,
            "username": me.username,
            "enabled": True
        }
        await update_user_userbot_data(user_id, userbot_data)
        
        return True, False, False  # Success, password not needed, no retry
    except PhoneCodeInvalid:
        attempts += 1
        await state.update_data(code_attempts=attempts)
        if attempts < 3:
            logger.error(f"Incorrect code ({attempts}/3). Try again.")
            await message.answer(f"🚫 Incorrect code ({attempts}/3). Try again.\n\n/cancel — cancel")
            return False, False, True  # retry
        else:
            logger.error("Exceeded number of code attempts.")
            await message.answer("�� Exceeded number of code attempts.")
            return False, False, False  # final error
    except SessionPasswordNeeded:
        logger.info(f"Cloud password required.")
        return True, True, False  # Success, but password needed
    except Exception as e:
        logger.error(f"Authorization error: {e}")
        await message.answer(f"🚫 Authorization error: {e}")
        return False, False, False


async def finish_userbot_signin(message, state):
    """
    Finishes userbot authorization after entering password.
    Saves session and data to config on success.
    """
    data = await state.get_data()
    user_id = message.from_user.id
    client_info = _clients.get(user_id)

    if not client_info:
        logger.error("Client not found. Try starting over.")
        await message.answer("🚫 Client not found. Try starting over.")
        return False, False
    
    app = client_info["client"]
    password = data["password"]
    api_id = data["api_id"]
    api_hash = data["api_hash"]
    phone = data["phone"]
    attempts = data.get("password_attempts", 0)

    if not password:
        logger.error("Password not specified.")
        await message.answer("🚫 Password not specified.")
        return False, False
    
    try:
        await app.check_password(password)

        # Check authorization via get_me()
        try:
            me = await app.get_me()
        except Exception:
            logger.error("Session not authorized even after password.")
            await message.answer("🚫 Session not authorized even after password.")
            return False, False

        await app.send_message("me", "✅ Userbot successfully authorized via Telegram-bot.")
        logger.info(f"Userbot successfully authorized: {me.first_name} ({me.id})")

        # Add client to _clients
        _clients[user_id] = {
            "client": app,
            "started": True,
        }

        # Save data
        from services.database import update_user_userbot_data
        userbot_data = {
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone,
            "user_id": me.id,
            "username": me.username,
            "enabled": True
        }
        await update_user_userbot_data(user_id, userbot_data)
        return True, False
    except PasswordHashInvalid:
        attempts += 1
        await state.update_data(password_attempts=attempts)
        if attempts < 3:
            logger.error(f"Incorrect password ({attempts}/3). Try again.")
            await message.answer(f"🚫 Incorrect password ({attempts}/3). Try again.\n\n/cancel — cancel")
            return False, True  # retry
        else:
            logger.error("Exceeded number of password attempts.")
            await message.answer("🚫 Exceeded number of password attempts.")
            return False, False  # final error
    except Exception as e:
        logger.error(f"Error entering password: {e}")
        await message.answer(f"🚫 Error entering password: {e}")
        return False, False


async def userbot_send_self(user_id: int, text: str) -> bool:
    """
    Sends a confirmation message to the user's "Favorites" from the userbot.
    """
    client_info = _clients.get(user_id)
    if not client_info:
        logger.error("Client not found in _clients.")
        return False

    app = client_info["client"]

    try:
        await app.send_message("me", text, parse_mode=None)
        return True
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False
    

async def get_userbot_client(user_id: int) -> bool:
    """
    
    """
    client_info = _clients.get(user_id)
    if not client_info:
        logger.error("Client not found in _clients.")
        return False

    app = client_info["client"]

    return app
    

async def delete_userbot_session(user_id: int) -> bool:
    """
    Completely deletes the userbot session: stops the client, deletes files, and clears the config.
    """
    session_name = f"userbot_{user_id}"
    session_path = os.path.join(sessions_dir, f"{session_name}.session")
    journal_path = session_path + "-journal"

    # Stop if client is active
    client_info = _clients.get(user_id)
    if client_info and client_info.get("client"):
        try:
            await client_info["client"].stop()
            logger.info("Client stopped.")
        except Exception as e:
            logger.error(f"Error stopping client: {e}")

    # Delete session file
    if os.path.exists(session_path):
        try:
            os.remove(session_path)
            logger.info(".session file deleted.")
        except Exception as e:
            logger.error(f"Failed to delete .session file: {e}")

    # Delete journal file if it exists
    if os.path.exists(journal_path):
        try:
            os.remove(journal_path)
            logger.info("Journal deleted.")
        except Exception as e:
            logger.error(f"Failed to delete journal: {e}")

    # Clear config
    await _clear_userbot_config(user_id)

    # Remove from memory
    if user_id in _clients:
        del _clients[user_id]

    return True


async def get_userbot_stars_balance() -> int:
    """
    Gets the star balance via an authorized userbot.
    """
    user_id = next(iter(_clients), None)
    client_info = _clients.get(user_id)
    if not client_info or not client_info.get("client"):
        logger.error("Userbot not active or not authorized.")
        return 0

    app = client_info["client"]

    try:
        stars = await app.get_stars_balance()
        return stars
    except Exception as e:
        logger.error(f"Error getting userbot star balance: {e}")
        return 0
from typing import Optional
from aiogram.client.session.aiohttp import AiohttpSession

async def get_proxy_data(user_id: int) -> Optional[dict]:
    """
    Returns proxy connection data for the specified user.

    :param user_id: Telegram ID of the user for whom proxy settings are requested
    :return: Dictionary with fields 'hostname', 'port', 'username', 'password' or None if proxy is not used
    """
    proxy = {
        "hostname": "",
        "port": 0,
        "username": "",
        "password": ""
    }
    proxy = None
    return proxy

async def get_aiohttp_session(user_id: int) -> Optional[AiohttpSession]:
    """
    Creates an aiohttp session with proxy for the specified user.
    """
    db_proxy = await get_proxy_data(user_id)
    if not db_proxy: return None
    proxy_url = f"socks5://{db_proxy.get('username')}:{db_proxy.get('password')}@{db_proxy.get('hostname')}:{db_proxy.get('port')}"
    if proxy_url:
        return AiohttpSession(proxy=proxy_url)
    else:
        return None
    
async def get_userbot_proxy(user_id: int) -> Optional[dict]:
    """
    Forms a dictionary of proxy settings for userbot connection.
    """
    db_proxy = await get_proxy_data(user_id)
    if not db_proxy: return None
    settings = {
        "scheme": "socks5",
        "hostname": db_proxy.get("hostname"),
        "port": db_proxy.get("port"),
        "username": db_proxy.get("username"),
        "password": db_proxy.get("password")
    }
    return settings
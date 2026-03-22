"""
Bark 推送通知模块
"""

import logging
import urllib.parse
from typing import Optional

from curl_cffi import requests as cffi_requests

from ..config.settings import get_settings

logger = logging.getLogger(__name__)


def send_bark_notification(
    title: str,
    body: str,
    group: Optional[str] = "codex-register",
) -> bool:
    """
    发送 Bark 推送通知

    Args:
        title: 通知标题
        body: 通知内容
        group: 通知分组

    Returns:
        是否发送成功
    """
    try:
        settings = get_settings()
        bark_key = settings.bark_key.get_secret_value() if settings.bark_key else ""
        bark_server = settings.bark_server_url or "https://api.day.app"

        if not bark_key:
            return False

        # 去除末尾斜杠
        bark_server = bark_server.rstrip("/")

        # URL 编码标题和内容
        encoded_title = urllib.parse.quote(title, safe="")
        encoded_body = urllib.parse.quote(body, safe="")

        url = f"{bark_server}/{bark_key}/{encoded_title}/{encoded_body}"
        params = {}
        if group:
            params["group"] = group

        response = cffi_requests.get(url, params=params, timeout=10)

        if response.status_code == 200:
            logger.info(f"Bark 通知发送成功: {title}")
            return True
        else:
            logger.warning(f"Bark 通知发送失败: HTTP {response.status_code}")
            return False

    except Exception as e:
        logger.warning(f"Bark 通知发送异常: {e}")
        return False

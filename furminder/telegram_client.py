from __future__ import annotations

from config import Settings
from telegram.request import HTTPXRequest


def build_telegram_request(settings: Settings) -> HTTPXRequest:
    return HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=settings.telegram_connect_timeout,
        read_timeout=settings.telegram_read_timeout,
        write_timeout=settings.telegram_write_timeout,
        pool_timeout=settings.telegram_pool_timeout,
        proxy_url=settings.telegram_proxy_url,
    )

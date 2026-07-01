import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    mongodb_db: str
    mongodb_uri: str | None = None
    mongodb_user: str | None = None
    mongodb_password: str | None = None
    mongodb_hosts: str | None = None
    mongodb_replica_set: str | None = None
    mongodb_auth_source: str | None = None
    mongodb_tls_ca_file: str | None = None
    telegram_proxy_url: str | None = None
    telegram_connect_timeout: float = 30.0
    telegram_read_timeout: float = 30.0
    telegram_write_timeout: float = 30.0
    telegram_pool_timeout: float = 10.0
    default_timezone: str = "Europe/Moscow"
    default_locale: str = "ru"


def _resolve_tls_ca_file(raw: str | None) -> str | None:
    if not raw:
        return None
    return str(Path(os.path.expandvars(raw)).expanduser())


def get_settings() -> Settings:
    bot_token = os.environ.get("BOT_TOKEN", "").strip()
    mongodb_db = os.environ.get("MONGODB_DB", "furminder").strip()

    mongodb_uri = os.environ.get("MONGODB_URI", "").strip() or None
    mongodb_user = os.environ.get("MONGODB_USER", "").strip() or None
    mongodb_password = os.environ.get("MONGODB_PASSWORD", "").strip() or None
    mongodb_hosts = os.environ.get("MONGODB_HOSTS", "").strip() or None
    mongodb_replica_set = os.environ.get("MONGODB_REPLICA_SET", "").strip() or None
    mongodb_auth_source = os.environ.get("MONGODB_AUTH_SOURCE", "").strip() or None
    mongodb_tls_ca_file = _resolve_tls_ca_file(os.environ.get("MONGODB_TLS_CA_FILE", "").strip() or None)

    if not bot_token:
        raise RuntimeError("BOT_TOKEN is not set")

    has_components = all(
        [mongodb_user, mongodb_password, mongodb_hosts, mongodb_replica_set, mongodb_auth_source]
    )
    if not mongodb_uri and not has_components:
        raise RuntimeError(
            "Set either MONGODB_URI or all of: MONGODB_USER, MONGODB_PASSWORD, "
            "MONGODB_HOSTS, MONGODB_REPLICA_SET, MONGODB_AUTH_SOURCE"
        )

    if mongodb_tls_ca_file and not Path(mongodb_tls_ca_file).is_file():
        raise RuntimeError(f"MONGODB_TLS_CA_FILE not found: {mongodb_tls_ca_file}")

    telegram_proxy_url = os.environ.get("TELEGRAM_PROXY_URL", "").strip() or None
    telegram_connect_timeout = float(os.environ.get("TELEGRAM_CONNECT_TIMEOUT", "30"))
    telegram_read_timeout = float(os.environ.get("TELEGRAM_READ_TIMEOUT", "30"))
    telegram_write_timeout = float(os.environ.get("TELEGRAM_WRITE_TIMEOUT", "30"))
    telegram_pool_timeout = float(os.environ.get("TELEGRAM_POOL_TIMEOUT", "10"))

    return Settings(
        bot_token=bot_token,
        mongodb_db=mongodb_db,
        mongodb_uri=mongodb_uri,
        mongodb_user=mongodb_user,
        mongodb_password=mongodb_password,
        mongodb_hosts=mongodb_hosts,
        mongodb_replica_set=mongodb_replica_set,
        mongodb_auth_source=mongodb_auth_source,
        mongodb_tls_ca_file=mongodb_tls_ca_file,
        telegram_proxy_url=telegram_proxy_url,
        telegram_connect_timeout=telegram_connect_timeout,
        telegram_read_timeout=telegram_read_timeout,
        telegram_write_timeout=telegram_write_timeout,
        telegram_pool_timeout=telegram_pool_timeout,
    )

from __future__ import annotations

from urllib.parse import quote_plus as quote

from motor.motor_asyncio import AsyncIOMotorClient

from config import Settings


def build_mongodb_uri(settings: Settings) -> str:
    if settings.mongodb_uri:
        return settings.mongodb_uri

    return "mongodb://{user}:{pw}@{hosts}/?replicaSet={rs}&authSource={auth_src}".format(
        user=quote(settings.mongodb_user or ""),
        pw=quote(settings.mongodb_password or ""),
        hosts=settings.mongodb_hosts,
        rs=settings.mongodb_replica_set,
        auth_src=settings.mongodb_auth_source,
    )


def create_mongo_client(settings: Settings) -> AsyncIOMotorClient:
    uri = build_mongodb_uri(settings)
    kwargs: dict = {}

    if settings.mongodb_tls_ca_file:
        kwargs["tls"] = True
        kwargs["tlsCAFile"] = settings.mongodb_tls_ca_file

    return AsyncIOMotorClient(uri, **kwargs)

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from config import Settings
from furminder.db.connection import create_mongo_client

DEFAULT_REMINDER_RULES = [
    {"offset_days": 7, "send_time": "09:00", "silent": False, "enabled": True},
    {"offset_days": 1, "send_time": "09:00", "silent": False, "enabled": True},
    {"offset_days": 0, "send_time": "09:00", "silent": False, "enabled": True},
]


class Database:
    def __init__(self, settings: Settings) -> None:
        self.client: AsyncIOMotorClient = create_mongo_client(settings)
        self.db: AsyncIOMotorDatabase = self.client[settings.mongodb_db]

    @classmethod
    def from_settings(cls, settings: Settings) -> Database:
        return cls(settings)

    @property
    def chats(self):
        return self.db.chats

    @property
    def events(self):
        return self.db.events

    @property
    def reminder_rules(self):
        return self.db.reminder_rules

    @property
    def sent_reminders(self):
        return self.db.sent_reminders

    async def ensure_indexes(self) -> None:
        await self.events.create_index([("chat_id", 1), ("local_id", 1)], unique=True)
        await self.events.create_index([("chat_id", 1), ("start_date", 1)])
        await self.reminder_rules.create_index([("chat_id", 1)])
        await self.sent_reminders.create_index(
            [("event_id", 1), ("rule_id", 1), ("occurrence_start", 1)],
            unique=True,
        )

    async def ensure_chat(self, chat_id: int, title: str | None = None) -> dict[str, Any]:
        existing = await self.chats.find_one({"_id": chat_id})
        if existing:
            if title and existing.get("title") != title:
                await self.chats.update_one({"_id": chat_id}, {"$set": {"title": title}})
            return existing

        chat_doc = {
            "_id": chat_id,
            "title": title or "",
            "timezone": "Europe/Moscow",
            "allow_non_admin_add": True,
            "default_silent": False,
            "active": True,
            "event_counter": 0,
            "created_at": datetime.utcnow(),
        }
        await self.chats.insert_one(chat_doc)
        for rule in DEFAULT_REMINDER_RULES:
            await self.reminder_rules.insert_one({"chat_id": chat_id, **rule})
        return chat_doc

    async def deactivate_chat(self, chat_id: int) -> None:
        await self.chats.update_one({"_id": chat_id}, {"$set": {"active": False}})

    async def get_chat(self, chat_id: int) -> dict[str, Any] | None:
        return await self.chats.find_one({"_id": chat_id})

    async def next_local_id(self, chat_id: int) -> int:
        result = await self.chats.find_one_and_update(
            {"_id": chat_id},
            {"$inc": {"event_counter": 1}},
            return_document=True,
        )
        return int(result["event_counter"])

    async def create_event(self, event_doc: dict[str, Any]) -> dict[str, Any]:
        result = await self.events.insert_one(event_doc)
        event_doc["_id"] = result.inserted_id
        return event_doc

    async def get_event(self, chat_id: int, local_id: int) -> dict[str, Any] | None:
        return await self.events.find_one({"chat_id": chat_id, "local_id": local_id})

    async def list_upcoming_events(self, chat_id: int, *, limit: int = 20) -> list[dict[str, Any]]:
        today = date.today().isoformat()
        cursor = self.events.find(
            {
                "chat_id": chat_id,
                "$or": [
                    {"start_date": {"$gte": today}},
                    {"recurrence.enabled": True},
                ],
            }
        ).sort("start_date", 1).limit(limit)
        return await cursor.to_list(length=limit)

    async def update_event(self, chat_id: int, local_id: int, updates: dict[str, Any]) -> bool:
        updates["updated_at"] = datetime.utcnow()
        result = await self.events.update_one(
            {"chat_id": chat_id, "local_id": local_id},
            {"$set": updates},
        )
        return result.modified_count > 0

    async def delete_event(self, chat_id: int, local_id: int) -> bool:
        event = await self.get_event(chat_id, local_id)
        if not event:
            return False
        await self.sent_reminders.delete_many({"event_id": event["_id"]})
        result = await self.events.delete_one({"chat_id": chat_id, "local_id": local_id})
        return result.deleted_count > 0

    async def list_reminder_rules(self, chat_id: int) -> list[dict[str, Any]]:
        cursor = self.reminder_rules.find({"chat_id": chat_id}).sort("offset_days", -1)
        return await cursor.to_list(length=100)

    async def add_reminder_rule(
        self,
        chat_id: int,
        *,
        offset_days: int,
        send_time: str,
        silent: bool,
    ) -> dict[str, Any]:
        doc = {
            "chat_id": chat_id,
            "offset_days": offset_days,
            "send_time": send_time,
            "silent": silent,
            "enabled": True,
        }
        result = await self.reminder_rules.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc

    async def toggle_reminder_rule(self, chat_id: int, rule_id: ObjectId) -> bool | None:
        rule = await self.reminder_rules.find_one({"_id": rule_id, "chat_id": chat_id})
        if not rule:
            return None
        new_value = not rule.get("enabled", True)
        await self.reminder_rules.update_one({"_id": rule_id}, {"$set": {"enabled": new_value}})
        return new_value

    async def delete_reminder_rule(self, chat_id: int, rule_id: ObjectId) -> bool:
        result = await self.reminder_rules.delete_one({"_id": rule_id, "chat_id": chat_id})
        if result.deleted_count:
            await self.sent_reminders.delete_many({"rule_id": rule_id})
        return result.deleted_count > 0

    async def mark_reminder_sent(
        self,
        *,
        event_id: ObjectId,
        rule_id: ObjectId,
        occurrence_start: str,
    ) -> None:
        await self.sent_reminders.update_one(
            {
                "event_id": event_id,
                "rule_id": rule_id,
                "occurrence_start": occurrence_start,
            },
            {
                "$setOnInsert": {
                    "event_id": event_id,
                    "rule_id": rule_id,
                    "occurrence_start": occurrence_start,
                    "sent_at": datetime.utcnow(),
                }
            },
            upsert=True,
        )

    async def was_reminder_sent(
        self,
        *,
        event_id: ObjectId,
        rule_id: ObjectId,
        occurrence_start: str,
    ) -> bool:
        doc = await self.sent_reminders.find_one(
            {
                "event_id": event_id,
                "rule_id": rule_id,
                "occurrence_start": occurrence_start,
            }
        )
        return doc is not None

    async def list_active_chats(self) -> list[dict[str, Any]]:
        cursor = self.chats.find({"active": True})
        return await cursor.to_list(length=10000)

    async def list_events_for_chat(self, chat_id: int) -> list[dict[str, Any]]:
        cursor = self.events.find({"chat_id": chat_id})
        return await cursor.to_list(length=10000)

    async def update_chat_settings(self, chat_id: int, updates: dict[str, Any]) -> None:
        await self.chats.update_one({"_id": chat_id}, {"$set": updates})


def parse_time_str(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))

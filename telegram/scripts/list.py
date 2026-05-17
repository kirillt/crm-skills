#!/usr/bin/env python3
"""
Auxiliary Telegram dialog listing and discovery tool.
"""

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.types import Channel, Chat, User

from loader import ensure_authorized_client, load_skip_ids, load_telegram_config
from session import session_lock


INTERNAL_DIALOG_IDS = {"777000", "1271266957"}
SESSION_FILE = Path("tmp") / "telegram" / "session"
LOCK_FILE = Path("tmp") / "telegram" / "session.lock"


def parse_args():
    parser = argparse.ArgumentParser(description="List Telegram dialogs for discovery and review.")
    parser.add_argument("mode", choices=["broadcast", "dm", "groups", "large", "small"], help="Dialog category to list")
    parser.add_argument("--since", help="Include only dialogs whose latest visible message is on or after this UTC date (YYYY-MM-DD)")
    parser.add_argument("--until", help="Include only dialogs whose latest visible message within the window is on or before this UTC date (YYYY-MM-DD)")
    parser.add_argument("--local-time", action="store_true", help="Display timestamps in the local timezone of the machine running the script")
    args = parser.parse_args()
    if args.since:
        datetime.strptime(args.since, "%Y-%m-%d")
    if args.until:
        datetime.strptime(args.until, "%Y-%m-%d")
    if args.since and args.until and args.until < args.since:
        parser.error("--until must be on or after --since")
    return args


def dialog_kind(entity):
    if isinstance(entity, Channel):
        return "broadcast" if entity.broadcast else "groups"
    if isinstance(entity, Chat):
        return "groups"
    if isinstance(entity, User):
        return "dm"
    return None


def format_display_dt(value, local_time=False):
    if value is None:
        return "(no last message date)"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    if local_time:
        return value.astimezone().isoformat(sep=" ", timespec="seconds")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def normalize_dt(value):
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_internal_dialog(entity, dialog_id):
    dialog_id_str = str(dialog_id)
    if dialog_id_str in INTERNAL_DIALOG_IDS:
        return True
    return isinstance(entity, User) and getattr(entity, "bot", False) and getattr(entity, "username", None) == "replies"


async def get_participant_count(client, entity):
    direct = getattr(entity, "participants_count", None)
    if isinstance(direct, int):
        return direct

    try:
        if isinstance(entity, Channel):
            full = await client(GetFullChannelRequest(entity))
            count = getattr(full.full_chat, "participants_count", None)
            if isinstance(count, int):
                return count
        elif isinstance(entity, Chat):
            full = await client(GetFullChatRequest(entity.id))
            count = getattr(full.full_chat, "participants_count", None)
            if isinstance(count, int):
                return count
            participants = getattr(getattr(full.full_chat, "participants", None), "participants", None)
            if participants is not None:
                return len(participants)
    except Exception:
        return None

    return None


async def latest_message_on_or_before(client, entity, until=None):
    if until is None:
        return None
    msgs = await client.get_messages(entity, offset_date=until + timedelta(days=1), limit=1)
    if msgs:
        return normalize_dt(msgs[0].date)
    return None


async def list_dialogs(client, mode, skip_ids, small_group_max_participants, since=None, until=None, local_time=False):
    if mode == "broadcast":
        header = "Broadcast channels"
    elif mode == "groups":
        header = "Groups"
    elif mode == "large":
        header = f"Large chats and channels (groups >= {small_group_max_participants})"
    elif mode == "small":
        header = f"Small groups and direct chats (groups < {small_group_max_participants})"
    else:
        header = "Direct chats"
    print(f"{header}:\n")

    rows = []
    async for dialog in client.iter_dialogs():
        entity = dialog.entity
        if is_internal_dialog(entity, dialog.id):
            continue
        if str(dialog.id) in skip_ids:
            continue

        kind = dialog_kind(entity)
        if kind is None:
            continue

        participant_count = None
        if mode == "small":
            if kind not in {"dm", "groups"}:
                continue
            if kind == "groups":
                participant_count = await get_participant_count(client, entity)
                if participant_count is None or participant_count >= small_group_max_participants:
                    continue
        elif mode == "large":
            if kind not in {"broadcast", "groups"}:
                continue
            if kind == "groups":
                participant_count = await get_participant_count(client, entity)
                if participant_count is not None and participant_count < small_group_max_participants:
                    continue
        elif kind != mode:
            continue

        last_dt = normalize_dt(getattr(dialog, "date", None))
        if until is not None:
            if last_dt is None:
                window_last_dt = await latest_message_on_or_before(client, entity, until)
                if window_last_dt is None:
                    continue
                last_dt = window_last_dt
            elif last_dt >= until + timedelta(days=1):
                window_last_dt = await latest_message_on_or_before(client, entity, until)
                if window_last_dt is None:
                    continue
                last_dt = window_last_dt
        if since is not None and (last_dt is None or last_dt < since):
            continue
        if until is not None and last_dt >= until + timedelta(days=1):
            continue

        rows.append((kind, participant_count, last_dt, dialog))

    rows.sort(key=lambda row: (-(row[2].timestamp()) if row[2] is not None else float("inf")))

    for kind, participant_count, last_dt, dialog in rows:
        entity = dialog.entity
        if kind == "groups":
            type_label = "[GROUP]"
            kind_label = "Group"
        elif kind == "broadcast":
            type_label = "[BROADCAST]"
            kind_label = "Broadcast"
        else:
            type_label = "[DM]"
            kind_label = "Direct"

        uname = getattr(entity, "username", None)
        uname_display = f"@{uname}" if uname else "(no username)"
        last_display = format_display_dt(last_dt, local_time=local_time)
        extra = f"  participants: {participant_count}" if kind == "groups" and participant_count is not None else ""
        print(f"  {type_label} {dialog.title}  ID: {dialog.id}  {kind_label}  {uname_display}  last: {last_display}{extra}")

    print(f"\n{len(rows)} dialog(s) found.")


async def main():
    args = parse_args()
    config = load_telegram_config()
    skip_ids = load_skip_ids()
    since = datetime.strptime(args.since, "%Y-%m-%d").replace(tzinfo=timezone.utc) if args.since else None
    until = datetime.strptime(args.until, "%Y-%m-%d").replace(tzinfo=timezone.utc) if args.until else None

    with session_lock(LOCK_FILE):
        client = await ensure_authorized_client(SESSION_FILE)
        try:
            await list_dialogs(
                client,
                args.mode,
                skip_ids,
                config["small_group_max_participants"],
                since=since,
                until=until,
                local_time=args.local_time,
            )
        finally:
            await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())

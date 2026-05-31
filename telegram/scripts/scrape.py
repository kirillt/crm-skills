#!/usr/bin/env python3
"""Shared Telegram scrape primitives."""

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone

from telethon.errors import FloodWaitError

from telethon.utils import get_peer_id


async def reconnect(client, max_retries, initial_backoff_s):
    for attempt in range(max_retries):
        try:
            if not client.is_connected():
                await client.connect()
            return
        except (ConnectionError, OSError) as err:
            wait = initial_backoff_s * (2 ** attempt)
            print(f"Reconnect {attempt + 1}/{max_retries} failed: {err}. Retrying in {wait}s...")
            await asyncio.sleep(wait)
    raise ConnectionError("Failed to reconnect after max retries")


async def resolve_target(client, reference):
    ref = reference.strip()
    if ref.lstrip("-").isdigit():
        return await client.get_entity(int(ref))
    return await client.get_entity(ref.lstrip("@"))


def channel_id_for_entity(entity):
    return str(get_peer_id(entity))


def write_message(by_date_root, by_id_root, channel_id, message):
    utc_dt = message.date.astimezone(timezone.utc)
    date_str = utc_dt.strftime("%Y-%m-%d")
    ts = utc_dt.strftime("%Y%m%dT%H%M%SZ")
    filename = f"{ts}-{channel_id}-{message.id}.json"

    dated_dir = by_date_root / date_str / channel_id
    channel_dir = by_id_root / channel_id / date_str
    dated_file = dated_dir / filename
    channel_file = channel_dir / filename
    is_new = not channel_file.exists()

    if dated_file.exists() and channel_file.exists():
        return False

    dated_dir.mkdir(parents=True, exist_ok=True)
    channel_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "text": message.message or "",
        "author": message.sender_id if message.sender_id is not None else channel_id,
        "channel": channel_id,
        "timestamp": utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    dated_file.write_text(encoded, encoding="utf-8")
    channel_file.write_text(encoded, encoding="utf-8")
    return is_new


def find_last_message_id(by_id_root, channel_id):
    pattern = re.compile(rf"-{re.escape(channel_id)}-(\d+)\.json$")
    channel_dir = by_id_root / channel_id
    if not channel_dir.exists():
        return 0

    for date_dir in sorted((entry for entry in channel_dir.iterdir() if entry.is_dir()), reverse=True):
        best = 0
        for entry in date_dir.iterdir():
            if not entry.is_file():
                continue
            match = pattern.search(entry.name)
            if match:
                best = max(best, int(match.group(1)))
        if best:
            return best
    return 0


def has_cached_messages(by_id_root, channel_id):
    channel_dir = by_id_root / channel_id
    if not channel_dir.exists():
        return False
    for date_dir in channel_dir.iterdir():
        if date_dir.is_dir() and any(entry.is_file() for entry in date_dir.iterdir()):
            return True
    return False


async def cutoff_offset_id(client, entity, since_date):
    since = datetime.strptime(since_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    msgs = await client.get_messages(entity, offset_date=since, limit=1)
    if msgs:
        return msgs[0].id
    return 0


def parse_utc_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def inclusive_utc_day_end(date_str):
    return parse_utc_date(date_str) + timedelta(days=1)


async def sync_messages(
    *,
    client,
    reference,
    by_date_root,
    by_id_root,
    skip_ids,
    max_retries,
    initial_backoff_s,
    since_date=None,
    until_date=None,
    all_history=False,
    full_conversation=False,
    context_messages=None,
    skip_cached=False,
    report_new_files=False,
):
    entity = await resolve_target(client, reference)
    channel_id = channel_id_for_entity(entity)
    name = getattr(entity, "title", None) or getattr(entity, "first_name", None) or reference

    if channel_id in skip_ids:
        print(f"{reference}: skipped because target ID {channel_id} is in auth/telegram.skip")
        return {"reference": reference, "channel_id": channel_id, "name": name, "status": "skipped", "written": 0}

    if skip_cached and has_cached_messages(by_id_root, channel_id):
        print(f"{name}: already cached; skipping Telegram sync")
        payload = {
            "reference": reference,
            "channel_id": channel_id,
            "name": name,
            "status": "cached",
            "iterated": 0,
        }
        if report_new_files:
            payload.update({"written": 0})
        return payload

    if context_messages:
        since_dt = parse_utc_date(since_date)
        until_dt_exclusive = inclusive_utc_day_end(until_date)
        print(f"{name}: context mode, up to {context_messages} messages ending at the latest in-window message")

        anchor = None
        async for message in client.iter_messages(entity, offset_date=until_dt_exclusive):
            message_dt = message.date.astimezone(timezone.utc)
            if message_dt < since_dt:
                break
            anchor = message
            break

        if anchor is None:
            print(f"{name}: no messages inside selected window")
            payload = {
                "reference": reference,
                "channel_id": channel_id,
                "name": name,
                "status": "no_window_messages",
                "iterated": 0,
            }
            if report_new_files:
                payload.update({"written": 0})
            return payload

        messages = [anchor]
        if context_messages > 1:
            async for message in client.iter_messages(entity, offset_id=anchor.id, limit=context_messages - 1):
                messages.append(message)

        written = 0
        for message in reversed(messages):
            if write_message(by_date_root, by_id_root, channel_id, message):
                written += 1

        processed = len(messages)
        ordered_messages = sorted(messages, key=lambda item: item.id)
        payload = {
            "reference": reference,
            "channel_id": channel_id,
            "name": name,
            "status": "done",
            "iterated": processed,
            "context_messages": context_messages,
            "anchor_message_id": anchor.id,
            "anchor_timestamp": anchor.date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "context_message_ids": [message.id for message in ordered_messages],
        }
        if report_new_files:
            print(f"{reference}: done, {processed} context messages iterated, {written} new files visible under cache/telegram/by_id/{channel_id}/")
            payload.update({"written": written})
        else:
            print(f"{name}: done, {processed} context message(s)")
        return payload

    full_sync = all_history or full_conversation
    offset_id = 0 if full_sync else find_last_message_id(by_id_root, channel_id)

    since_dt = None if full_sync else (parse_utc_date(since_date) if since_date else None)
    until_dt_exclusive = None if full_sync else (inclusive_utc_day_end(until_date) if until_date else None)

    if not full_sync and since_date:
        cutoff_id = await cutoff_offset_id(client, entity, since_date)
        offset_id = max(offset_id, cutoff_id)

    if all_history:
        print(f"{name}: full-history mode")
    elif full_conversation:
        if since_date and until_date:
            print(f"{name}: full-conversation mode for window {since_date} through {until_date}")
        else:
            print(f"{name}: full-conversation mode")
    elif since_date and until_date:
        print(f"{name}: syncing messages from {since_date} through {until_date}")
    elif since_date:
        print(f"{name}: syncing messages after {since_date}")
    elif offset_id > 0:
        print(f"{name}: resuming from message {offset_id}")

    processed = 0
    written = 0
    current_offset = offset_id

    while True:
        try:
            async for message in client.iter_messages(entity, offset_id=current_offset, reverse=True):
                message_dt = message.date.astimezone(timezone.utc)
                if since_dt is not None and message_dt < since_dt:
                    continue
                if until_dt_exclusive is not None and message_dt >= until_dt_exclusive:
                    break
                if write_message(by_date_root, by_id_root, channel_id, message):
                    written += 1
                processed += 1
                current_offset = message.id
                if processed % 100 == 0:
                    print(f"{reference}: {processed} messages processed...")
            break
        except FloodWaitError as err:
            print(f"{reference}: rate-limited, waiting {err.seconds}s...")
            await asyncio.sleep(err.seconds)
        except (ConnectionError, OSError) as err:
            print(f"{reference}: connection lost: {err}. Reconnecting...")
            await reconnect(client, max_retries, initial_backoff_s)
            entity = await resolve_target(client, reference)

    payload = {
        "reference": reference,
        "channel_id": channel_id,
        "name": name,
        "status": "done",
        "iterated": processed,
    }

    if processed == 0:
        print(f"{name}: no new messages")

    if report_new_files:
        print(f"{reference}: done, {processed} messages iterated, {written} new files visible under cache/telegram/by_id/{channel_id}/")
        payload.update({"written": written})
    else:
        print(f"{name}: done, {processed} message(s)")

    return payload

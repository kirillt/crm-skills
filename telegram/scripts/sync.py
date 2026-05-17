#!/usr/bin/env python3
"""
Telegram message sync entrypoint shared by small and large chat workflows.
"""

import argparse
import asyncio
import json
from pathlib import Path
from datetime import datetime

from loader import ensure_authorized_client, load_skip_ids, load_telegram_config
from scrape import sync_messages
from session import session_lock


SESSION_FILE = Path("tmp") / "telegram" / "session"
LOCK_FILE = Path("tmp") / "telegram" / "session.lock"
OUTPUT_ROOT = Path("cache") / "telegram"
BY_DATE_ROOT = OUTPUT_ROOT / "by_date"
BY_ID_ROOT = OUTPUT_ROOT / "by_id"


def parse_args():
    parser = argparse.ArgumentParser(description="Sync Telegram messages for one or more targets.")
    parser.add_argument("target", nargs="+", help="Telegram target reference(s): @handle, user ID, or chat ID")
    parser.add_argument("--since", help="Sync only messages after this UTC date (YYYY-MM-DD)")
    parser.add_argument("--until", help="Sync only messages through this UTC date (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="Debug mode: sync full history instead of using the cutoff")
    parser.add_argument("--full-conversation", action="store_true", help="For window-selected targets, sync the full conversation instead of only messages inside the window")
    parser.add_argument("--skip-cached", action="store_true", help="Skip targets that already have any cached Telegram messages")
    args = parser.parse_args()

    if args.all and args.full_conversation:
        parser.error("--all and --full-conversation are mutually exclusive")
    if args.all and (args.since or args.until):
        parser.error("--all cannot be combined with --since or --until")
    if not args.all and not args.since:
        parser.error("Provide --since YYYY-MM-DD, or use --all for debug full-history sync")

    if args.since:
        datetime.strptime(args.since, "%Y-%m-%d")
    if args.until:
        datetime.strptime(args.until, "%Y-%m-%d")
    if args.since and args.until and args.until < args.since:
        parser.error("--until must be on or after --since")

    return args


async def main():
    args = parse_args()
    config = load_telegram_config()
    skip_ids = load_skip_ids()

    BY_DATE_ROOT.mkdir(parents=True, exist_ok=True)
    BY_ID_ROOT.mkdir(parents=True, exist_ok=True)

    with session_lock(LOCK_FILE):
        client = await ensure_authorized_client(SESSION_FILE)
        try:
            results = []
            for target in args.target:
                results.append(await sync_messages(
                    client=client,
                    reference=target,
                    by_date_root=BY_DATE_ROOT,
                    by_id_root=BY_ID_ROOT,
                    skip_ids=skip_ids,
                    max_retries=config["max_retries"],
                    initial_backoff_s=config["initial_backoff_s"],
                    since_date=args.since,
                    until_date=args.until,
                    all_history=args.all,
                    full_conversation=args.full_conversation,
                    skip_cached=args.skip_cached,
                    report_new_files=True,
                ))
        finally:
            await client.disconnect()

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

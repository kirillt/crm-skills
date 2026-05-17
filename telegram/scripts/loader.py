#!/usr/bin/env python3
import json
import getpass
import sys
from io import StringIO
from pathlib import Path

import qrcode
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError


AUTH_FILE = Path("auth") / "telegram.json"
SKIP_FILE = Path("auth") / "telegram.skip"
TELEGRAM_CONFIG_FILE = Path("config") / "telegram" / "main.json"

DEFAULT_TELEGRAM_CONFIG = {
    "discover-batch-size": 15,
    "persist-batch-size": 15,
    "small_group_max_participants": 15,
    "max_retries": 5,
    "initial_backoff_s": 2,
}


def load_telegram_config():
    loaded = {}

    if TELEGRAM_CONFIG_FILE.exists():
        try:
            candidate = json.loads(TELEGRAM_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(candidate, dict):
                loaded = candidate
        except (OSError, json.JSONDecodeError):
            loaded = {}

    config = dict(DEFAULT_TELEGRAM_CONFIG)
    for key, default_value in DEFAULT_TELEGRAM_CONFIG.items():
        value = loaded.get(key)
        if isinstance(default_value, bool):
            if isinstance(value, bool):
                config[key] = value
        elif isinstance(value, int) and value > 0:
            config[key] = value

    return config


def load_auth_state():
    state = {"api_id": None, "api_hash": None}
    if not AUTH_FILE.exists():
        return state

    try:
        loaded = json.loads(AUTH_FILE.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            state.update(loaded)
    except (OSError, json.JSONDecodeError):
        pass

    return state


def save_auth_state(state):
    AUTH_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTH_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def load_auth_credentials():
    state = load_auth_state()
    if not all([state.get("api_id"), state.get("api_hash")]):
        raise SystemExit("Missing Telegram API credentials in auth/telegram.json")
    return state


def load_skip_ids():
    if not SKIP_FILE.exists():
        return set()

    try:
        return {
            line.strip()
            for line in SKIP_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        }
    except OSError:
        return set()


async def _auth_qr(client):
    print("Scan the QR code: Telegram -> Settings -> Devices -> Scan QR\n")
    qr_login = await client.qr_login()
    qr = qrcode.QRCode(box_size=1, border=1)
    qr.add_data(qr_login.url)
    qr.make()
    buf = StringIO()
    qr.print_ascii(out=buf)
    buf.seek(0)
    print(buf.read())
    try:
        await qr_login.wait()
        return True
    except SessionPasswordNeededError:
        await client.sign_in(password=getpass.getpass("2FA password: "))
        return True
    except Exception as err:
        print(f"QR auth failed: {err}", file=sys.stderr)
        return False


async def ensure_authorized_client(session_file):
    state = load_auth_state()
    if not all([state.get("api_id"), state.get("api_hash")]):
        print("API Configuration Required (https://my.telegram.org)")
        try:
            state["api_id"] = int(input("Enter your API ID: "))
            state["api_hash"] = input("Enter your API Hash: ")
            save_auth_state(state)
        except ValueError:
            print("Invalid API ID. Must be a number.", file=sys.stderr)
            raise SystemExit(1)

    client = TelegramClient(str(session_file), state["api_id"], state["api_hash"])
    await client.connect()

    if not await client.is_user_authorized():
        if not await _auth_qr(client):
            print("Authentication failed.", file=sys.stderr)
            await client.disconnect()
            raise SystemExit(1)

    return client

#!/usr/bin/env python3
"""
Posts the game currently running on a MiSTer to a Discord channel.

Data source: Zaparoo Core's local HTTP API on the MiSTer (default port 7497).
  - On startup it asks Zaparoo what is running right now (JSON-RPC `media.active`).
  - Then it listens to Zaparoo's event stream (SSE, `/api/v0.1/events`) for
    `media.started` / `media.stopped` and posts each change to a Discord webhook.

Nothing is installed on the MiSTer and no login/SSH is used. Zaparoo must allow
this PC in its config (see README: `allowed_ips` under `[service]`).
Standard library only; Python 3.8+.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

RECONNECT_DELAY_SECONDS = 5
HTTP_TIMEOUT_SECONDS = 10
API_PATH = "/api/v0.1"


def load_config():
    config = {}
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

    host = os.environ.get("ZAPAROO_HOST", config.get("zaparoo_host", "")).rstrip("/")
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", config.get("discord_webhook_url", ""))

    if not host:
        sys.exit("Missing zaparoo_host (config.json or ZAPAROO_HOST env var)")
    if not webhook or webhook.startswith("<"):
        sys.exit("Missing discord_webhook_url (config.json or DISCORD_WEBHOOK_URL env var)")

    return host, webhook


def zaparoo_rpc(host, method):
    """Single JSON-RPC call to Zaparoo Core. Returns the `result` object or None."""
    body = json.dumps({"jsonrpc": "2.0", "method": method, "id": 1}).encode("utf-8")
    req = urllib.request.Request(
        host + API_PATH,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
        reply = json.loads(resp.read())
    return reply.get("result")


def post_to_discord(webhook_url, message):
    body = json.dumps({"content": message}).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT_SECONDS) as resp:
            resp.read()
    except urllib.error.HTTPError as e:
        print(f"[discord] webhook post failed: HTTP {e.code}")
    except urllib.error.URLError as e:
        print(f"[discord] webhook post failed: {e}")


def game_name(params):
    return params.get("mediaName") or params.get("name") or params.get("mediaPath") or params.get("path")


def format_started(params):
    name = game_name(params) or "Unknown game"
    system = params.get("systemName") or params.get("systemId")
    if system:
        return f"🎮 Now playing on MiSTer: **{name}** ({system})"
    return f"🎮 Now playing on MiSTer: **{name}**"


def format_stopped(params):
    name = game_name(params)
    if name:
        return f"⏹️ Stopped: **{name}**"
    return "⏹️ MiSTer game stopped"


def seed_current_game(host):
    """Return the name of whatever Zaparoo reports as active right now, or None."""
    active = zaparoo_rpc(host, "media.active")
    if not active:
        return None
    return game_name(active)


def listen(host, webhook_url, last_name):
    url = host + API_PATH + "/events"
    print(f"[zaparoo] connecting to {url}")
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})

    with urllib.request.urlopen(req) as resp:
        print("[zaparoo] connected, listening for media events")
        for raw_line in resp:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if not payload:
                continue
            try:
                event = json.loads(payload)
            except json.JSONDecodeError:
                continue

            method = event.get("method")
            params = event.get("params") or {}

            if method == "media.started":
                name = game_name(params)
                if name == last_name:
                    continue
                last_name = name
                message = format_started(params)
                print(f"[event] {message}")
                post_to_discord(webhook_url, message)
            elif method == "media.stopped":
                last_name = None
                message = format_stopped(params)
                print(f"[event] {message}")
                post_to_discord(webhook_url, message)


def main():
    host, webhook_url = load_config()
    while True:
        try:
            # Re-seed on every (re)connect so a missed event never leaves us stale.
            # The seeded game is NOT posted; only later changes are.
            current = seed_current_game(host)
            if current:
                print(f"[zaparoo] currently running: {current} (not posted; waiting for a change)")
            listen(host, webhook_url, current)
        except KeyboardInterrupt:
            print("\nStopping.")
            return
        except (urllib.error.URLError, urllib.error.HTTPError, ConnectionError, OSError) as e:
            print(f"[zaparoo] connection lost ({e}), retrying in {RECONNECT_DELAY_SECONDS}s")
            time.sleep(RECONNECT_DELAY_SECONDS)


if __name__ == "__main__":
    main()

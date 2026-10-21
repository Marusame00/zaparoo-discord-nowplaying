#!/usr/bin/env python3
"""
Shows the MiSTer game you are playing as your Discord Rich Presence status.

  Discord status:  Playing <Application name>
                   <details>   e.g. Playstation · Final Fantasy Viii
                   <state>     e.g. on MiSTer

Data source: Zaparoo Core's local HTTP API on the MiSTer (default port 7497).
  - On startup and on every reconnect it asks Zaparoo what is running
    (JSON-RPC `media.active`).
  - It then follows `media.started` / `media.stopped` from Zaparoo's event
    stream (SSE, `/api/v0.1/events`) and updates your status to match.

Output goes to the local Discord desktop app over its IPC named pipe. No channel,
webhook, or bot is involved. The Discord desktop app must be running on this PC.
Standard library only; Python 3.8+ on Windows.
"""

import datetime
import json
import os
import re
import struct
import sys
import time
import urllib.error
import urllib.request
import uuid

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

RECONNECT_DELAY_SECONDS = 5
HTTP_TIMEOUT_SECONDS = 10
API_PATH = "/api/v0.1"

# Discord IPC opcodes
OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2

DISCORD_PIPES = [rf"\\.\pipe\discord-ipc-{i}" for i in range(10)]


# ---------------------------------------------------------------- config

def load_config():
    config = {}
    if os.path.isfile(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)

    host = os.environ.get("ZAPAROO_HOST", config.get("zaparoo_host", "")).rstrip("/")
    client_id = os.environ.get("DISCORD_CLIENT_ID", config.get("discord_client_id", ""))

    if not host:
        sys.exit("Missing zaparoo_host (config.json or ZAPAROO_HOST env var)")
    if not client_id or client_id.startswith("<"):
        sys.exit("Missing discord_client_id (config.json or DISCORD_CLIENT_ID env var)")

    return host, str(client_id)


# ---------------------------------------------------------------- Zaparoo

def zaparoo_rpc(host, method):
    """One JSON-RPC call to Zaparoo Core. Returns the `result` object or None."""
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


def parse_zaparoo_time(text):
    """Zaparoo sends RFC3339 with nanoseconds; trim to microseconds for Python."""
    if not text:
        return None
    m = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?(.*)$", text)
    if not m:
        return None
    frac = (m.group(2) or "")[:7]  # "." + up to 6 digits
    try:
        dt = datetime.datetime.fromisoformat(m.group(1) + frac + m.group(3))
    except ValueError:
        return None
    return dt.timestamp()


def media_info(params):
    """Normalise a Zaparoo media object into what we show. Returns None if empty."""
    name = params.get("mediaName") or params.get("name")
    if not name:
        return None
    return {
        "game": name,
        "system": params.get("systemName") or params.get("systemId") or "",
        "started": parse_zaparoo_time(params.get("started")) or time.time(),
    }


def same_game(a, b):
    return a is not None and b is not None and a["game"] == b["game"] and a["system"] == b["system"]


# ---------------------------------------------------------------- Discord IPC

class DiscordIPC:
    """Minimal client for Discord's local IPC pipe (Windows named pipe)."""

    def __init__(self, client_id):
        self.client_id = client_id
        self.pipe = None

    def connect(self):
        last_error = None
        for path in DISCORD_PIPES:
            try:
                self.pipe = open(path, "r+b", buffering=0)
                break
            except OSError as e:
                last_error = e
        if self.pipe is None:
            raise ConnectionError(f"Discord is not running or IPC unavailable ({last_error})")

        self._send(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id})
        opcode, reply = self._recv()
        if reply.get("evt") == "ERROR":
            self.close()
            raise ConnectionError(f"Discord rejected handshake: {reply.get('data', {}).get('message')}")

    def set_activity(self, activity):
        self._command("SET_ACTIVITY", {"pid": os.getpid(), "activity": activity})

    def clear_activity(self):
        self._command("SET_ACTIVITY", {"pid": os.getpid(), "activity": None})

    def close(self):
        if self.pipe is not None:
            try:
                self._send(OP_CLOSE, {})
            except OSError:
                pass
            try:
                self.pipe.close()
            finally:
                self.pipe = None

    def _command(self, cmd, args):
        self._send(OP_FRAME, {"cmd": cmd, "args": args, "nonce": str(uuid.uuid4())})
        _, reply = self._recv()
        if reply.get("evt") == "ERROR":
            raise ConnectionError(f"Discord {cmd} failed: {reply.get('data', {}).get('message')}")

    def _send(self, opcode, payload):
        data = json.dumps(payload).encode("utf-8")
        self.pipe.write(struct.pack("<II", opcode, len(data)) + data)

    def _recv(self):
        header = self._read_exact(8)
        opcode, length = struct.unpack("<II", header)
        body = self._read_exact(length) if length else b""
        return opcode, json.loads(body) if body else {}

    def _read_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.pipe.read(n - len(buf))
            if not chunk:
                raise ConnectionError("Discord closed the IPC pipe")
            buf += chunk
        return buf


def build_activity(info):
    return {
        "details": f"{info['system']} · {info['game']}" if info["system"] else info["game"],
        "state": "on MiSTer",
        "timestamps": {"start": int(info["started"])},
    }


# ---------------------------------------------------------------- main loop

def run_session(host, ipc):
    """Connect to Zaparoo and follow events until something breaks."""
    url = host + API_PATH + "/events"
    current = media_info(zaparoo_rpc(host, "media.active") or {})
    if current:
        ipc.set_activity(build_activity(current))
        print(f"[status] {current['system']} · {current['game']}")
    else:
        ipc.clear_activity()
        print("[status] nothing running")

    print(f"[zaparoo] listening on {url}")
    req = urllib.request.Request(url, headers={"Accept": "text/event-stream"})
    with urllib.request.urlopen(req) as resp:
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
                info = media_info(params)
                if info and not same_game(info, current):
                    current = info
                    ipc.set_activity(build_activity(info))
                    print(f"[status] {info['system']} · {info['game']}")
            elif method == "media.stopped":
                if current is not None:
                    current = None
                    ipc.clear_activity()
                    print("[status] cleared")


def main():
    host, client_id = load_config()
    ipc = DiscordIPC(client_id)
    while True:
        try:
            ipc.connect()
            print("[discord] connected")
            run_session(host, ipc)
        except KeyboardInterrupt:
            print("\nStopping.")
            ipc.close()
            return
        except (ConnectionError, urllib.error.URLError, OSError) as e:
            print(f"[retry] {e}; retrying in {RECONNECT_DELAY_SECONDS}s")
            ipc.close()
            time.sleep(RECONNECT_DELAY_SECONDS)


if __name__ == "__main__":
    main()

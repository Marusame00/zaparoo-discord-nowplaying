# zaparoo-discord-nowplaying

Shows the game you are playing on your MiSTer as your **Discord status** (Rich
Presence), using Zaparoo Core for the game data.

```
Playing MiSTer                      <- Discord application name
Playstation · Final Fantasy Viii    <- details
on MiSTer                           <- state (elapsed timer shown)
```

Nothing is posted to a channel. No webhook, server, or bot is needed. Your status
updates when the game changes and clears when it stops.

## How it works

1. Asks Zaparoo Core on the MiSTer what is running (`media.active`). It asks again on
   every reconnect.
2. Follows Zaparoo's event stream (`/api/v0.1/events`) for `media.started` and
   `media.stopped`.
3. Sends the change to the Discord desktop app on this PC over its local IPC pipe.

The MiSTer is not modified. There is no SSH and no login on the MiSTer.

## Requirements

- Zaparoo Core running on the MiSTer.
- Windows PC on the same LAN, with the **Discord desktop app open**. Discord ignores
  status from a closed app.
- Python 3.8+. No pip packages.

## Setup

### 1. Allow your PC in Zaparoo

Zaparoo rejects remote API requests by default (`403 remote access disabled for this
transport`). Add your PC's LAN IP under `[service]` in `Y:\zaparoo\config.toml`:

```toml
[service]
allowed_ips = ["192.168.0.11"]   # the PC that runs this script
```

Restart Zaparoo afterwards. Hot reload did not pick up the change during testing. You
can restart it from the MiSTer Scripts menu (`zaparoo`) or reboot.

Check from the PC. You should get JSON back, not 403:

```
curl -X POST http://<mister-ip>:7497/api/v0.1 -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"media.active\",\"id\":1}"
```

### 2. Create a Discord application

1. Go to https://discord.com/developers/applications and click **New Application**.
2. Name it **MiSTer**. This is the word after "Playing" on your status.
3. On **General Information**, copy the **Application ID**. This is your client ID.

You can change the name later from the same page.

### 3. Configure

```
copy config.example.json config.json
```

Edit `config.json`:

- `zaparoo_host`: `http://<mister-ip>:7497`
- `discord_client_id`: the Application ID from step 2

`config.json` is git-ignored. The environment variables `ZAPAROO_HOST` and
`DISCORD_CLIENT_ID` also work.

### 4. Run

```
python zaparoo_discord_nowplaying.py
```

Leave it running. It reconnects if Discord restarts, the MiSTer reboots, or the network
drops. To run it at login, put a shortcut to it in `shell:startup`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `Discord is not running or IPC unavailable` | Start the Discord desktop app. |
| `Discord closed the IPC pipe` right after connecting | The client ID is wrong or not from your application. |
| `403 remote access disabled` | Your PC's IP is not in `allowed_ips`, or Zaparoo was not restarted. |
| Status does not show | Discord settings -> Activity Privacy -> "Display current activity" must be on. |

## Limitations

- Discord's status header is the **application name**, which is set once per
  application in the developer portal. It cannot change per game, so it always reads
  "Playing MiSTer". The per-game part is the details line, which is
  `system · game`.
- Only changes made while the script runs are shown. A game already running at startup
  is shown with the time it started, which is taken from Zaparoo when available.
- Built against Zaparoo Core's documented API and Discord's IPC protocol. Verify both
  again if either changes.

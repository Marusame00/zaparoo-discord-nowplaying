# zaparoo-discord-nowplaying

Posts a Discord message whenever the game running on your MiSTer changes.

It reads the game state from **Zaparoo Core**, which runs on the MiSTer and
exposes an API on your local network (default port `7497`). The script:

1. Asks Zaparoo what is running right now (`media.active`). This is not posted, so you
   only get messages for changes.
2. Listens to Zaparoo's event stream (`/api/v0.1/events`) for `media.started` and
   `media.stopped`, and posts each change to a Discord webhook.

Nothing is installed on the MiSTer. There is no SSH and no login on the MiSTer. The
script only reads from Zaparoo's HTTP API.

## Requirements

- Zaparoo Core running on the MiSTer, with its config at `Y:\zaparoo\config.toml`.
- Python 3.8+ on a PC on the same LAN. No pip packages are needed.
- A Discord channel webhook.

## Setup

### 1. Allow your PC in Zaparoo

Zaparoo rejects remote API requests by default with `remote access disabled for this
transport` (HTTP 403). Add your PC's LAN IP to `[service]` in `config.toml`:

```toml
[service]
api_port = 7497
allowed_ips = ["192.168.0.11"]   # the PC that runs this script
```

Restart the Zaparoo service after editing. Hot reload did not pick up the change in
testing. On the MiSTer you can restart it from the Scripts menu (`zaparoo`), or
reboot the MiSTer.

Check that it works from the PC. This should return JSON, not 403:

```
curl -X POST http://<mister-ip>:7497/api/v0.1 -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"media.active\",\"id\":1}"
```

### 2. Create a Discord webhook

Channel settings -> Integrations -> Webhooks -> New Webhook -> Copy Webhook URL.

### 3. Configure

```
copy config.example.json config.json
```

Edit `config.json`:

- `zaparoo_host`: `http://<mister-ip>:7497`
- `discord_webhook_url`: the webhook URL from step 2

`config.json` is git-ignored because it holds a live webhook secret. Do not commit
it. You can also set the `ZAPAROO_HOST` and `DISCORD_WEBHOOK_URL` environment
variables instead of using the file.

### 4. Run

```
python zaparoo_discord_nowplaying.py
```

Leave it running. It reconnects automatically if the MiSTer reboots or the network
drops. To run it at login on Windows, add a shortcut to `shell:startup`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `403 remote access disabled for this transport` | Your PC's IP is not in `allowed_ips`, or Zaparoo was not restarted. |
| `connection lost ... retrying` in a loop | Wrong IP or port, or the MiSTer is off. Open `http://<mister-ip>:7497/app/` in a browser to check. |
| Nothing posts when you change games | Confirm the `[event]` lines appear in the console. Check the webhook URL is correct. |

## Limitations

- Only changes made while the script is running are posted. The game that is already
  running at startup is shown in the console but not posted.
- The `media.stopped` event is handled, but it has not been seen fire on real
  hardware yet, so it is not confirmed.
- Written against Zaparoo Core's API as documented. Check `zaparoo.org/docs/core/api/`
  if a future Zaparoo release changes the event format.

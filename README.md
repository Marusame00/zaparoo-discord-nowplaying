# zaparoo-discord-nowplaying

Shows the game you are playing on your MiSTer as your **Discord status** (Rich
Presence), with the MiSTer logo, using Zaparoo Core for the game data.

```
Playing MiSTer                      <- Discord application name + logo
Playstation · Final Fantasy Viii    <- details (system · game)
on MiSTer                           <- state (with an elapsed timer)
```

This is a status on your own profile, not a channel message. There is no bot, no
webhook, and nothing posted anywhere. It only updates a field that is already part
of your Discord account (your current activity).

## Is this for you?

- You want friends to see what you are playing on MiSTer without you doing anything
  once it is running.
- You are fine leaving a small script running in the background on a PC while you
  play, and Discord open on that same PC (Discord does not show a status for an app
  that is not open).
- You do not need this if you only want to tell friends manually, or if you never
  have Discord open while gaming — Rich Presence cannot work without Discord running
  on the same machine.

## How it works, and why each piece exists

| Piece | What it does | Why it is needed |
|---|---|---|
| **Zaparoo Core** (on the MiSTer) | Tracks which game/core is active and exposes it over HTTP on your LAN. | This script does not talk to the MiSTer directly — Zaparoo is the thing that already knows what is running and answers questions about it. No Zaparoo, no game data. |
| **This script** (on a PC) | Asks Zaparoo what's running, then listens for change events (`media.started` / `media.stopped`). | Something has to sit in the middle: Zaparoo does not talk to Discord, and Discord does not talk to Zaparoo. |
| **Discord desktop app** (on the same PC) | Receives the status update from this script over a local connection and displays it. | Rich Presence is a *local* Discord feature — only the Discord app running on your own PC can set your status this way. There's no remote/cloud path for it. |
| **Discord "Application"** (discord.com, one-time) | A registered ID that identifies which name and logo your status uses. | Discord requires every Rich Presence update to say which registered app it's coming from — that's where the "MiSTer" name and logo are attached. |

## Requirements

- Zaparoo Core running on the MiSTer (you already have this if you use Zaparoo).
- A Windows PC on the same local network as the MiSTer, with the **Discord desktop
  app open** on it.
- Python 3.8 or newer on that PC. No extra packages to install — only Python's
  standard library is used.

## Setup

### 1. Let your PC reach Zaparoo

Zaparoo blocks API requests from other devices by default — it returns `403 remote
access disabled for this transport` unless you explicitly trust the requesting
device. This is a one-time setting on the MiSTer, not something you repeat per game
or per run.

Edit `Y:\zaparoo\config.toml` (`Y:` is the MiSTer's SD card over the network share;
adjust if yours is mapped differently) and add your PC's LAN IP address:

```toml
[service]
allowed_ips = ["192.168.0.11"]   # the PC that will run this script
```

Then restart the Zaparoo service so the change takes effect — editing the file alone
is not enough, Zaparoo does not reload it live. Restart it from the MiSTer's Scripts
menu (`zaparoo`), or reboot the MiSTer.

To confirm it worked, run this from the PC. If you get JSON back instead of a `403`
error, it's allowed:

```
curl -X POST http://<mister-ip>:7497/api/v0.1 -H "Content-Type: application/json" -d "{\"jsonrpc\":\"2.0\",\"method\":\"media.active\",\"id\":1}"
```

### 2. Get a Discord Application ID

This is the "Why this isn't totally plug-and-play" step. Discord requires a
registered Application ID before it will show Rich Presence at all, because that ID
is what carries the "MiSTer" name and logo.

You have two options:

- **Easiest: reuse the shared one.** `config.example.json` already ships with a
  public Application ID (`1562535128549429289`) registered as "MiSTer" with the
  MiSTer logo already uploaded. You can use it as-is and skip straight to step 3 —
  there's nothing private about an Application ID, it's just a label, not a
  credential.
- **Optional: make your own.** Only do this if you want a different name/logo than
  "MiSTer", or you'd rather not depend on someone else's registration staying up:
  1. Go to https://discord.com/developers/applications and click **New
     Application**.
  2. Name it whatever you want the status to say after "Playing".
  3. Under **Rich Presence -> Art Assets**, upload a square-ish logo and give it the
     key name `mister` (or change `LARGE_IMAGE_KEY` in the script to match whatever
     key you choose).
  4. Fill in a short **Description** on the General Information page if others might
     use this Application ID too — Discord's app listings look unfinished with a
     blank description, and it's shown if anyone looks the app up. Something like:
     *"Shows what game is running on a MiSTer FPGA, via Zaparoo. Not a bot — only
     used locally for Rich Presence status."* works fine.
  5. Copy the **Application ID** from the same page.

### 3. Configure this script

```
copy config.example.json config.json
```

Edit `config.json`:

- `zaparoo_host`: `http://<mister-ip>:7497`
- `discord_client_id`: leave the shared ID, or paste your own from step 2

`config.json` is git-ignored on purpose — it's your personal settings file, not
something to commit. (Note: neither value in it is actually secret; there's no API
key or password involved anywhere in this setup.) You can also set the
`ZAPAROO_HOST` and `DISCORD_CLIENT_ID` environment variables instead of using the
file, if you prefer.

### 4. Run it

```
python zaparoo_discord_nowplaying.py
```

Leave the window open while you play. It automatically reconnects if Discord
restarts, the MiSTer reboots, or the network drops — you don't need to restart it
yourself for those.

To have it start automatically when you log into Windows, put a shortcut to it in
the `shell:startup` folder (type that into the Windows Run dialog to open it).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `Discord is not running or IPC unavailable` | The Discord desktop app isn't open on this PC. |
| `Discord closed the IPC pipe` right after connecting | The `discord_client_id` is wrong, or doesn't match a real Application. |
| `403 remote access disabled` | Your PC's IP isn't in Zaparoo's `allowed_ips`, or Zaparoo wasn't restarted after you edited it. |
| Status never appears, no errors | Discord Settings -> Activity Privacy -> "Display current activity as a status message" is turned off. |
| Logo still shows "?" | Art asset uploads can take a few minutes to propagate after saving in the developer portal. |

## Limitations

- Discord's "Playing ___" header comes from the Application's registered name and
  can't change per game — it will always say "Playing MiSTer" (or whatever name the
  Application ID you used was given). The game itself shows on the line below
  (`system · game`), which does change per game.
- Only changes made while the script is actually running get shown. If a game was
  already running before you started the script, it is picked up and shown once
  (with its real start time from Zaparoo, so the elapsed timer is still accurate),
  but you won't see the "started" transition for it.
- Built against Zaparoo Core's documented API and Discord's local IPC protocol as of
  writing. If either changes its behavior in a future update, this may need
  adjusting.

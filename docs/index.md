# Spotify Display

A Raspberry Pi that shows what's playing on Spotify on a 3.5" TFT screen. Album art on the left with a blurred colour-matched background, track/artist/album scrolling on the right, progress bar at the bottom. When nothing's playing it falls back to a clock. After 5 minutes idle it dims into a slow drifting screensaver to avoid burn-in.

Deployed via Ansible - flash an SD card, fill in your credentials, run the playbook.

---

<p align="center">
<img src="https://github.com/user-attachments/assets/72b68a01-391b-47c1-a21d-d362d126a549" alt="spotify-pi-display" width="600">
</p>

---
## Hardware

- Raspberry Pi (tested on Raspberry Pi Zero 2 WH) - [Amazon](https://amzn.eu/d/05L8Rk97)
- 3.5" SPI TFT display, PiScreen / ILI9486 (uses the `piscreen` overlay at 480×320) - [Amazon](https://amzn.eu/d/0a0KBdTW)
- Case - [Amazon](https://amzn.eu/d/0abvhrHq) / [STL on Thingiverse](https://www.thingiverse.com/thing:7004025)
- MicroSD card, 8 GB+, flashed with Raspberry Pi OS Lite (Bookworm recommended)

---

## First-time setup

On first boot the Pi starts a hotspot called `SpotifyDisplay` (password `setup1234`). Connect to it and go to `https://192.168.4.1`, or just scan the QR code on the screen.

The portal walks you through two steps:
1. Enter your home WiFi credentials - the Pi connects in the background, the hotspot drops, and the screen shows a new QR code
2. Scan that to open the Spotify auth page on your home network (`https://spotifydisplay.local/spotify`), log in, accept the certificate warning

After that it reboots and starts displaying tracks.

---

## Prerequisites

On your machine: Python 3, pip, Ansible (`pip install ansible`)

On the Pi: fresh Raspberry Pi OS Lite, SSH enabled, a user with sudo. That's it.

---

## Getting started

**1. Clone the repo**

```bash
git clone https://github.com/YOUR_USERNAME/spotify-display-ansible.git
cd spotify-display-ansible
```

**2. Create a Spotify app**

Head to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), create an app, and add this as a Redirect URI:

```
https://spotifydisplay.local/callback
```

Grab the Client ID and Client Secret.

**3. Fill in your details**

`group_vars/all.yml`:

```yaml
app_dir: /home/YOUR_USERNAME/spotify-display

spotify_client_id: "YOUR_SPOTIFY_CLIENT_ID"
spotify_client_secret: "YOUR_SPOTIFY_CLIENT_SECRET"

portal_pin: "YOUR_PORTAL_PIN"
```

`inventory.ini`:

```ini
[raspberrypi]
pinode1 ansible_host=YOUR_PI_IP ansible_user=YOUR_USERNAME ansible_password=YOUR_PASSWORD ansible_become_password=YOUR_PASSWORD ansible_python_interpreter=/usr/bin/python3
```

The Pi's IP is in your router's DHCP table on first boot. After the first deploy you can switch `ansible_host` to `spotifydisplay.local`.

**4. Run it**

```bash
ansible-playbook -i inventory.ini playbook.yml
```

Takes 5–10 minutes. It'll reboot the Pi at the end.

---

## Day-to-day

Once set up, there's a management portal at `https://spotifydisplay.local`. It shows the current track and service status and lets you:

- Change WiFi network
- Re-authorise Spotify (without a full reset)
- View the last 60 lines of logs
- Reset back to first-time setup mode

Access is PIN-protected - whatever you set in `portal_pin`.

---

## Playbook tags

Useful if you've already done the initial setup and just want to push updated scripts or restart services:

```bash
# just copy the Python files and restart
ansible-playbook -i inventory.ini playbook.yml --tags deploy,services

# just reinstall packages
ansible-playbook -i inventory.ini playbook.yml --tags packages
```

| Tag | What it touches |
|---|---|
| `packages` | apt + pip installs |
| `config` | display overlay, WiFi, SSL cert, system config |
| `deploy` | copies Python scripts to the Pi |
| `services` | installs/enables systemd services |

---

## Resetting

From the portal: **Reset to Setup Mode** - clears the token and saved WiFi, reboots. Hotspot comes back up.

Via Ansible (if you can't reach the portal):

```bash
ansible-playbook -i inventory.ini reset.yml
```

---

## Display states

| State | Display |
|---|---|
| Playing | Album art, track info, progress bar |
| Paused | Same but dimmed, "PAUSED" at the bottom |
| Idle | Clock and date on a dark background |
| Screensaver (5 min) | Dim drifting clock |
| No internet | Dark red |
| Rate limited | Blue with a countdown |
| Token expired | Amber - auto-refresh attempted |

State transitions cross-fade. The progress bar interpolates between API polls so it moves smoothly rather than jumping every 2 seconds.

---

## File layout

```
├── playbook.yml
├── reset.yml
├── inventory.ini              ← contains your credentials
├── group_vars/
│   └── all.yml
├── files/
│   ├── spotify_display.py     ← main display loop, writes to /dev/fb1
│   ├── setup_display.py       ← animated TFT UI during setup
│   ├── setup_portal.py        ← Flask portal for WiFi + Spotify OAuth
│   └── manage_portal.py       ← Flask management portal post-setup
└── templates/
    └── spotify-display-service.j2
```

Five systemd services run on the Pi. Setup services (`qr-display`, `setup-portal`, `spotify-hotspot`) only run until `/etc/spotify_display_configured` exists. The display and management services (`spotify-display`, `manage-portal`) only run after that file is created.

---

## A few things worth knowing

- Credentials go into `/etc/spotify_display.env` with `600` permissions - only root can read them
- The SSL cert is self-signed so your browser will complain. That's expected, just accept it
- The hotspot password (`setup1234`) is weak by design - it's only up for the few minutes it takes to do first-time setup, then it's gone
- `inventory.ini` has your Pi password in plaintext. It's in `.gitignore` - don't commit it

---

## Updating

No OTA yet. SSH in and copy the updated files, then:

```bash
sudo systemctl restart spotify-display manage-portal
```

Or use `--tags deploy,services` with the playbook.

---

## Troubleshooting

**Hotspot doesn't show up** - wait a full minute, NetworkManager takes a moment. If it still doesn't appear: `systemctl status spotify-hotspot setup-portal qr-display`

**Can't reach the portal after WiFi setup** - make sure your device is back on your home network, not still on the SpotifyDisplay hotspot. Try `https://spotifydisplay.local/spotify` first; if mDNS isn't working, grab the Pi's IP from your router.

**"No auth token - rescan QR"** - the OAuth flow didn't finish. Run `reset.yml` and start again.

**"Token expired" on screen** - it'll try to refresh automatically. If it keeps happening, use Re-authorise Spotify in the portal.

**TFT blank or wrong colours** - this only works with the PiScreen/ILI9486 using the `piscreen` overlay. Other displays need a different `dtoverlay` in `playbook.yml`. Check SPI is on with `ls /dev/spidev*`.

---

Built with [Spotipy](https://spotipy.readthedocs.io/), [Pillow](https://python-pillow.org/), [Flask](https://flask.palletsprojects.com/), and [qrcode](https://github.com/lincolnloop/python-qrcode).

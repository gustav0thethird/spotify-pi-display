#!/usr/bin/env python3
"""
Two-phase Spotify Display setup portal.

Phase 1 — hotspot (192.168.4.1):
  User enters home WiFi credentials.
  Portal connects Pi to home WiFi in background, polls for result.
  On success: renders Phase 2 QR on TFT, shows IP for Android fallback.
  On failure: restores hotspot so user can try again.

Phase 2 — home network (spotifydisplay.local or home IP):
  /spotify  → Spotify OAuth redirect
  /callback → token exchange → save → reboot
"""
import json
import os
import subprocess
import threading
import time
import urllib.parse

import requests as http
from flask import Flask, jsonify, redirect, request, session


app = Flask(__name__)

# Stable session secret derived from machine ID so restarts don't invalidate sessions
try:
    with open("/etc/machine-id") as f:
        app.secret_key = f.read().strip()
except Exception:
    app.secret_key = "spotify-display-fallback-key"

TEST_MODE = os.environ.get("TEST_MODE") == "1"
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
REDIRECT_URI = (
    "http://127.0.0.1:5000/callback"
    if TEST_MODE
    else "https://spotifydisplay.local/callback"
)
SCOPE = "user-read-currently-playing"
CACHE_PATH = "./test_spotify_cache.json" if TEST_MODE else "/srv/.spotify_cache"

# ---------------------------------------------------------------------------
# WiFi connection state (shared between background thread and /wifi-status)
# ---------------------------------------------------------------------------
_wifi = {"status": "idle", "ip": None, "error": None}
_wifi_lock = threading.Lock()


def _set_wifi(status, ip=None, error=None):
    with _wifi_lock:
        _wifi["status"] = status
        _wifi["ip"] = ip
        _wifi["error"] = error


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PAGE = """<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Spotify Display Setup</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0a0a14;color:#e2e8f0;font-family:sans-serif;min-height:100vh;
         display:flex;align-items:center;justify-content:center;padding:20px}}
    .card{{background:#111827;border:1px solid #1a2035;border-radius:12px;
           padding:32px;max-width:440px;width:100%}}
    .logo{{color:#1DB954;font-size:.85em;font-weight:bold;letter-spacing:3px;
           text-transform:uppercase;margin-bottom:24px}}
    h2{{font-size:1.35em;margin-bottom:8px}}
    p{{color:#8892a4;font-size:.9em;margin-bottom:16px;line-height:1.55}}
    label{{display:block;color:#8892a4;font-size:.85em;margin-bottom:4px}}
    input{{width:100%;padding:10px 12px;margin-bottom:14px;font-size:1em;
           border-radius:6px;border:1px solid #1a2035;background:#0d1117;color:#e2e8f0}}
    input:focus{{outline:none;border-color:#1DB954}}
    button{{width:100%;background:#1DB954;color:#fff;border:none;cursor:pointer;
            padding:13px;font-size:1em;font-weight:bold;border-radius:6px}}
    button:hover{{background:#17a348}}
    .note{{color:#4b5563;font-size:.82em;line-height:1.5}}
    .err{{color:#f87171;font-size:.9em;margin-bottom:12px}}
    ol{{padding-left:1.4em;color:#8892a4;margin-bottom:16px}}
    li{{margin-bottom:8px}}
    a{{color:#1DB954;text-decoration:none}}
    a:hover{{text-decoration:underline}}
    strong{{color:#e2e8f0}}
    h3{{color:#1DB954;margin-bottom:10px}}
    .net-list{{max-height:200px;overflow-y:auto;margin-bottom:14px;border-radius:6px;
               border:1px solid #1a2035}}
    .net-item{{display:flex;justify-content:space-between;align-items:center;
               padding:10px 12px;cursor:pointer;border-bottom:1px solid #1a2035;
               font-size:.9em;transition:background .15s}}
    .net-item:last-child{{border-bottom:none}}
    .net-item:hover,.net-item.selected{{background:#1DB95420;color:#e2e8f0}}
    .net-item.selected{{border-left:3px solid #1DB954}}
    .net-ssid{{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
    .net-meta{{display:flex;align-items:center;gap:8px;flex-shrink:0}}
    .net-lock{{color:#8892a4;font-size:.8em}}
    .net-signal{{color:#1DB954;font-size:.75em;letter-spacing:-1px}}
  </style>
</head>
<body><div class="card">
  <div class="logo">&#9654; Spotify Display</div>
  {body}
</div></body>
</html>"""


def _page(body):
    return PAGE.format(body=body)


def _get_home_ip(timeout=25):
    """Poll wlan0 for a non-hotspot IP address."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            out = subprocess.run(
                ["ip", "-4", "addr", "show", "wlan0"],
                capture_output=True, text=True,
            ).stdout
            for line in out.splitlines():
                line = line.strip()
                if line.startswith("inet "):
                    ip = line.split()[1].split("/")[0]
                    if not ip.startswith("192.168.4."):
                        return ip
        except Exception:
            pass
        time.sleep(1)
    return None


# ---------------------------------------------------------------------------
# Phase 1 — WiFi credentials form + background connection
# ---------------------------------------------------------------------------

@app.route("/scan")
def scan_networks():
    if TEST_MODE:
        return jsonify([
            {"ssid": "TestNetwork", "signal": 82, "secured": True},
            {"ssid": "OpenNet",     "signal": 55, "secured": False},
        ])
    try:
        subprocess.run(
            ["nmcli", "dev", "wifi", "rescan", "ifname", "wlan0"],
            check=False, capture_output=True, timeout=5,
        )
    except Exception:
        pass
    try:
        result = subprocess.run(
            ["nmcli", "--escape", "no", "-t", "-f", "SSID,SIGNAL,SECURITY",
             "dev", "wifi", "list", "ifname", "wlan0"],
            capture_output=True, text=True, timeout=15,
        )
        seen = set()
        networks = []
        for line in result.stdout.splitlines():
            parts = line.rsplit(":", 2)
            if len(parts) < 2:
                continue
            ssid = parts[0].strip().lstrip("* ")
            if not ssid or ssid in seen:
                continue
            try:
                signal = int(parts[1])
            except ValueError:
                signal = 0
            security = parts[2].strip() if len(parts) > 2 else ""
            networks.append({"ssid": ssid, "signal": signal, "secured": bool(security)})
            seen.add(ssid)
        networks.sort(key=lambda x: x["signal"], reverse=True)
        return jsonify(networks)
    except Exception:
        return jsonify([])


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        with _wifi_lock:
            if _wifi["status"] == "connecting":
                return _page("<h2>Already connecting…</h2><p>Please wait.</p>")

        ssid = request.form.get("ssid", "").strip()
        password = request.form.get("password", "")
        if not ssid or not password:
            return _page("<h2>Connect to WiFi</h2><p>Enter your home network credentials so the display can reach Spotify.</p>" + _wifi_form("Please fill in both fields.")), 400

        if TEST_MODE:
            params = urllib.parse.urlencode({
                "client_id": CLIENT_ID,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "scope": SCOPE,
            })
            return redirect(f"https://accounts.spotify.com/authorize?{params}")

        _set_wifi("connecting")
        threading.Thread(
            target=_connect_home_wifi,
            args=(ssid, password),
            daemon=True,
        ).start()

        return _page(f"""
            <h2>Connecting to {ssid}&hellip;</h2>
            <p>Checking WiFi credentials &mdash; this takes about 15&nbsp;seconds.</p>
            <div id="msg"><p style="color:#8892a4">&#9203; Please wait&hellip;</p></div>
            <script>
            function poll() {{
                fetch('/wifi-status')
                    .then(r => r.json())
                    .then(d => {{
                        if (d.status === 'connected') {{
                            var primary = d.ip ? 'https://' + d.ip + '/spotify' : 'https://spotifydisplay.local/spotify';
                            document.getElementById('msg').innerHTML =
                                '<h3>&#10003; Connected!</h3>' +
                                '<ol>' +
                                '<li>Reconnect this device to <strong>{ssid}</strong></li>' +
                                '<li>Visit <a href="' + primary + '"><strong>' + primary + '</strong></a></li>' +
                                (d.ip ? '' : '<li>Or: <a href="https://spotifydisplay.local/spotify">https://spotifydisplay.local/spotify</a></li>') +
                                '</ol>' +
                                '<p class="note">Accept the browser security warning &mdash; the certificate is self-signed.</p>';
                        }} else if (d.status === 'failed') {{
                            document.getElementById('msg').innerHTML =
                                '<p class="err">&#10007; ' + (d.error || 'Could not connect') + '</p>' +
                                '<p>The hotspot is back up. <a href="/">Try again &rarr;</a></p>';
                        }} else {{
                            setTimeout(poll, 2000);
                        }}
                    }})
                    .catch(() => setTimeout(poll, 2000));
            }}
            setTimeout(poll, 2000);
            </script>
        """)

    return _page("<h2>Connect to WiFi</h2><p>Enter your home network credentials so the display can reach Spotify.</p>" + _wifi_form())


def _wifi_form(error=""):
    err = f"<p class='err'>{error}</p>" if error else ""
    return f"""{err}
        <div id="net-scan"><p style="color:#8892a4;font-size:.85em;text-align:center">
          &#9203; Scanning for networks&hellip;</p></div>
        <form method="post" id="wifi-form">
          <label>WiFi Name (SSID)</label>
          <input name="ssid" id="ssid-input" placeholder="Select a network above or type manually"
                 autocomplete="off" required>
          <label>Password</label>
          <input name="password" id="pw-input" type="password" autocomplete="off" required>
          <button type="submit">Connect to WiFi &rarr;</button>
        </form>
        <script>
        (function() {{
          fetch('/scan')
            .then(function(r) {{ return r.json(); }})
            .then(function(nets) {{
              var el = document.getElementById('net-scan');
              if (!nets || !nets.length) {{
                el.innerHTML = '<p style="color:#8892a4;font-size:.85em">No networks found &mdash; enter SSID manually.</p>';
                return;
              }}
              var html = '<label>Nearby Networks</label><div class="net-list">';
              nets.forEach(function(n) {{
                var s = n.signal;
                var bars = (s>=75?'&#9608;&#9608;&#9608;&#9608;':s>=50?'&#9608;&#9608;&#9608;&#9601;':s>=25?'&#9608;&#9608;&#9601;&#9601;':'&#9608;&#9601;&#9601;&#9601;');
                var lock = n.secured ? '<span class="net-lock">[lock]</span>' : '';
                var safe = n.ssid.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
                html += '<div class="net-item" onclick="selectNet(this,\'' + safe.replace(/'/g,'&#39;') + '\')">'
                      + '<span class="net-ssid">' + safe + '</span>'
                      + '<span class="net-meta">' + lock + '<span class="net-signal">' + bars + '</span></span>'
                      + '</div>';
              }});
              html += '</div>';
              el.innerHTML = html;
            }})
            .catch(function() {{
              document.getElementById('net-scan').innerHTML = '';
            }});
        }})();

        function selectNet(el, ssid) {{
          document.querySelectorAll('.net-item').forEach(function(i) {{
            i.classList.remove('selected');
          }});
          el.classList.add('selected');
          document.getElementById('ssid-input').value = ssid;
          document.getElementById('pw-input').focus();
        }}
        </script>"""


@app.route("/wifi-status")
def wifi_status():
    with _wifi_lock:
        return jsonify(dict(_wifi))


def _connect_home_wifi(ssid, password):
    """Connect Pi to home WiFi. On failure restore hotspot. Runs in background thread."""
    time.sleep(1)  # let Flask send the response first

    # Add the connection profile
    subprocess.run([
        "nmcli", "con", "add",
        "type", "wifi", "ifname", "wlan0",
        "con-name", "home-wifi",
        "ssid", ssid,
        "wifi-sec.key-mgmt", "wpa-psk",
        "wifi-sec.psk", password,
        "connection.autoconnect", "yes",
        "connection.autoconnect-priority", "10",
    ], check=False)

    # Drop hotspot and bring up home WiFi
    subprocess.run(["nmcli", "con", "down", "SpotifyDisplay-hotspot"], check=False)
    result = subprocess.run(
        ["nmcli", "--wait", "30", "con", "up", "home-wifi"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        subprocess.run(["nmcli", "con", "delete", "home-wifi"], check=False)
        subprocess.run(["nmcli", "con", "up", "SpotifyDisplay-hotspot"], check=False)
        _set_wifi("failed", error="Wrong password or network not found")
        return

    home_ip = _get_home_ip(timeout=15)
    _set_wifi("connected", ip=home_ip)

    # Regenerate SSL cert to include home IP — so browser doesn't reject on IP access
    if home_ip:
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", "/etc/ssl/spotify-display.key",
            "-out",    "/etc/ssl/spotify-display.crt",
            "-days", "3650", "-nodes",
            "-subj", f"/CN={home_ip}",
            "-addext", f"subjectAltName=IP:192.168.4.1,IP:{home_ip},DNS:spotifydisplay.local",
        ], check=False)
        # Restart Flask to load the new cert (delay lets /wifi-status response reach browser)
        threading.Timer(2.0, lambda: subprocess.run(
            ["systemctl", "restart", "setup-portal"], check=False
        )).start()


# ---------------------------------------------------------------------------
# Phase 2 — Spotify OAuth (Pi now has internet)
# ---------------------------------------------------------------------------

@app.route("/spotify")
def spotify_auth():
    redirect_uri = (
        "http://127.0.0.1:5000/callback"
        if TEST_MODE
        else "https://spotifydisplay.local/callback"
    )
    session["redirect_uri"] = redirect_uri
    params = urllib.parse.urlencode({
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": SCOPE,
    })
    return redirect(f"https://accounts.spotify.com/authorize?{params}")


@app.route("/callback")
def callback():
    code = request.args.get("code")
    error = request.args.get("error")

    if error or not code:
        return _page(f"<h2>Authorisation failed</h2><p class='err'>{error or 'No code returned from Spotify.'}</p>"), 400

    redirect_uri = session.get("redirect_uri", REDIRECT_URI)

    try:
        resp = http.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            auth=(CLIENT_ID, CLIENT_SECRET),
            timeout=15,
        )
    except Exception as e:
        return _page(f"<h2>Network error</h2><p>{e}</p>"), 503

    if resp.status_code != 200:
        return _page(f"<h2>Token exchange failed</h2><pre>{resp.text}</pre>"), 400

    token_data = resp.json()
    token_data["expires_at"] = int(time.time()) + token_data["expires_in"]

    os.makedirs("/srv", exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(token_data, f)
    os.chmod(CACHE_PATH, 0o600)
    # chown to match /srv owner (the app user) — portal runs as root
    srv = os.stat("/srv")
    os.chown(CACHE_PATH, srv.st_uid, srv.st_gid)

    if TEST_MODE:
        return _page(f"<h2>Test mode &mdash; auth successful</h2><p>Token saved to <code>{CACHE_PATH}</code></p>")

    open("/etc/spotify_display_configured", "w").close()
    os.system("systemctl disable spotify-hotspot setup-portal qr-display")
    threading.Timer(2.0, lambda: os.system("reboot")).start()

    return _page("<h2>All set!</h2><p>Spotify authorised. Rebooting into Now Playing mode&hellip;</p>")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if TEST_MODE:
        app.run(host="127.0.0.1", port=5000, debug=True)
    else:
        app.run(
            host="0.0.0.0",
            port=443,
            ssl_context=(
                "/etc/ssl/spotify-display.crt",
                "/etc/ssl/spotify-display.key",
            ),
        )

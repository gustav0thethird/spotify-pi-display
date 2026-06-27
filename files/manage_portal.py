#!/usr/bin/env python3
"""
Management portal — served permanently after setup is complete.
Runs on port 443 when /etc/spotify_display_configured exists.
Lets the owner view status and reset back to setup mode.
"""
import functools
import html
import json
import os
import subprocess
import threading
import time

from flask import Flask, jsonify, redirect, request, session

app = Flask(__name__)

try:
    with open("/etc/machine-id") as f:
        app.secret_key = f.read().strip()
except Exception:
    app.secret_key = "spotify-display-fallback-key"

CACHE_PATH  = "/srv/.spotify_cache"
CONFIGURED  = "/etc/spotify_display_configured"
STATE_PATH  = "/tmp/spotify_display_state.json"
PORTAL_PIN  = os.environ.get("PORTAL_PIN", "")


_manage_wifi = {"status": "idle", "ip": None, "error": None}
_manage_wifi_lock = threading.Lock()


def _set_manage_wifi(status, ip=None, error=None):
    with _manage_wifi_lock:
        _manage_wifi["status"] = status
        _manage_wifi["ip"] = ip
        _manage_wifi["error"] = error


def _get_now_playing():
    try:
        with open(STATE_PATH) as f:
            return json.load(f)
    except Exception:
        return None


def _get_home_ip(timeout=20):
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


def _require_auth(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if PORTAL_PIN and not session.get("authed"):
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper

# ---------------------------------------------------------------------------
# Shared page shell
# ---------------------------------------------------------------------------

PAGE = """<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Spotify Display</title>
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:#0a0a14;color:#e2e8f0;font-family:sans-serif;min-height:100vh;
         display:flex;align-items:center;justify-content:center;padding:20px}}
    .card{{background:#111827;border:1px solid #1a2035;border-radius:12px;
           padding:32px;max-width:440px;width:100%}}
    .logo{{color:#1DB954;font-size:.85em;font-weight:bold;letter-spacing:3px;
           text-transform:uppercase;margin-bottom:24px}}
    h1{{font-size:1.35em;margin-bottom:8px}}
    p{{color:#8892a4;font-size:.9em;margin-bottom:18px;line-height:1.55}}
    hr{{border:none;border-top:1px solid #1a2035;margin:20px 0}}
    .status{{background:#0d1117;border-radius:8px;padding:16px;margin-bottom:24px}}
    .row{{display:flex;justify-content:space-between;padding:5px 0;
          border-bottom:1px solid #1a2035;font-size:.88em}}
    .row:last-child{{border:none}}
    .lbl{{color:#8892a4}}
    .val{{font-weight:bold}}
    .ok{{color:#1DB954}}
    .bad{{color:#f87171}}
    .err{{color:#f87171;font-size:.9em;margin-bottom:12px}}
    pre{{background:#0d1117;padding:12px;border-radius:6px;font-size:.82em;
         overflow-x:auto;margin-bottom:16px;color:#8892a4}}
    .net-list{{max-height:200px;overflow-y:auto;margin-bottom:14px;border-radius:6px;
               border:1px solid #1a2035}}
    .net-item{{display:flex;justify-content:space-between;align-items:center;
               padding:10px 12px;cursor:pointer;border-bottom:1px solid #1a2035;
               font-size:.9em;transition:background .15s}}
    .net-item:last-child{{border-bottom:none}}
    .net-item:hover,.net-item.selected{{background:#1DB95420}}
    .net-item.selected{{border-left:3px solid #1DB954}}
    .net-ssid{{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
    .net-meta{{display:flex;align-items:center;gap:8px;flex-shrink:0}}
    .net-lock{{color:#8892a4;font-size:.8em}}
    .net-signal{{color:#1DB954;font-size:.75em;letter-spacing:-1px}}
    .warn-box{{background:#451a03;border:1px solid #92400e;border-radius:8px;
               padding:12px;color:#fcd34d;font-size:.85em;margin-bottom:20px;line-height:1.5}}
    label{{display:block;color:#8892a4;font-size:.85em;margin-bottom:4px}}
    input{{width:100%;padding:10px 12px;margin-bottom:14px;font-size:1em;
           border-radius:6px;border:1px solid #1a2035;background:#0d1117;color:#e2e8f0}}
    input:focus{{outline:none;border-color:#1DB954}}
    .btn{{display:block;width:100%;padding:12px;border-radius:6px;border:none;
          font-size:.95em;font-weight:bold;cursor:pointer;text-align:center;
          text-decoration:none;margin-bottom:10px}}
    .btn-danger{{background:#7f1d1d;color:#fca5a5}}
    .btn-danger:hover{{background:#991b1b}}
    .btn-cancel{{background:#1a2035;color:#8892a4}}
    .btn-cancel:hover{{background:#222c42}}
  </style>
</head>
<body><div class="card">
  <div class="logo">&#9654; Spotify Display</div>
  {body}
</div></body>
</html>"""


def _page(body):
    return PAGE.format(body=body)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _status_rows():
    rows = []

    state = _get_now_playing()
    if state:
        status = state.get("status", "unknown")
        if status == "playing" and state.get("song"):
            rows.append(("Now playing", f'<span class="ok">{html.escape(state["song"])}</span>'))
            rows.append(("Artist",      f'<span class="val">{html.escape(state.get("artist") or "")}</span>'))
            if state.get("album"):
                rows.append(("Album", f'<span style="color:#8892a4">{html.escape(state["album"])}</span>'))
        elif status == "paused" and state.get("song"):
            rows.append(("Now playing", f'<span style="color:#8892a4">Paused &mdash; {html.escape(state["song"])}</span>'))
        else:
            rows.append(("Now playing", '<span style="color:#4b5563">Nothing playing</span>'))

    token_ok = os.path.exists(CACHE_PATH)
    rows.append(("Auth token",
                 '<span class="ok">Present</span>' if token_ok
                 else '<span class="bad">Missing</span>'))

    try:
        r = subprocess.run(["systemctl", "is-active", "spotify-display"],
                           capture_output=True, text=True)
        active = r.stdout.strip() == "active"
        rows.append(("Display service",
                     '<span class="ok">Running</span>' if active
                     else f'<span class="bad">{r.stdout.strip()}</span>'))
    except Exception:
        pass

    try:
        out = subprocess.run(["ip", "-4", "addr", "show", "wlan0"],
                             capture_output=True, text=True).stdout
        for line in out.splitlines():
            s = line.strip()
            if s.startswith("inet ") and not s.split()[1].startswith("192.168.4."):
                rows.append(("IP address", s.split()[1].split("/")[0]))
                break
    except Exception:
        pass

    return rows


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form.get("pin") == PORTAL_PIN:
            session["authed"] = True
            return redirect("/")
        return _page("""
            <h1>Management Login</h1>
            <p class="err">Incorrect PIN &mdash; try again.</p>
            <form method="post">
              <label>PIN</label>
              <input name="pin" type="password" autofocus>
              <button class="btn btn-danger" type="submit" style="background:#1DB954;color:#fff">Unlock &rarr;</button>
            </form>
        """)
    return _page("""
        <h1>Management Login</h1>
        <p>Enter the PIN to access device management.</p>
        <form method="post">
          <label>PIN</label>
          <input name="pin" type="password" autofocus>
          <button class="btn" style="background:#1DB954;color:#fff;font-weight:bold" type="submit">Unlock &rarr;</button>
        </form>
    """)


@app.route("/")
@_require_auth
def index():
    rows_html = "".join(
        f'<div class="row"><span class="lbl">{l}</span>'
        f'<span class="val">{v}</span></div>'
        for l, v in _status_rows()
    )
    return _page(f"""
        <h1>Device Management</h1>
        <p>Your Spotify Display is configured and running.</p>
        <div class="status">{rows_html}</div>
        <hr>
        <a href="/reauth" class="btn btn-cancel">Re-authorise Spotify</a>
        <a href="/wifi" class="btn btn-cancel">Change WiFi Network</a>
        <a href="/logs" class="btn btn-cancel">View Logs</a>
        <a href="/update" class="btn btn-cancel">Software Update</a>
        <a href="/reset" class="btn btn-danger">Reset to Setup Mode</a>
    """)


@app.route("/reset", methods=["GET", "POST"])
@_require_auth
def reset():
    if request.method == "POST":
        threading.Thread(target=_do_reset, daemon=True).start()
        return _page("""
            <h1>Resetting&hellip;</h1>
            <p>Clearing configuration and rebooting.<br>
               The <strong>SpotifyDisplay</strong> hotspot will appear
               in about 30&nbsp;seconds.</p>
        """)

    return _page("""
        <h1>Reset to Setup Mode?</h1>
        <div class="warn-box">
          &#9888; This removes your Spotify authorisation and saved WiFi.
          The device will reboot into first-time setup mode.
        </div>
        <form method="post">
          <button class="btn btn-danger" type="submit">Yes, reset the device</button>
        </form>
        <a href="/" class="btn btn-cancel">Cancel</a>
    """)


def _do_reset():
    time.sleep(1)
    subprocess.run(["systemctl", "stop", "spotify-display"], check=False)
    for path in (CACHE_PATH, CONFIGURED):
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
    subprocess.run(["nmcli", "con", "delete", "home-wifi"], check=False)
    subprocess.run(
        ["systemctl", "enable", "qr-display", "setup-portal", "spotify-hotspot"],
        check=False,
    )
    subprocess.run(["reboot"], check=False)


@app.route("/reauth", methods=["GET", "POST"])
@_require_auth
def reauth():
    if request.method == "POST":
        threading.Thread(target=_do_reauth, daemon=True).start()
        return _page("""
            <h1>Re-authorising&hellip;</h1>
            <p>Starting Spotify login. Redirecting in a moment&hellip;</p>
            <script>setTimeout(function(){ window.location='/spotify'; }, 5000);</script>
        """)
    return _page("""
        <h1>Re-authorise Spotify</h1>
        <div class="warn-box">
          &#9888; This will clear your current Spotify token and restart the
          authorisation flow. Your WiFi settings are kept.
        </div>
        <form method="post">
          <button class="btn btn-danger" type="submit">Re-authorise Spotify</button>
        </form>
        <a href="/" class="btn btn-cancel">Cancel</a>
    """)


def _do_reauth():
    time.sleep(1)
    try:
        os.remove(CACHE_PATH)
    except FileNotFoundError:
        pass
    try:
        os.remove(CONFIGURED)
    except FileNotFoundError:
        pass
    subprocess.run(["systemctl", "enable", "setup-portal"], check=False)
    subprocess.Popen(
        ["sh", "-c", "sleep 2 && systemctl stop manage-portal && sleep 1 && systemctl start setup-portal"],
        start_new_session=True,
    )


# ---------------------------------------------------------------------------
# WiFi change
# ---------------------------------------------------------------------------

@app.route("/scan")
@_require_auth
def scan_networks():
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


@app.route("/manage-wifi-status")
@_require_auth
def manage_wifi_status():
    with _manage_wifi_lock:
        return jsonify(dict(_manage_wifi))


def _wifi_form(error=""):
    err = f"<p class='err'>{error}</p>" if error else ""
    return f"""{err}
        <div id="net-scan"><p style="color:#8892a4;font-size:.85em;text-align:center">
          &#9203; Scanning&hellip;</p></div>
        <form method="post" id="wifi-form">
          <label>WiFi Name (SSID)</label>
          <input name="ssid" id="ssid-input" placeholder="Select above or type manually"
                 autocomplete="off" required>
          <label>Password</label>
          <input name="password" id="pw-input" type="password" autocomplete="off" required>
          <button class="btn" style="background:#1DB954;color:#fff;font-weight:bold"
                  type="submit">Switch Network &rarr;</button>
        </form>
        <a href="/" class="btn btn-cancel" style="margin-top:4px">Cancel</a>
        <script>
        (function(){{
          fetch('/scan')
            .then(function(r){{return r.json();}})
            .then(function(nets){{
              var el=document.getElementById('net-scan');
              if(!nets||!nets.length){{el.innerHTML='';return;}}
              var html='<label>Nearby Networks</label><div class="net-list">';
              nets.forEach(function(n){{
                var s=n.signal;
                var bars=(s>=75?'&#9608;&#9608;&#9608;&#9608;':s>=50?'&#9608;&#9608;&#9608;&#9601;':s>=25?'&#9608;&#9608;&#9601;&#9601;':'&#9608;&#9601;&#9601;&#9601;');
                var lock=n.secured?'<span class="net-lock">[lock]</span>':'';
                var safe=n.ssid.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
                html+='<div class="net-item" onclick="selNet(this,\''+safe.replace(/'/g,'&#39;')+'\')">'
                     +'<span class="net-ssid">'+safe+'</span>'
                     +'<span class="net-meta">'+lock+'<span class="net-signal">'+bars+'</span></span>'
                     +'</div>';
              }});
              html+='</div>';
              el.innerHTML=html;
            }})
            .catch(function(){{document.getElementById('net-scan').innerHTML='';}});
        }})();
        function selNet(el,ssid){{
          document.querySelectorAll('.net-item').forEach(function(i){{i.classList.remove('selected');}});
          el.classList.add('selected');
          document.getElementById('ssid-input').value=ssid;
          document.getElementById('pw-input').focus();
        }}
        </script>"""


@app.route("/wifi", methods=["GET", "POST"])
@_require_auth
def wifi():
    if request.method == "POST":
        with _manage_wifi_lock:
            if _manage_wifi["status"] == "connecting":
                return _page("<h1>Already connecting&hellip;</h1><p>Please wait.</p>")

        ssid = request.form.get("ssid", "").strip()
        password = request.form.get("password", "")
        if not ssid or not password:
            return _page("<h1>Change WiFi</h1>" + _wifi_form("Please fill in both fields.")), 400

        _set_manage_wifi("connecting")
        threading.Thread(target=_change_wifi, args=(ssid, password), daemon=True).start()

        return _page(f"""
            <h1>Switching to {ssid}&hellip;</h1>
            <p>This takes about 15&nbsp;seconds. The device will briefly disconnect.</p>
            <div id="msg"><p style="color:#8892a4">&#9203; Connecting&hellip;</p></div>
            <script>
            var attempts=0;
            function poll(){{
              fetch('/manage-wifi-status')
                .then(function(r){{return r.json();}})
                .then(function(d){{
                  if(d.status==='connected'){{
                    var url=d.ip?'https://'+d.ip:'https://spotifydisplay.local';
                    document.getElementById('msg').innerHTML=
                      '<h3 style="color:#1DB954">&#10003; Connected!</h3>'+
                      '<p>Now on <strong>{ssid}</strong>.<br>'+
                      'Switch your device to <strong>{ssid}</strong> then visit '+
                      '<a href="https://spotifydisplay.local">spotifydisplay.local</a></p>';
                  }}else if(d.status==='failed'){{
                    document.getElementById('msg').innerHTML=
                      '<p class="err">&#10007; '+(d.error||'Could not connect')+'</p>'+
                      '<p>Previous network restored. <a href="/wifi">Try again &rarr;</a></p>';
                  }}else{{
                    attempts++;
                    if(attempts>15){{
                      document.getElementById('msg').innerHTML=
                        '<h3 style="color:#1DB954">Likely connected!</h3>'+
                        '<p>Switch your device to <strong>{ssid}</strong> and visit '+
                        '<a href="https://spotifydisplay.local">spotifydisplay.local</a></p>';
                    }}else{{setTimeout(poll,2000);}}
                  }}
                }})
                .catch(function(){{
                  attempts++;
                  if(attempts>8){{
                    document.getElementById('msg').innerHTML=
                      '<h3 style="color:#1DB954">Network switched!</h3>'+
                      '<p>Switch your device to <strong>{ssid}</strong> and visit '+
                      '<a href="https://spotifydisplay.local">spotifydisplay.local</a></p>';
                  }}else{{setTimeout(poll,3000);}}
                }});
            }}
            setTimeout(poll,2000);
            </script>
        """)

    _set_manage_wifi("idle")
    return _page("<h1>Change WiFi Network</h1>" + _wifi_form())


def _change_wifi(ssid, password):
    time.sleep(1)
    try:
        out = subprocess.run(
            ["nmcli", "--escape", "no", "-t", "-f", "NAME,TYPE,DEVICE", "con", "show", "--active"],
            capture_output=True, text=True,
        ).stdout
        old_name = None
        for line in out.splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[2] == "wlan0":
                old_name = parts[0]
                break
    except Exception:
        old_name = None

    subprocess.run([
        "nmcli", "con", "add",
        "type", "wifi", "ifname", "wlan0",
        "con-name", "home-wifi-new",
        "ssid", ssid,
        "wifi-sec.key-mgmt", "wpa-psk",
        "wifi-sec.psk", password,
        "connection.autoconnect", "yes",
        "connection.autoconnect-priority", "10",
    ], check=False)

    if old_name:
        subprocess.run(["nmcli", "con", "down", old_name], check=False)
    result = subprocess.run(
        ["nmcli", "--wait", "30", "con", "up", "home-wifi-new"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        subprocess.run(["nmcli", "con", "delete", "home-wifi-new"], check=False)
        if old_name:
            subprocess.run(["nmcli", "con", "up", old_name], check=False)
        _set_manage_wifi("failed", error="Wrong password or network not found")
        return

    subprocess.run(["nmcli", "con", "delete", old_name or "home-wifi"], check=False)
    subprocess.run(["nmcli", "con", "modify", "home-wifi-new", "con-name", "home-wifi"], check=False)

    home_ip = _get_home_ip(timeout=15)
    _set_manage_wifi("connected", ip=home_ip)

    if home_ip:
        subprocess.run([
            "openssl", "req", "-x509", "-newkey", "rsa:2048",
            "-keyout", "/etc/ssl/spotify-display.key",
            "-out",    "/etc/ssl/spotify-display.crt",
            "-days", "3650", "-nodes",
            "-subj", f"/CN={home_ip}",
            "-addext", f"subjectAltName=IP:192.168.4.1,IP:{home_ip},DNS:spotifydisplay.local",
        ], check=False)
        subprocess.Popen(
            ["sh", "-c", "sleep 3 && systemctl restart manage-portal"],
            start_new_session=True,
        )


# ---------------------------------------------------------------------------
# Log viewer
# ---------------------------------------------------------------------------

@app.route("/logs")
@_require_auth
def logs():
    try:
        result = subprocess.run(
            ["journalctl", "-u", "spotify-display", "-n", "60",
             "--no-pager", "--output=short-iso"],
            capture_output=True, text=True, timeout=10,
        )
        lines = html.escape(result.stdout or "(no output)")
    except Exception as e:
        lines = html.escape(f"Error reading logs: {e}")
    return _page(f"""
        <h1>Service Log</h1>
        <p style="display:flex;justify-content:space-between">
          <span>Last 60 lines &mdash; <code>spotify-display</code></span>
          <a href="/logs">Refresh</a>
        </p>
        <pre style="max-height:440px;overflow-y:auto;font-size:.72em;
                    line-height:1.45;white-space:pre-wrap;word-break:break-all;
                    margin-top:10px">{lines}</pre>
        <a href="/" class="btn btn-cancel" style="margin-top:10px">Back</a>
    """)


# ---------------------------------------------------------------------------
# OTA update (stub)
# ---------------------------------------------------------------------------

@app.route("/update", methods=["GET", "POST"])
@_require_auth
def update():
    if request.method == "POST":
        return _page(f"""
            <h1>Update</h1>
            <p>OTA updates are not yet configured. To update manually, SSH in and run:</p>
            <pre>cd {os.path.dirname(os.path.abspath(__file__))}
git pull
sudo systemctl restart spotify-display manage-portal</pre>
            <a href="/" class="btn btn-cancel">Back</a>
        """)
    return _page("""
        <h1>Software Update</h1>
        <p>OTA updates are not yet configured for this device.</p>
        <form method="post">
          <button class="btn btn-cancel" type="submit">Check for updates</button>
        </form>
        <a href="/" class="btn btn-cancel">Back</a>
    """)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=443,
        ssl_context=(
            "/etc/ssl/spotify-display.crt",
            "/etc/ssl/spotify-display.key",
        ),
    )

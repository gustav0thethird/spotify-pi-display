#!/usr/bin/env python3
"""
Animated setup display for /dev/fb1.

State machine:
  SPINNING         waiting for hotspot to come up
  PROGRESS         hotspot confirmed, bar animates to 100%
  QR1              Phase 1 QR — scan to join SpotifyDisplay hotspot
  WIFI_CONNECTING  hotspot dropped (portal connecting to home WiFi)
  QR2              Phase 2 QR — scan to authorize Spotify

Exits on SIGTERM or when /etc/spotify_display_configured is created.
"""
import math
import os
import signal
import subprocess
import time

import numpy as np
import qrcode
from PIL import Image, ImageDraw, ImageFont

FB = "/dev/fb1"
W, H = 480, 320
FPS = 20
FRAME_T = 1.0 / FPS

BG       = (8,   10,  22)
GREEN    = (29,  185, 84)
GREEN_LT = (60,  220, 110)
WHITE    = (255, 255, 255)
OFFWHITE = (210, 215, 225)
GRAY     = (100, 105, 118)
TRACK    = (30,  34,  50)
DIM      = (45,  48,  62)

CONFIGURED = "/etc/spotify_display_configured"
HOTSPOT    = "SpotifyDisplay-hotspot"

_running = True


def _stop(sig, frame):
    global _running
    _running = False


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)

# ── Fonts ──────────────────────────────────────────────────────────────────

def _tf(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return ImageFont.load_default()


_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
_REG  = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
         "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]

_fT = _fL = _fM = _fS = _fXS = None


def _fonts():
    global _fT, _fL, _fM, _fS, _fXS
    if _fT is None:
        _fT  = _tf(_BOLD, 26)
        _fL  = _tf(_BOLD, 20)
        _fM  = _tf(_BOLD, 15)
        _fS  = _tf(_REG,  13)
        _fXS = _tf(_REG,  10)

# ── Framebuffer ─────────────────────────────────────────────────────────────

def _write(img):
    a = np.array(img)
    r = (a[:, :, 0] >> 3).astype(np.uint16)
    g = (a[:, :, 1] >> 2).astype(np.uint16)
    b = (a[:, :, 2] >> 3).astype(np.uint16)
    try:
        with open(FB, "wb") as f:
            f.write(((r << 11) | (g << 5) | b).tobytes())
    except OSError:
        pass

# ── Canvas helpers ──────────────────────────────────────────────────────────

def _base():
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.line([(0, 0), (W, 0)], fill=GREEN, width=2)
    d.text((W - 6, H - 5), "SPOTIFY DISPLAY", font=_fXS, fill=DIM, anchor="rs")
    return img, d


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _live_dot(d, frame):
    if (frame // 12) % 2 == 0:
        d.ellipse([W - 20, 8, W - 8, 20], fill=GREEN)
        d.text((W - 24, 9), "LIVE", font=_fXS, fill=GREEN, anchor="rs")

# ── SPINNING ────────────────────────────────────────────────────────────────

TAIL_SEGS  = 20
ARC_SPAN   = 285
SPIN_SPEED = 8


def _render_spinner(angle, pulse, label):
    _fonts()
    img, d = _base()

    d.text((W // 2, 28), label, font=_fL, fill=OFFWHITE, anchor="mt")

    cx, cy, r = W // 2, H // 2 + 8, 52

    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=TRACK, width=2)

    for i in range(TAIL_SEGS):
        t = i / TAIL_SEGS
        seg_s = (angle + ARC_SPAN * t) % 360
        seg_e = (angle + ARC_SPAN * (i + 1) / TAIL_SEGS) % 360
        d.arc([cx - r, cy - r, cx + r, cy + r],
              start=seg_s, end=seg_e,
              fill=_lerp((10, 60, 28), GREEN_LT, t), width=4)

    ha = math.radians(angle + ARC_SPAN)
    hx = cx + r * math.cos(ha)
    hy = cy + r * math.sin(ha)
    dr = 6 + int(2 * pulse)
    d.ellipse([hx - dr, hy - dr, hx + dr, hy + dr], fill=GREEN_LT)

    ir = r - 14
    d.ellipse([cx - ir, cy - ir, cx + ir, cy + ir],
              outline=_lerp(BG, (20, 70, 35), 0.4 + 0.3 * pulse), width=6)

    return img

# ── PROGRESS ─────────────────────────────────────────────────────────────────

PROGRESS_FRAMES = 40


def _render_progress(progress, pulse):
    _fonts()
    img, d = _base()

    d.text((W // 2, 26), "✓  Hotspot Ready", font=_fT, fill=GREEN, anchor="mt")

    bw, bh = 360, 16
    bx = (W - bw) // 2
    by = H // 2 - bh // 2

    d.rectangle([bx, by, bx + bw, by + bh], fill=TRACK)

    fw = max(0, int(bw * progress))
    if fw > 0:
        d.rectangle([bx, by, bx + fw, by + bh], fill=GREEN)
        sx = bx + int(fw * ((math.sin(pulse * math.pi * 2) + 1) / 2))
        sx = min(sx, bx + fw - 4)
        d.rectangle([sx, by + 2, sx + 20, by + bh - 2], fill=GREEN_LT)

    d.ellipse([bx, by, bx + bh, by + bh], fill=TRACK)
    d.ellipse([bx + bw - bh, by, bx + bw, by + bh], fill=TRACK)
    if fw >= bh:
        d.ellipse([bx, by, bx + bh, by + bh], fill=GREEN)
    if fw >= bw:
        d.ellipse([bx + bw - bh, by, bx + bw, by + bh], fill=GREEN)

    d.rectangle([bx, by, bx + bw, by + bh], outline=DIM, width=1)
    d.text((W // 2, by + bh + 14), f"{int(progress * 100)}%",
           font=_fS, fill=GRAY, anchor="mt")

    return img

# ── QR card ───────────────────────────────────────────────────────────────────

def _qr_card(url, headline, subhead, rows, frame):
    """Generic QR card. rows = list of (label, value) pairs."""
    _fonts()
    img, d = _base()

    qs = 228
    qr = qrcode.make(url).convert("RGB").resize((qs, qs))
    qx, qy = 8, (H - qs) // 2
    img.paste(qr, (qx, qy))

    tx = qx + qs + 12
    d.rectangle([tx, qy, tx + 3, qy + qs], fill=GREEN)
    tx += 10

    y = qy + 8
    d.text((tx, y), headline, font=_fL, fill=WHITE)
    y += 28
    d.text((tx, y), subhead,  font=_fL, fill=GREEN)
    y += 40

    for label, value in rows:
        d.text((tx, y), label, font=_fS, fill=GRAY)
        y += 17
        d.text((tx, y), value, font=_fM, fill=WHITE)
        y += 28

    _live_dot(d, frame)
    return img


_qr1_base = None
_qr2_base = None


def render_qr1(frame):
    global _qr1_base
    if _qr1_base is None:
        _qr1_base = _qr_card(
            url      = "https://192.168.4.1",
            headline = "SCAN TO",
            subhead  = "CONNECT",
            rows     = [
                ("Network",  "SpotifyDisplay"),
                ("Password", "setup1234"),
            ],
            frame    = 0,
        )
    img = _qr1_base.copy()
    _live_dot(ImageDraw.Draw(img), frame)
    return img


def render_qr2(home_ip, frame):
    global _qr2_base
    if _qr2_base is None:
        url = f"https://{home_ip}/spotify" if home_ip else "https://spotifydisplay.local/spotify"
        label = f"{home_ip}/spotify" if home_ip else "spotifydisplay.local/spotify"
        _qr2_base = _qr_card(
            url      = url,
            headline = "SCAN TO",
            subhead  = "AUTHORIZE",
            rows     = [("Visit", label)],
            frame    = 0,
        )
    img = _qr2_base.copy()
    _live_dot(ImageDraw.Draw(img), frame)
    return img

# ── System checks ─────────────────────────────────────────────────────────────

def _hotspot_up():
    try:
        out = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,STATE", "con", "show", "--active"],
            capture_output=True, text=True, timeout=2,
        ).stdout
        return any(HOTSPOT in ln and "activated" in ln for ln in out.splitlines())
    except Exception:
        return False


def _home_ip():
    try:
        out = subprocess.run(
            ["ip", "-4", "addr", "show", "wlan0"],
            capture_output=True, text=True, timeout=2,
        ).stdout
        for line in out.splitlines():
            line = line.strip()
            if line.startswith("inet "):
                ip = line.split()[1].split("/")[0]
                if not ip.startswith("192.168.4."):
                    return ip
    except Exception:
        pass
    return None

# ── Main loop ─────────────────────────────────────────────────────────────────

CHECK_EVERY = 25   # frames between network polls
QR_REFRESH  = 12   # frames between QR re-renders (live dot)


def main():
    state   = "spinning"
    angle   = 0
    prog    = 0.0
    frame   = 0
    home_ip = None

    while _running:
        if os.path.exists(CONFIGURED):
            break

        t0    = time.monotonic()
        pulse = (math.sin(frame * 0.18) + 1) / 2

        if state == "spinning":
            _write(_render_spinner(angle, pulse, "Starting up…"))
            angle = (angle + SPIN_SPEED) % 360
            if frame % CHECK_EVERY == 0 and _hotspot_up():
                state = "progress"
                frame = 0

        elif state == "progress":
            prog = min(1.0, frame / PROGRESS_FRAMES)
            _write(_render_progress(prog, pulse))
            if prog >= 1.0:
                state = "qr1"
                frame = 0

        elif state == "qr1":
            if frame % QR_REFRESH == 0:
                _write(render_qr1(frame))
            # Hotspot drops when portal switches Pi to home WiFi
            if frame % CHECK_EVERY == 0 and not _hotspot_up():
                state = "wifi_connecting"
                frame = 0

        elif state == "wifi_connecting":
            _write(_render_spinner(angle, pulse, "Connecting to WiFi…"))
            angle = (angle + SPIN_SPEED) % 360
            if frame % CHECK_EVERY == 0:
                ip = _home_ip()
                if ip:
                    home_ip = ip
                    state = "qr2"
                    frame = 0
                elif _hotspot_up():
                    # Portal failed, hotspot restored — go back to QR1
                    _qr1_base = None   # force re-render
                    state = "qr1"
                    frame = 0

        elif state == "qr2":
            if frame % QR_REFRESH == 0:
                _write(render_qr2(home_ip, frame))

        frame += 1
        sleep = FRAME_T - (time.monotonic() - t0)
        if sleep > 0:
            time.sleep(sleep)


if __name__ == "__main__":
    main()

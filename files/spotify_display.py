#!/usr/bin/env python3
import io
import json
import math
import os
import re
import socket
import time

import numpy as np
import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

# === CONFIGURATION ===
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://192.168.4.1/callback")
SCOPE = "user-read-currently-playing"
CACHE_PATH = "/srv/.spotify_cache"

FB_DEV = "/dev/fb1"
WIDTH, HEIGHT = 480, 320

FONT_MAIN = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_SMALL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

SPINNER = ["|", "/", "-", "\\"]
SCREENSAVER_SECS = 300   # blank screen after 5 min of idle/paused
WATCHDOG_INTERVAL = 20   # seconds between watchdog pings


def _sd_notify(msg):
    sock_path = os.environ.get("NOTIFY_SOCKET")
    if not sock_path:
        return
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as s:
            s.connect(sock_path)
            s.send(msg.encode())
    except Exception:
        pass


# === INIT ===
sp = Spotify(
    auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope=SCOPE,
        cache_path=CACHE_PATH
    ),
    requests_timeout=5,
    retries=0
)

def _load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

font_main       = _load_font(FONT_MAIN, 20)
font_small      = _load_font(FONT_SMALL, 16)
font_clock      = _load_font(FONT_MAIN, 64)
font_date_small = _load_font(FONT_SMALL, 18)

# Album art cache — keyed by URL so we only fetch on track change
_art_cache_url = None
_art_cache_img = None


def _get_art(url, size):
    global _art_cache_url, _art_cache_img
    if url == _art_cache_url and _art_cache_img is not None:
        return _art_cache_img
    try:
        data = requests.get(url, timeout=5).content
        art = Image.open(io.BytesIO(data)).convert("RGB").resize((size, size))
        _art_cache_url = url
        _art_cache_img = art
        return art
    except Exception as e:
        print("Error loading album art:", e)
        return None

def rgb_to_rgb565(img):
    arr = np.array(img)
    r = (arr[:, :, 0] >> 3).astype(np.uint16)
    g = (arr[:, :, 1] >> 2).astype(np.uint16)
    b = (arr[:, :, 2] >> 3).astype(np.uint16)
    rgb565 = (r << 11) | (g << 5) | b
    return rgb565.tobytes()

def draw_text_center(draw, text, y, font, fill=(255,255,255)):
    try:
        w, h = draw.textsize(text, font=font)
    except AttributeError:
        bbox = draw.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((WIDTH - w)//2, y), text, fill=fill, font=font)

def draw_marquee(base_img, text, x, y, font, max_width, frame, fill=(255,255,255)):
    draw_tmp = ImageDraw.Draw(base_img)
    try:
        bbox = draw_tmp.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        text_width, text_height = draw_tmp.textsize(text, font=font)

    text_img = Image.new("RGBA", (max_width, text_height + 4), (0, 0, 0, 0))
    text_draw = ImageDraw.Draw(text_img)

    if text_width <= max_width:
        text_draw.text((0, 0), text, font=font, fill=fill + (255,))
    else:
        offset = frame % (text_width + 40)
        text_draw.text((-offset, 0), text, font=font, fill=fill + (255,))
        text_draw.text((-offset + text_width + 40, 0), text, font=font, fill=fill + (255,))

    base_img.paste(text_img, (x, y), text_img)


def _draw_at_center(draw, text, cx, cy, font, fill):
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except AttributeError:
        tw, th = draw.textsize(text, font=font)
    draw.text((cx - tw // 2, cy - th // 2), text, fill=fill, font=font)


def render_screensaver():
    t = time.time()
    drift_x = int(50 * math.sin(t / 67))
    drift_y = int(30 * math.cos(t / 53))
    cx = WIDTH  // 2 + drift_x
    cy = HEIGHT // 2 + drift_y
    img  = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    _draw_at_center(draw, time.strftime("%H:%M"),    cx, cy - 20, font_clock,      fill=(45, 45, 45))
    _draw_at_center(draw, time.strftime("%a  %d %b"), cx, cy + 48, font_date_small, fill=(25, 25, 25))
    return img


def render_display(info, frame=0):
    img = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
    draw = ImageDraw.Draw(img)

    if not info:
        draw_text_center(draw, "Unknown state", HEIGHT // 2 - 10, font_main, fill=(180,180,180))
        return img

    status = info.get("status", "unknown")

    if status in ("playing", "paused") and info.get("song"):
        art_x, art_y = 10, 10
        art_size = 300

        art = _get_art(info["album_art_url"], art_size) if info.get("album_art_url") else None

        text_fill   = (255, 255, 255)
        artist_fill = (220, 220, 220)
        album_fill  = (130, 130, 130)

        if art:
            dominant = art.resize((1, 1)).getpixel((0, 0))
            bg = Image.new("RGB", (WIDTH, HEIGHT), dominant)
            bg = bg.filter(ImageFilter.GaussianBlur(40))
            img.paste(bg, (0, 0))
            lum = 0.2126 * dominant[0] + 0.7152 * dominant[1] + 0.0722 * dominant[2]
            if lum > 160:
                text_fill   = (15,  15,  15)
                artist_fill = (50,  50,  50)
                album_fill  = (100, 100, 100)

        if art:
            img.paste(art, (art_x, art_y))

        text_x     = art_x + art_size + 12
        text_width = WIDTH - text_x - 10

        song   = info["song"]           or ""
        artist = info["artist"]         or ""
        album  = info.get("album")      or ""

        try:
            def _h(t, f):
                b = draw.textbbox((0, 0), t, font=f)
                return b[3] - b[1]
            song_h   = _h(song,   font_main)
            artist_h = _h(artist, font_small)
            album_h  = _h(album,  font_small) if album else 0
        except AttributeError:
            _, song_h   = draw.textsize(song,   font=font_main)
            _, artist_h = draw.textsize(artist, font=font_small)
            album_h     = draw.textsize(album,  font=font_small)[1] if album else 0

        total_text_height = song_h + artist_h + 10 + (album_h + 8 if album else 0)
        text_y = (HEIGHT - total_text_height) // 2

        draw_marquee(img, song,   text_x, text_y,                              font_main,  text_width, frame, fill=text_fill)
        draw_marquee(img, artist, text_x, text_y + song_h + 10,               font_small, text_width, frame, fill=artist_fill)
        if album:
            draw_marquee(img, album, text_x, text_y + song_h + artist_h + 18, font_small, text_width, frame, fill=album_fill)

        # Progress bar
        if info.get("duration_ms", 0) > 0:
            progress = min(info.get("progress_ms", 0) / info["duration_ms"], 1.0)
            bar_y = HEIGHT - 5
            draw.rectangle([0, bar_y, WIDTH, HEIGHT], fill=(25, 25, 25))
            fill_w = int(WIDTH * progress)
            if fill_w > 0:
                draw.rectangle([0, bar_y, fill_w, HEIGHT], fill=(29, 185, 84))

        # Paused: dim the whole frame and show label
        if status == "paused":
            dark = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))
            img = Image.blend(img, dark, 0.45)
            draw = ImageDraw.Draw(img)
            draw_text_center(draw, "|| PAUSED", HEIGHT - 22, font_small, fill=(160, 160, 160))

    else:
        if status in ("idle", "paused"):
            img = Image.new("RGB", (WIDTH, HEIGHT), (8, 8, 8))
            draw = ImageDraw.Draw(img)
            draw_text_center(draw, time.strftime("%H:%M"), HEIGHT // 2 - 55, font_clock, fill=(190, 190, 190))
            draw_text_center(draw, time.strftime("%a  %d %b"), HEIGHT // 2 + 40, font_date_small, fill=(70, 70, 70))

        else:
            color = (0, 0, 0)
            msg = None

            if status == "no_internet":
                msg = "No internet connection"
                color = (80, 0, 0)

            elif status == "token_expired":
                msg = "Token expired - retrying"
                color = (100, 60, 0)

            elif status == "rate_limited":
                retry = info.get("retry_after", 30)
                spinner = SPINNER[frame % len(SPINNER)]
                msg = f"Rate limited {spinner} Retry in {retry}s"
                info["retry_after"] = max(retry - 1, 0)
                color = (0, 40, 100)

            elif status == "api_unreachable":
                msg = "Spotify API unreachable"
                color = (40, 0, 80)

            else:
                msg = f"Unknown state: {status}"
                color = (50, 50, 50)

            img = Image.new("RGB", (WIDTH, HEIGHT), color)
            draw = ImageDraw.Draw(img)
            draw_text_center(draw, msg, HEIGHT // 2 - 10, font_main, fill=(255,255,255))

    return img


def safe_get_now_playing(sp, retries=3):
    for attempt in range(retries):
        try:
            current = sp.current_user_playing_track()

            if not current:
                return {"status": "idle", "song": None, "artist": None, "album_art_url": None}

            if not current.get("is_playing"):
                return {"status": "paused", "song": None, "artist": None, "album_art_url": None}

            item = current.get("item")
            if not item:
                return {"status": "idle", "song": None, "artist": None, "album_art_url": None}

            return {
                "status": "playing",
                "song": item["name"],
                "artist": ", ".join(a["name"] for a in item["artists"]),
                "album": item["album"].get("name", ""),
                "album_art_url": item["album"]["images"][0]["url"] if item["album"]["images"] else None,
                "progress_ms": current.get("progress_ms", 0),
                "duration_ms": item.get("duration_ms", 0),
            }

        except Exception as e:
            msg = str(e).lower()

            if "429" in msg or "rate limit" in msg:
                retry_after = 30
                match = re.search(r"after[:=]\s*([0-9]+)", msg)
                if match:
                    retry_after = int(match.group(1))
                if retry_after > 600:
                    retry_after = 600
                print(f"Rate limited. Cooling down {retry_after}s.")
                return {"status": "rate_limited", "retry_after": retry_after,
                        "song": None, "artist": None, "album_art_url": None}

            if any(w in msg for w in ["401", "token expired", "expired", "invalid token",
                                       "no token", "oauth", "invalid_grant", "unauthorized"]):
                print("Auth error, attempting token refresh:", e)
                try:
                    cached = sp.auth_manager.get_cached_token()
                    if cached and cached.get("refresh_token"):
                        sp.auth_manager.refresh_access_token(cached["refresh_token"])
                        print("Token refreshed.")
                        continue
                except Exception as refresh_err:
                    print("Token refresh failed:", refresh_err)
                return {"status": "token_expired", "song": None, "artist": None, "album_art_url": None}

            if any(w in msg for w in ["connection", "dns", "timed out", "failed to establish",
                                       "max retries", "ssl", "certificate", "network",
                                       "unreachable", "no route", "name or service", "refused"]):
                print("Network error:", e)
                return {"status": "no_internet", "song": None, "artist": None, "album_art_url": None}

            print(f"Spotify API error ({attempt+1}/{retries}): {e}")
            time.sleep(2)

    print("Spotify unreachable after retries.")
    return {"status": "api_unreachable", "song": None, "artist": None, "album_art_url": None}


def main():
    _sd_notify("READY=1")

    # Wait for Spotify API before entering main loop (network may not be ready yet)
    for _attempt in range(6):
        _probe = safe_get_now_playing(sp)
        if _probe and _probe.get("status") not in ("no_internet", "api_unreachable"):
            break
        print(f"Spotify not reachable (attempt {_attempt + 1}/6), retrying in 10s…")
        time.sleep(10)

    if not os.path.exists(CACHE_PATH):
        print(f"Token cache not found at {CACHE_PATH} — run setup again")
        img = Image.new("RGB", (WIDTH, HEIGHT), (80, 0, 0))
        draw = ImageDraw.Draw(img)
        draw_text_center(draw, "No auth token — rescan QR", HEIGHT // 2 - 10, font_main)
        try:
            with open(FB_DEV, "wb") as f:
                f.write(rgb_to_rgb565(img))
        except Exception:
            pass
        time.sleep(30)
        return

    last_info = None
    last_fetch = 0
    cooldown_until = 0
    FETCH_INTERVAL = 2
    FRAME_INTERVAL = 0.05
    frame = 0

    fade_frame = 0
    FADE_FRAMES = 20
    last_img = None

    last_playing_info = None
    last_playing_at = time.time()
    last_watchdog = 0
    idle_streak = 0          # consecutive non-playing fetches before we show idle
    IDLE_DEBOUNCE = 3        # require 3 consecutive idle/paused responses (~6s) before switching

    while True:
        now = time.time()

        if now < cooldown_until:
            remaining = int(cooldown_until - now)
            info = {
                "status": "rate_limited",
                "retry_after": remaining,
                "song": None,
                "artist": None,
                "album_art_url": None
            }

        elif now - last_fetch > FETCH_INTERVAL:
            fetched = safe_get_now_playing(sp)

            if fetched and fetched.get("status") == "rate_limited":
                retry_after = fetched.get("retry_after", 30)
                cooldown_until = now + retry_after
                print(f"Rate limited. Cooling down for {retry_after}s (until {time.strftime('%H:%M:%S', time.localtime(cooldown_until))})")

            # Debounce idle/paused: only switch away from playing after IDLE_DEBOUNCE consecutive non-playing responses
            if fetched and fetched.get("status") in ("idle", "paused"):
                idle_streak += 1
                if idle_streak < IDLE_DEBOUNCE and last_info and last_info.get("status") == "playing":
                    fetched = last_info  # hold the playing state until streak confirmed
            else:
                idle_streak = 0

            info = fetched

            if info != last_info or (info and last_info and info.get("status") != last_info.get("status")):
                fade_frame = 0

            last_info = info
            last_fetch = now

        else:
            info = last_info

        # Track last playing state for paused display and screensaver
        if info and info.get("status") == "playing":
            last_playing_at = now
            last_playing_info = info

        # Write current state for management portal dashboard
        try:
            with open("/tmp/spotify_display_state.json", "w") as _sf:
                json.dump({
                    "status":        info.get("status")        if info else "unknown",
                    "song":          info.get("song")          if info else None,
                    "artist":        info.get("artist")        if info else None,
                    "album":         info.get("album")         if info else None,
                    "album_art_url": info.get("album_art_url") if info else None,
                    "updated_at":    now,
                }, _sf)
        except Exception:
            pass

        # Screensaver: drifting dim clock after SCREENSAVER_SECS of idle/paused
        if (info and info.get("status") in ("idle", "paused") and
                now - last_playing_at > SCREENSAVER_SECS):
            try:
                with open(FB_DEV, "wb") as f:
                    f.write(rgb_to_rgb565(render_screensaver()))
            except Exception:
                pass
            time.sleep(1)
            frame += 2
            continue

        # Watchdog ping
        if now - last_watchdog > WATCHDOG_INTERVAL:
            _sd_notify("WATCHDOG=1")
            last_watchdog = now

        # Build display_info: smooth progress bar + carry last track when paused
        display_info = info
        if info:
            if info.get("status") == "playing" and info.get("duration_ms", 0) > 0:
                elapsed_ms = int((now - last_fetch) * 1000)
                estimated = min(info["progress_ms"] + elapsed_ms, info["duration_ms"])
                display_info = {**info, "progress_ms": estimated}
            elif info.get("status") == "paused" and last_playing_info:
                display_info = {**last_playing_info, "status": "paused"}

        new_img = render_display(display_info, frame)

        if last_img and fade_frame < FADE_FRAMES:
            alpha = fade_frame / FADE_FRAMES
            out_img = Image.blend(last_img, new_img, alpha)
            fade_frame += 1
        else:
            out_img = new_img

        try:
            with open(FB_DEV, "wb") as f:
                f.write(rgb_to_rgb565(out_img))
        except Exception as e:
            print("Error writing framebuffer:", e)

        last_img = new_img
        frame += 2

        if info and info.get("status") == "rate_limited":
            time.sleep(1)
        else:
            time.sleep(FRAME_INTERVAL)


if __name__ == "__main__":
    main()

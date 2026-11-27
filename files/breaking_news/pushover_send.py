#!/usr/bin/env python3
"""Pushover helper. Creds from ~/.config/pushover/env (PUSHOVER_USER, PUSHOVER_TOKEN).
send(title, message, priority=0, url=None, url_title=None, image_url=None, sound=None, html=True, ttl=None) -> bool
Message is cut to 1024 chars, title to 250. Image (<=2.5MB) is downloaded and uploaded as attachment."""
import io, json, urllib.request, uuid
from pathlib import Path

API = "https://api.pushover.net/1/messages.json"


def _env():
    d = {}
    for l in (Path.home() / ".config/pushover/env").read_text().splitlines():
        if "=" in l:
            k, v = l.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def _fetch_image(url):
    try:
        r = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(r, timeout=10).read(2_600_000)
        return data if 0 < len(data) <= 2_500_000 else None
    except Exception:
        return None


def send(title, message, priority=0, url=None, url_title=None, image_url=None, sound=None, html=True, ttl=None):
    e = _env()
    f = {"token": e["PUSHOVER_TOKEN"], "user": e["PUSHOVER_USER"], "title": title[:250],
         "message": message[:1024], "priority": str(priority)}
    if html: f["html"] = "1"
    if url: f["url"] = url
    if url_title: f["url_title"] = url_title[:100]
    if sound: f["sound"] = sound
    if ttl: f["ttl"] = str(ttl)
    b = uuid.uuid4().hex
    body = io.BytesIO()
    for k, v in f.items():
        body.write(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    img = _fetch_image(image_url) if image_url else None
    if img:
        body.write(f'--{b}\r\nContent-Disposition: form-data; name="attachment"; filename="image.jpg"\r\n'
                   f'Content-Type: image/jpeg\r\n\r\n'.encode() + img + b"\r\n")
    body.write(f"--{b}--\r\n".encode())
    req = urllib.request.Request(API, data=body.getvalue(),
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}"}, method="POST")
    try:
        return json.loads(urllib.request.urlopen(req, timeout=20).read()).get("status") == 1
    except Exception as ex:
        print("pushover failed:", ex)
        return False


def _md_to_html(t):
    import html, re
    t = html.escape(t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`([^`]+)`", r"<tt>\1</tt>", t)
    t = re.sub(r"(?<![\w*])_([^_\n]+)_(?![\w*])", r"<i>\1</i>", t)
    return t


def mirror(title, priority=0, fail_words=("FAILED", "failed"), sound=None):
    """Tee this script's stdout; at exit, push whatever was printed (if anything) to Pushover.
    Output still flows to stdout, so the existing cron delivery (Mattermost) is unchanged.
    Failure-looking output is bumped to priority 1."""
    import atexit, sys

    class Tee:
        def __init__(self, real): self.real, self.buf = real, []
        def write(self, s): self.buf.append(s); return self.real.write(s)
        def flush(self): self.real.flush()
        def __getattr__(self, n): return getattr(self.real, n)

    tee = Tee(sys.stdout)
    sys.stdout = tee

    def _push():
        text = "".join(tee.buf).strip()
        if not text:
            return
        bad = any(w in text for w in fail_words)
        send(("⚠️ " if bad else "") + title, _md_to_html(text), priority=max(priority, 1) if bad else priority,
             sound=sound or ("siren" if bad else None))
    atexit.register(_push)

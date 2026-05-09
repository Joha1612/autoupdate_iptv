import base64
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import Request, urlopen

from Crypto.Cipher import AES

# =========================================
# CONFIG
# =========================================

BASE_URL = "https://makethemoongreatagain.pages.dev/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

APP_KEY = "HmIcX6iHMHfI0zji".encode()
APP_IV = "MZ63rk5cIGYEy0GY".encode()

SIG_B64 = "oAR80SGuX3EEjUGFRwLFKBTiris="

ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789+!@#$%&="
)

ENDPOINTS = {
    "app": "app.json",
    "events": "events.json",
    "events_with_streams": "events.json",
    "eventcats": "eventcats.json",
    "cats": "cats.json",
}


# =========================================
# HASH FUNCTION
# =========================================

def fnv(data, seed_xor):
    h = (0x811C9DC5 ^ seed_xor) & 0xFFFFFFFF

    for b in data:
        h ^= b
        h = (h * 0x1000193) & 0xFFFFFFFF

    return h


# =========================================
# KEY GENERATION
# =========================================

def derive_native_material(sig_b64):
    data = sig_b64.encode()
    n = len(data)

    state = fnv(data, 0)

    key = []

    for i in range(16):
        state = ((state * 31) + (data[i % n] ^ i)) & 0xFFFFFFFF
        key.append(ALPHABET[state % 70])

    state = fnv(data, 0x1EEF)

    iv = []

    pos = 0
    tweak = 0

    while pos < 0x30:
        state = (
            (state * 29) + (data[pos % n] ^ tweak)
        ) & 0xFFFFFFFF

        iv.append(ALPHABET[state % 70])

        pos += 3
        tweak += 7

    return "".join(key).encode(), "".join(iv).encode()


NATIVE_KEY, NATIVE_IV = derive_native_material(SIG_B64)


# =========================================
# HELPERS
# =========================================

def unpad(data):
    pad = data[-1]

    if 1 <= pad <= 16 and data.endswith(bytes([pad]) * pad):
        return data[:-pad]

    return data


def fetch_encrypted(path):
    req = Request(
        BASE_URL + path,
        headers={
            "User-Agent": USER_AGENT
        }
    )

    with urlopen(req, timeout=30) as resp:
        body = resp.read().decode("utf-8")

    return json.loads(body)["data"]


# =========================================
# DECRYPTION
# =========================================

def decrypt_app(payload_b64):
    cipher = AES.new(APP_KEY, AES.MODE_CBC, APP_IV)

    data = cipher.decrypt(base64.b64decode(payload_b64))

    return json.loads(
        unpad(data).decode("utf-8")
    )


def decrypt_native(payload_b64):
    cipher = AES.new(
        NATIVE_KEY,
        AES.MODE_CBC,
        NATIVE_IV
    )

    data = cipher.decrypt(
        base64.b64decode(payload_b64)
    )

    return json.loads(
        unpad(data).decode("utf-8")
    )


# =========================================
# DATA FETCHERS
# =========================================

def get_data(name):
    path = ENDPOINTS[name]

    payload_b64 = fetch_encrypted(path)

    if name == "app":
        return decrypt_app(payload_b64)

    if name == "events_with_streams":
        return get_events_with_streams()

    return decrypt_native(payload_b64)


def get_channel_streams(channel_id):
    payload_b64 = fetch_encrypted(
        f"channels/{channel_id}.json"
    )

    return decrypt_native(payload_b64)


def get_events_with_streams():
    events = decrypt_native(
        fetch_encrypted(
            ENDPOINTS["events"]
        )
    )

    enriched = []

    for event in events:
        item = dict(event)

        try:
            item["streams"] = get_channel_streams(
                item["id"]
            )

        except Exception as e:
            item["streams_error"] = str(e)

        enriched.append(item)

    return enriched


# =========================================
# AUTO M3U GENERATOR
# =========================================

def create_m3u():

    print("Generating M3U playlist...")

    data = get_events_with_streams()

    lines = ["#EXTM3U"]

    for item in data:

        # EVENT NAME
        event_info = item.get("eventInfo", {})

        event_name = (
            event_info.get("eventName")
            or item.get("title")
            or "Live Event"
        )

        streams = item.get("streams", [])

        for stream in streams:

            channel_name = stream.get(
                "title",
                "Unknown"
            )

            url = (
                stream.get("link")
                or stream.get("url")
                or stream.get("stream")
                or stream.get("src")
            )

            if not url:
                continue

            # CHANNEL + EVENT NAME

            full_name = f"{channel_name} ,({event_name})"

            # CATEGORY
            category = item.get("cat", "Sports")

            # lines.append(
            #     f'#EXTINF:-1 group-title="{category}",{full_name}'
            # )

            lines.append(
                f'#EXTINF:-1 '
                f'tvg-id="{channel_name}" '
                f'tvg-name="{channel_name}" '
                f'group-title="{category}",'
                f'{full_name}'
            )

            # DRM KEY
            api_key = stream.get("api")

            if api_key:

                lines.append(
                    "#KODIPROP:inputstream.adaptive.license_type=clearkey"
                )

                lines.append(
                    f"#KODIPROP:inputstream.adaptive.license_key={api_key}"
                )

            lines.append(
                "#EXTVLCOPT:http-user-agent=Mozilla/5.0"
            )

            lines.append(url)

            lines.append("")

            print("ADDED:", full_name)

    with open(
        "auto_playlist.m3u",
        "w",
        encoding="utf-8"
    ) as f:

        f.write("\n".join(lines))

    print("DONE")


# Git

def auto_push_to_github():

    print("Uploading to GitHub...")

    os.system("git add .")

    os.system(
        'git commit -m "Auto update playlist"'
    )

    os.system("git push")

    print("GitHub Updated")


# =========================================
# HTTP SERVER
# =========================================

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        route = (
            self.path
            .split("?", 1)[0]
            .strip("/")
        )

        if route == "":
            self.respond({
                "routes": sorted(ENDPOINTS)
            })
            return

        if route not in ENDPOINTS:
            self.respond({
                "error": "not found"
            }, 404)
            return

        try:
            self.respond(
                get_data(route)
            )

        except Exception as e:
            self.respond({
                "error": str(e)
            }, 500)

    def log_message(self, format, *args):
        return

    def respond(self, payload, status=200):

        body = json.dumps(
            payload,
            ensure_ascii=False
        ).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json; charset=utf-8"
        )

        self.send_header(
            "Content-Length",
            str(len(body))
        )

        self.end_headers()

        self.wfile.write(body)


# =========================================
# MAIN
# =========================================

def main():

    # AUTO GENERATE M3U
    create_m3u()

    # github
    auto_push_to_github()

    # START API SERVER
    server = HTTPServer(
        ("127.0.0.1", 8000),
        Handler
    )

    print("Server running:")
    print("http://127.0.0.1:8000")
    print("http://127.0.0.1:8000/events_with_streams")

    server.serve_forever()


if __name__ == "__main__":
    main()
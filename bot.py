import os
import json
import base64
import asyncio
from pathlib import Path

import requests
import discord

ARTIST_NAME = "t-low"
ARTIST_ID = "6CXcJfwCbIa8J99qSeqO6j"

BASE_DIR = Path(**file**).resolve().parent
STATE_FILE = BASE_DIR / "state.json"

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

MANUAL_RUN = os.getenv("MANUAL_RUN", "false").lower() == "true"

def load_state():
if not STATE_FILE.exists():
return {
"last_release_id": None
}

```
try:
    with open(STATE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)
except Exception as error:
    print(f"State konnte nicht gelesen werden: {error}")

    return {
        "last_release_id": None
    }
```

def save_state(state):
with open(STATE_FILE, "w", encoding="utf-8") as file:
json.dump(
state,
file,
indent=4,
ensure_ascii=False
)

def get_spotify_token():
print("Hole Spotify Token...")

```
credentials = (
    f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
)

encoded_credentials = base64.b64encode(
    credentials.encode("utf-8")
).decode("utf-8")

response = requests.post(
    "https://accounts.spotify.com/api/token",
    headers={
        "Authorization": (
            f"Basic {encoded_credentials}"
        ),
        "Content-Type": (
            "application/x-www-form-urlencoded"
        )
    },
    data={
        "grant_type": "client_credentials"
    },
    timeout=20
)

if not response.ok:
    print("Spotify Token Fehler:")
    print(f"Status: {response.status_code}")
    print(response.text)

    response.raise_for_status()

data = response.json()

token = data.get("access_token")

if not token:
    raise Exception(
        "Spotify hat keinen Access Token zurückgegeben."
    )

print("Spotify Token erhalten.")

return token
```

def spotify_get(url, token, params=None):
response = requests.get(
url,
headers={
"Authorization": f"Bearer {token}"
},
params=params,
timeout=20
)

```
if not response.ok:
    print("")
    print("=" * 60)
    print("SPOTIFY API FEHLER")
    print("=" * 60)
    print(f"Status: {response.status_code}")
    print(f"URL: {response.url}")
    print(response.text)
    print("=" * 60)
    print("")

    response.raise_for_status()

return response.json()
```

def get_artist():
token = get_spotify_token()

```
print("")
print("Verwende Artist:")
print(f"Name: {ARTIST_NAME}")
print(f"ID: {ARTIST_ID}")

return token
```

def get_releases(token):
print("")
print("Suche t-low Releases...")

```
url = (
    f"https://api.spotify.com/v1/artists/"
    f"{ARTIST_ID}/albums"
)

releases = []
offset = 0

while True:
    data = spotify_get(
        url,
        token,
        {
            "include_groups": "album,single",
            "market": "DE",
            "limit": 10,
            "offset": offset
        }
    )

    items = data.get("items", [])

    releases.extend(items)

    print(
        f"Geladen: {len(items)} Releases "
        f"(Offset {offset})"
    )

    if not data.get("next"):
        break

    offset += 10

    if offset >= 100:
        break

unique_releases = {}

for release in releases:
    release_id = release.get("id")

    if release_id:
        unique_releases[release_id] = release

releases = list(unique_releases.values())

releases.sort(
    key=lambda release: release.get(
        "release_date",
        ""
    ),
    reverse=True
)

print(
    f"Insgesamt {len(releases)} Releases gefunden."
)

return releases
```

def get_latest_release(token):
releases = get_releases(token)

```
if not releases:
    return None

latest = releases[0]

release_id = latest.get("id")
release_name = latest.get(
    "name",
    "Unbekannt"
)
release_date = latest.get(
    "release_date",
    "Unbekannt"
)
release_type = latest.get(
    "album_type",
    "Unbekannt"
)

print("")
print("=" * 60)
print("NEUESTER RELEASE")
print("=" * 60)
print(f"Name: {release_name}")
print(f"Datum: {release_date}")
print(f"Typ: {release_type}")
print(f"ID: {release_id}")
print("=" * 60)

tracks_data = spotify_get(
    f"https://api.spotify.com/v1/albums/"
    f"{release_id}/tracks",
    token,
    {
        "market": "DE",
        "limit": 50
    }
)

tracks = tracks_data.get(
    "items",
    []
)

if not tracks:
    print("Keine Tracks in diesem Release gefunden.")
    return None

track = tracks[0]

image_url = None

images = latest.get(
    "images",
    []
)

if images:
    image_url = images[0].get("url")

return {
    "release_id": release_id,
    "release_name": release_name,
    "release_date": release_date,
    "release_type": release_type,
    "track_id": track.get("id"),
    "track_name": track.get(
        "name",
        "Unbekannt"
    ),
    "spotify_url": track.get(
        "external_urls",
        {}
    ).get("spotify"),
    "image": image_url
}
```

def create_embed(release):
embed = discord.Embed(
title=f"🎵 Neuer Release von {ARTIST_NAME}",
description=(
f"**{release['track_name']}**\n\n"
f"[🎧 Auf Spotify anhören]"
f"({release['spotify_url']})"
),
url=release["spotify_url"],
color=0x1DB954
)

```
embed.add_field(
    name="💿 Release",
    value=release["release_name"],
    inline=True
)

embed.add_field(
    name="📅 Datum",
    value=release["release_date"],
    inline=True
)

if release.get("image"):
    embed.set_thumbnail(
        url=release["image"]
    )

embed.set_footer(
    text="Spotify Release Bot"
)

return embed
```

async def send_discord_message(release=None):
intents = discord.Intents.default()

```
client = discord.Client(
    intents=intents
)

@client.event
async def on_ready():
    print(
        f"Discord verbunden als {client.user}"
    )

    try:
        channel = client.get_channel(
            int(DISCORD_CHANNEL_ID)
        )

        if channel is None:
            channel = await client.fetch_channel(
                int(DISCORD_CHANNEL_ID)
            )

        print(
            f"Discord Channel gefunden: "
            f"{channel.name}"
        )

        if release is None:
            await channel.send(
                "Kein Neuer Song"
            )

            print(
                ">>> 'Kein Neuer Song' gesendet."
            )

        else:
            embed = create_embed(
                release
            )

            await channel.send(
                embed=embed
            )

            print(
                ">>> Neuer Release gesendet!"
            )

    except Exception as error:
        print(
            f"Discord Fehler: {error}"
        )

        raise

    finally:
        await client.close()

await client.start(
    DISCORD_TOKEN
)
```

def check_configuration():
missing = []

```
if not DISCORD_TOKEN:
    missing.append(
        "DISCORD_TOKEN"
    )

if not DISCORD_CHANNEL_ID:
    missing.append(
        "DISCORD_CHANNEL_ID"
    )

if not SPOTIFY_CLIENT_ID:
    missing.append(
        "SPOTIFY_CLIENT_ID"
    )

if not SPOTIFY_CLIENT_SECRET:
    missing.append(
        "SPOTIFY_CLIENT_SECRET"
    )

if missing:
    raise Exception(
        "Fehlende Secrets: "
        + ", ".join(missing)
    )
```

async def main():
print("")
print("=" * 60)
print("T-LOW DISCORD RELEASE BOT")
print("=" * 60)

```
check_configuration()

print("Alle Secrets vorhanden.")

token = get_artist()

release = get_latest_release(
    token
)

if release is None:
    print(
        "Kein Release gefunden."
    )

    if MANUAL_RUN:
        await send_discord_message()

    return

state = load_state()

last_release_id = state.get(
    "last_release_id"
)

current_release_id = release.get(
    "release_id"
)

print("")
print(
    f"Gespeicherter Release: "
    f"{last_release_id}"
)

print(
    f"Aktueller Release: "
    f"{current_release_id}"
)

if last_release_id is None:
    print("")
    print(
        "Erster Start."
    )
    print(
        "Aktuellen Release wird gespeichert."
    )

    state["last_release_id"] = (
        current_release_id
    )

    save_state(state)

    if MANUAL_RUN:
        await send_discord_message()

    return

if last_release_id == current_release_id:
    print("")
    print("Kein neuer Release.")

    if MANUAL_RUN:
        await send_discord_message()

    return

print("")
print("=" * 60)
print("!!! NEUER RELEASE GEFUNDEN !!!")
print("=" * 60)

print(
    f"Song: {release['track_name']}"
)

print(
    f"Release: {release['release_name']}"
)

print(
    f"Datum: {release['release_date']}"
)

state["last_release_id"] = (
    current_release_id
)

save_state(state)

await send_discord_message(
    release
)
```

if **name** == "**main**":
try:
asyncio.run(
main()
)

```
except KeyboardInterrupt:
    print("Bot beendet.")

except Exception as error:
    print("")
    print("=" * 60)
    print("FATALER FEHLER")
    print("=" * 60)
    print(error)
    print("=" * 60)

    raise
```

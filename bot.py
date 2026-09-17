import os
import json
import base64
import asyncio
from pathlib import Path

import requests
import discord

ARTIST_NAME = "t-low"

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state.json"

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

MANUAL_RUN = os.getenv("MANUAL_RUN", "false").lower() == "true"

def load_state():
if not STATE_FILE.exists():
return {"last_track_id": None}

```
try:
    with open(STATE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)
except Exception as error:
    print(f"State konnte nicht gelesen werden: {error}")
    return {"last_track_id": None}
```

def save_state(state):
with open(STATE_FILE, "w", encoding="utf-8") as file:
json.dump(state, file, indent=4, ensure_ascii=False)

def get_spotify_token():
print("Hole Spotify Token...")

```
credentials = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"

encoded = base64.b64encode(
    credentials.encode("utf-8")
).decode("utf-8")

response = requests.post(
    "https://accounts.spotify.com/api/token",
    headers={
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/x-www-form-urlencoded"
    },
    data={
        "grant_type": "client_credentials"
    },
    timeout=20
)

if not response.ok:
    print("Spotify Token Fehler:")
    print(response.status_code)
    print(response.text)
    response.raise_for_status()

token = response.json().get("access_token")

if not token:
    raise Exception("Kein Spotify Token erhalten.")

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

def find_artist(token):
print(f"Suche Artist: {ARTIST_NAME}")

```
data = spotify_get(
    "https://api.spotify.com/v1/search",
    token,
    {
        "q": ARTIST_NAME,
        "type": "artist",
        "limit": 10
    }
)

artists = data.get("artists", {}).get("items", [])

if not artists:
    raise Exception(
        f"Artist '{ARTIST_NAME}' nicht gefunden."
    )

for artist in artists:
    if artist.get("name", "").lower() == ARTIST_NAME.lower():
        print(f"Artist gefunden: {artist['name']}")
        print(f"Artist ID: {artist['id']}")
        return artist

print(
    f"Kein exakter Treffer. Verwende: "
    f"{artists[0]['name']}"
)

return artists[0]
```

def get_artist_releases(token, artist_id):
print("Suche Veröffentlichungen...")

```
url = (
    f"https://api.spotify.com/v1/artists/"
    f"{artist_id}/albums"
)

releases = []
offset = 0

while True:
    print(
        f"Lade Veröffentlichungen "
        f"(Offset {offset})..."
    )

    data = spotify_get(
        url,
        token,
        {
            "include_groups": "album,single",
            "limit": 50,
            "offset": offset
        }
    )

    releases.extend(
        data.get("items", [])
    )

    if not data.get("next"):
        break

    offset += 50

    if offset >= 200:
        break

print(
    f"{len(releases)} Veröffentlichungen gefunden."
)

return releases
```

def date_value(date_string):
if not date_string:
return 0

```
try:
    parts = date_string.split("-")

    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 1
    day = int(parts[2]) if len(parts) > 2 else 1

    return (
        year * 10000
        + month * 100
        + day
    )

except Exception:
    return 0
```

def get_latest_release(token, artist_id):
releases = get_artist_releases(
token,
artist_id
)

```
if not releases:
    return None

unique = {}

for release in releases:
    release_id = release.get("id")

    if release_id:
        unique[release_id] = release

releases = list(unique.values())

releases.sort(
    key=lambda release: date_value(
        release.get("release_date")
    ),
    reverse=True
)

latest = releases[0]

album_id = latest.get("id")
album_name = latest.get("name", "Unbekannt")
release_date = latest.get(
    "release_date",
    "Unbekannt"
)
album_type = latest.get(
    "album_type",
    "Unbekannt"
)

print("")
print("=" * 60)
print("NEUESTE VERÖFFENTLICHUNG")
print("=" * 60)
print(f"Name: {album_name}")
print(f"Datum: {release_date}")
print(f"Typ: {album_type}")
print(f"ID: {album_id}")
print("=" * 60)

tracks_data = spotify_get(
    f"https://api.spotify.com/v1/albums/{album_id}/tracks",
    token,
    {
        "limit": 50
    }
)

tracks = tracks_data.get(
    "items",
    []
)

if not tracks:
    print("Keine Tracks gefunden.")
    return None

track = tracks[0]

images = latest.get(
    "images",
    []
)

image_url = None

if images:
    image_url = images[0].get("url")

return {
    "id": track.get("id"),
    "name": track.get(
        "name",
        "Unbekannt"
    ),
    "url": track.get(
        "external_urls",
        {}
    ).get("spotify"),
    "album": album_name,
    "release_date": release_date,
    "image": image_url,
    "album_type": album_type
}
```

def create_embed(track):
embed = discord.Embed(
title=f"🎵 Neuer Song von {ARTIST_NAME}",
description=(
f"**{track['name']}**\n\n"
f"[🎧 Auf Spotify anhören]({track['url']})"
),
url=track["url"],
color=0x1DB954
)

```
embed.add_field(
    name="📅 Release",
    value=track["release_date"],
    inline=True
)

embed.add_field(
    name="💿 Album",
    value=track["album"],
    inline=True
)

if track.get("image"):
    embed.set_thumbnail(
        url=track["image"]
    )

embed.set_footer(
    text="Spotify Release Bot"
)

return embed
```

async def send_discord_message(
message_type,
track=None
):
intents = discord.Intents.default()

```
client = discord.Client(
    intents=intents
)

@client.event
async def on_ready():
    print(
        f"Discord verbunden als: {client.user}"
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

        if message_type == "no_new_song":
            await channel.send(
                "Kein Neuer Song"
            )

            print(
                ">>> Nachricht gesendet."
            )

        elif message_type == "new_song":
            embed = create_embed(track)

            await channel.send(
                embed=embed
            )

            print(
                ">>> Neuer Song gesendet!"
            )

    except Exception as error:
        print(
            f"FEHLER beim Discord-Senden: {error}"
        )

    finally:
        await client.close()

await client.start(
    DISCORD_TOKEN
)
```

async def check_for_new_song():
print("")
print("=" * 60)
print("SPOTIFY RELEASE CHECK")
print("=" * 60)
print(f"Artist: {ARTIST_NAME}")
print(f"Manueller Start: {MANUAL_RUN}")
print("=" * 60)

```
token = get_spotify_token()

artist = find_artist(token)

track = get_latest_release(
    token,
    artist["id"]
)

if track is None:
    print("Keine Veröffentlichung gefunden.")

    if MANUAL_RUN:
        await send_discord_message(
            "no_new_song"
        )

    return

print("")
print(f"Track: {track['name']}")
print(f"Release: {track['release_date']}")
print(f"Album: {track['album']}")
print(f"Track-ID: {track['id']}")

state = load_state()

last_track_id = state.get(
    "last_track_id"
)

print(
    f"Gespeicherte Track-ID: "
    f"{last_track_id}"
)

print(
    f"Aktuelle Track-ID: "
    f"{track['id']}"
)

if last_track_id is None:
    print(
        "Erster Start. Song wird gespeichert."
    )

    state["last_track_id"] = track["id"]

    save_state(state)

    if MANUAL_RUN:
        await send_discord_message(
            "no_new_song"
        )

    return

if last_track_id == track["id"]:
    print("Kein neuer Song.")

    if MANUAL_RUN:
        await send_discord_message(
            "no_new_song"
        )

    return

print("")
print("=" * 60)
print("!!! NEUER SONG GEFUNDEN !!!")
print("=" * 60)

state["last_track_id"] = track["id"]

save_state(state)

await send_discord_message(
    "new_song",
    track
)
```

def check_configuration():
missing = []

```
if not DISCORD_TOKEN:
    missing.append("DISCORD_TOKEN")

if not DISCORD_CHANNEL_ID:
    missing.append("DISCORD_CHANNEL_ID")

if not SPOTIFY_CLIENT_ID:
    missing.append("SPOTIFY_CLIENT_ID")

if not SPOTIFY_CLIENT_SECRET:
    missing.append("SPOTIFY_CLIENT_SECRET")

if missing:
    raise Exception(
        "Fehlende Environment Variables: "
        + ", ".join(missing)
    )
```

async def main():
print("")
print("=" * 60)
print("BOT START")
print("=" * 60)

```
check_configuration()

print(
    "Alle Environment Variables vorhanden."
)

await check_for_new_song()

print("")
print("=" * 60)
print("BOT BEENDET")
print("=" * 60)
```

if **name** == "**main**":
try:
asyncio.run(main())

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

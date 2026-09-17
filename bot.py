```python
import os
import json
import base64
import requests
import discord
from pathlib import Path


# ============================================================
# KONFIGURATION
# ============================================================

ARTIST_NAME = "t-low"

STATE_FILE = Path(__file__).parent / "state.json"

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

# Wird von GitHub Actions gesetzt
MANUAL_RUN = os.environ.get("MANUAL_RUN", "false").lower() == "true"


# ============================================================
# STATE
# ============================================================

def load_state():
    if not STATE_FILE.exists():
        return {
            "last_track_id": None
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "last_track_id": None
        }


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)


# ============================================================
# SPOTIFY
# ============================================================

def get_spotify_token():
    url = "https://accounts.spotify.com/api/token"

    auth = base64.b64encode(
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}".encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {auth}",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    data = {
        "grant_type": "client_credentials"
    }

    response = requests.post(
        url,
        headers=headers,
        data=data,
        timeout=15
    )

    response.raise_for_status()

    return response.json()["access_token"]


def find_artist(token):
    url = "https://api.spotify.com/v1/search"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    params = {
        "q": ARTIST_NAME,
        "type": "artist",
        "limit": 10
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    artists = response.json()["artists"]["items"]

    if not artists:
        raise Exception(f"Artist nicht gefunden: {ARTIST_NAME}")

    for artist in artists:
        if artist["name"].lower() == ARTIST_NAME.lower():
            return artist

    return artists[0]


def get_latest_track(token, artist_id):
    url = f"https://api.spotify.com/v1/artists/{artist_id}/albums"

    headers = {
        "Authorization": f"Bearer {token}"
    }

    params = {
        "include_groups": "album,single",
        "market": "DE",
        "limit": 50
    }

    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    albums = response.json()["items"]

    if not albums:
        return None

    albums.sort(
        key=lambda x: x["release_date"],
        reverse=True
    )

    newest_album = albums[0]

    album_id = newest_album["id"]

    tracks_url = f"https://api.spotify.com/v1/albums/{album_id}/tracks"

    response = requests.get(
        tracks_url,
        headers=headers,
        params={
            "market": "DE",
            "limit": 50
        },
        timeout=15
    )

    response.raise_for_status()

    tracks = response.json()["items"]

    if not tracks:
        return None

    track = tracks[0]

    return {
        "id": track["id"],
        "name": track["name"],
        "url": track["external_urls"]["spotify"],
        "album": newest_album["name"],
        "release_date": newest_album["release_date"],
        "image": (
            newest_album["images"][0]["url"]
            if newest_album["images"]
            else None
        )
    }


# ============================================================
# DISCORD
# ============================================================

class SpotifyBot(discord.Client):

    async def on_ready(self):
        print(f"Discord Bot gestartet: {self.user}")

        try:
            await check_for_new_song()
        except Exception as e:
            print(f"Fehler beim Prüfen: {e}")

        await self.close()


# ============================================================
# DISCORD NACHRICHTEN
# ============================================================

async def send_message(message_type, track=None):

    intents = discord.Intents.default()

    client = discord.Client(
        intents=intents
    )

    @client.event
    async def on_ready():

        channel = client.get_channel(
            DISCORD_CHANNEL_ID
        )

        if channel is None:
            print("Discord Channel nicht gefunden.")
            await client.close()
            return

        # ----------------------------------------------------
        # KEIN NEUER SONG
        # ----------------------------------------------------

        if message_type == "no_new_song":

            await channel.send(
                "Kein Neuer Song"
            )

            print("Discord Nachricht gesendet: Kein Neuer Song")

        # ----------------------------------------------------
        # NEUER SONG
        # ----------------------------------------------------

        elif message_type == "new_song":

            embed = discord.Embed(
                title=f"🎵 Neuer Song von {ARTIST_NAME}",
                description=(
                    f"**{track['name']}**\n\n"
                    f"[🎧 Auf Spotify anhören]({track['url']})"
                ),
                url=track["url"],
                color=0x1DB954
            )

            embed.add_field(
                name="Release",
                value=track["release_date"],
                inline=True
            )

            embed.add_field(
                name="Album",
                value=track["album"],
                inline=True
            )

            if track["image"]:
                embed.set_thumbnail(
                    url=track["image"]
                )

            embed.set_footer(
                text="Spotify Release Bot"
            )

            await channel.send(
                embed=embed
            )

            print(
                f"Discord Nachricht gesendet: {track['name']}"
            )

        await client.close()

    await client.start(DISCORD_TOKEN)


# ============================================================
# SONG PRÜFEN
# ============================================================

async def check_for_new_song():

    print(f"Prüfe neuen Song von: {ARTIST_NAME}")

    print(
        f"Manueller Start: {'JA' if MANUAL_RUN else 'NEIN'}"
    )

    spotify_token = get_spotify_token()

    artist = find_artist(spotify_token)

    print(
        f"Artist gefunden: "
        f"{artist['name']} ({artist['id']})"
    )

    track = get_latest_track(
        spotify_token,
        artist["id"]
    )

    if not track:
        print("Kein Song gefunden.")

        # Bei manuellem Start trotzdem melden
        if MANUAL_RUN:
            await send_message("no_new_song")

        return

    print(
        f"Neueste Veröffentlichung: "
        f"{track['name']} ({track['release_date']})"
    )

    state = load_state()

    last_track_id = state.get("last_track_id")

    # --------------------------------------------------------
    # ERSTER START
    # --------------------------------------------------------

    if last_track_id is None:

        print(
            "Erster Start. Aktuellen Song speichern."
        )

        state["last_track_id"] = track["id"]
        save_state(state)

        # Bei manuellem Start trotzdem Nachricht senden
        if MANUAL_RUN:
            await send_message("no_new_song")

        return

    # --------------------------------------------------------
    # KEIN NEUER SONG
    # --------------------------------------------------------

    if last_track_id == track["id"]:

        print("Kein neuer Song.")

        # Nur bei manuellem Start Discord-Nachricht
        if MANUAL_RUN:
            await send_message("no_new_song")

        return

    # --------------------------------------------------------
    # NEUER SONG
    # --------------------------------------------------------

    print(
        f"NEUER SONG GEFUNDEN: {track['name']}"
    )

    state["last_track_id"] = track["id"]
    save_state(state)

    await send_message(
        "new_song",
        track
    )


# ============================================================
# START
# ============================================================

if not DISCORD_TOKEN:
    raise Exception("DISCORD_TOKEN fehlt!")

if not DISCORD_CHANNEL_ID:
    raise Exception("DISCORD_CHANNEL_ID fehlt!")

if not SPOTIFY_CLIENT_ID:
    raise Exception("SPOTIFY_CLIENT_ID fehlt!")

if not SPOTIFY_CLIENT_SECRET:
    raise Exception("SPOTIFY_CLIENT_SECRET fehlt!")


intents = discord.Intents.default()

client = SpotifyBot(
    intents=intents
)

client.run(DISCORD_TOKEN)
```

import os
import json
import base64
from pathlib import Path

import requests
import discord


ARTIST_NAME = "t-low"

STATE_FILE = Path(__file__).parent / "state.json"

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = int(os.environ.get("DISCORD_CHANNEL_ID", "0"))

SPOTIFY_CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET")

MANUAL_RUN = os.environ.get("MANUAL_RUN", "false").lower() == "true"


# ============================================================
# STATE
# ============================================================

def load_state():
    if not STATE_FILE.exists():
        return {"last_track_id": None}

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except Exception:
        return {"last_track_id": None}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as file:
        json.dump(state, file, indent=4)


# ============================================================
# SPOTIFY
# ============================================================

def get_spotify_token():
    print("Hole Spotify Token...")

    credentials = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"

    encoded = base64.b64encode(
        credentials.encode()
    ).decode()

    response = requests.post(
        "https://accounts.spotify.com/api/token",
        headers={
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={
            "grant_type": "client_credentials"
        },
        timeout=15
    )

    response.raise_for_status()

    print("Spotify Token erhalten.")

    return response.json()["access_token"]


def find_artist(token):
    print(f"Suche Artist: {ARTIST_NAME}")

    response = requests.get(
        "https://api.spotify.com/v1/search",
        headers={
            "Authorization": f"Bearer {token}"
        },
        params={
            "q": ARTIST_NAME,
            "type": "artist",
            "limit": 10
        },
        timeout=15
    )

    response.raise_for_status()

    artists = response.json()["artists"]["items"]

    if not artists:
        raise Exception(
            f"Artist nicht gefunden: {ARTIST_NAME}"
        )

    for artist in artists:
        if artist["name"].lower() == ARTIST_NAME.lower():
            print(
                f"Artist gefunden: {artist['name']}"
            )
            return artist

    print(
        f"Exakter Artist nicht gefunden. "
        f"Verwende: {artists[0]['name']}"
    )

    return artists[0]


def get_latest_track(token, artist_id):

    print("Suche letzte Veröffentlichung...")

    response = requests.get(
        f"https://api.spotify.com/v1/artists/{artist_id}/albums",
        headers={
            "Authorization": f"Bearer {token}"
        },
        params={
            "include_groups": "album,single",
            "market": "DE",
            "limit": 50
        },
        timeout=15
    )

    response.raise_for_status()

    albums = response.json()["items"]

    if not albums:
        return None

    albums.sort(
        key=lambda album: album["release_date"],
        reverse=True
    )

    newest_album = albums[0]

    print(
        f"Letzte Veröffentlichung: "
        f"{newest_album['name']} "
        f"({newest_album['release_date']})"
    )

    response = requests.get(
        f"https://api.spotify.com/v1/albums/{newest_album['id']}/tracks",
        headers={
            "Authorization": f"Bearer {token}"
        },
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

class DiscordSender(discord.Client):

    async def on_ready(self):

        print(f"Discord verbunden als: {self.user}")
        print(f"Channel ID: {DISCORD_CHANNEL_ID}")

        channel = self.get_channel(
            DISCORD_CHANNEL_ID
        )

        if channel is None:
            print(
                "FEHLER: Channel wurde nicht gefunden!"
            )

            print(
                "Versuche Channel direkt über Discord zu laden..."
            )

            try:
                channel = await self.fetch_channel(
                    DISCORD_CHANNEL_ID
                )

                print(
                    f"Channel gefunden: {channel}"
                )

            except Exception as error:
                print(
                    f"FEHLER beim Laden des Channels: {error}"
                )

                await self.close()
                return

        print(
            f"Discord Channel gefunden: "
            f"{channel.name}"
        )

        try:

            if self.message_type == "no_new_song":

                await channel.send(
                    "Kein Neuer Song"
                )

                print(
                    ">>> 'Kein Neuer Song' wurde gesendet."
                )

            elif self.message_type == "new_song":

                track = self.track

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
                    ">>> Neuer Song wurde gesendet."
                )

        except Exception as error:

            print(
                f"FEHLER beim Senden: {error}"
            )

        await self.close()


async def send_discord_message(
    message_type,
    track=None
):

    intents = discord.Intents.default()

    client = DiscordSender(
        intents=intents
    )

    client.message_type = message_type
    client.track = track

    await client.start(
        DISCORD_TOKEN
    )


# ============================================================
# CHECK
# ============================================================

async def check_for_new_song():

    print("")
    print("=" * 50)
    print("SPOTIFY RELEASE CHECK")
    print("=" * 50)

    print(
        f"Artist: {ARTIST_NAME}"
    )

    print(
        f"Manueller Start: {MANUAL_RUN}"
    )

    print("=" * 50)

    token = get_spotify_token()

    artist = find_artist(token)

    track = get_latest_track(
        token,
        artist["id"]
    )

    if track is None:

        print(
            "Kein Track gefunden."
        )

        if MANUAL_RUN:
            print(
                "Manueller Start -> sende "
                "'Kein Neuer Song'"
            )

            await send_discord_message(
                "no_new_song"
            )

        return

    print(
        f"Track: {track['name']}"
    )

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

    # ========================================================
    # ERSTER START
    # ========================================================

    if last_track_id is None:

        print(
            "Noch kein Song gespeichert."
        )

        state["last_track_id"] = track["id"]

        save_state(state)

        if MANUAL_RUN:

            print(
                "Manueller Start -> "
                "sende 'Kein Neuer Song'"
            )

            await send_discord_message(
                "no_new_song"
            )

        return

    # ========================================================
    # KEIN NEUER SONG
    # ========================================================

    if last_track_id == track["id"]:

        print(
            "Kein neuer Song."
        )

        if MANUAL_RUN:

            print(
                "Manueller Start -> "
                "sende 'Kein Neuer Song'"
            )

            await send_discord_message(
                "no_new_song"
            )

        return

    # ========================================================
    # NEUER SONG
    # ========================================================

    print(
        "!!! NEUER SONG GEFUNDEN !!!"
    )

    state["last_track_id"] = track["id"]

    save_state(state)

    await send_discord_message(
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


class MainBot(discord.Client):

    async def on_ready(self):

        print(
            f"Bot gestartet: {self.user}"
        )

        try:
            await check_for_new_song()

        except Exception as error:

            print(
                f"FATALER FEHLER: {error}"
            )

            raise

        finally:
            await self.close()


client = MainBot(
    intents=intents
)

client.run(
    DISCORD_TOKEN
)

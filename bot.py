```python
import os
import json
import base64
from pathlib import Path

import requests
import discord


# ============================================================
# KONFIGURATION
# ============================================================

ARTIST_NAME = "t-low"

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state.json"

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

MANUAL_RUN = os.getenv("MANUAL_RUN", "false").lower() == "true"


# ============================================================
# HILFSFUNKTIONEN
# ============================================================

def load_state():
    if not STATE_FILE.exists():
        return {
            "last_track_id": None
        }

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except Exception as error:
        print(f"State konnte nicht gelesen werden: {error}")

        return {
            "last_track_id": None
        }


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as file:
            json.dump(
                state,
                file,
                indent=4,
                ensure_ascii=False
            )

        print("State gespeichert.")

    except Exception as error:
        print(f"FEHLER beim Speichern des States: {error}")


def spotify_request(method, url, token, **kwargs):
    """
    Führt einen Spotify API Request aus und gibt bei Fehlern
    die tatsächliche Spotify Fehlermeldung aus.
    """

    headers = kwargs.pop("headers", {})

    headers["Authorization"] = f"Bearer {token}"

    response = requests.request(
        method,
        url,
        headers=headers,
        timeout=20,
        **kwargs
    )

    if not response.ok:
        print("")
        print("=" * 60)
        print("SPOTIFY API FEHLER")
        print("=" * 60)
        print(f"HTTP Status: {response.status_code}")
        print(f"URL: {response.url}")

        try:
            print(
                json.dumps(
                    response.json(),
                    indent=4,
                    ensure_ascii=False
                )
            )
        except Exception:
            print(response.text)

        print("=" * 60)
        print("")

        response.raise_for_status()

    return response


# ============================================================
# SPOTIFY TOKEN
# ============================================================

def get_spotify_token():

    print("Hole Spotify Token...")

    credentials = (
        f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    )

    encoded_credentials = base64.b64encode(
        credentials.encode("utf-8")
    ).decode("utf-8")

    response = requests.post(
        "https://accounts.spotify.com/api/token",

        headers={
            "Authorization": f"Basic {encoded_credentials}",
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
        raise Exception(
            "Spotify hat keinen Access Token zurückgegeben."
        )

    print("Spotify Token erhalten.")

    return token


# ============================================================
# ARTIST SUCHEN
# ============================================================

def find_artist(token):

    print(f"Suche Artist: {ARTIST_NAME}")

    response = spotify_request(
        "GET",
        "https://api.spotify.com/v1/search",
        token,

        params={
            "q": ARTIST_NAME,
            "type": "artist",
            "limit": 10
        }
    )

    artists = response.json().get(
        "artists",
        {}
    ).get(
        "items",
        []
    )

    if not artists:
        raise Exception(
            f"Artist '{ARTIST_NAME}' wurde nicht gefunden."
        )

    # Erst nach exakt passendem Namen suchen
    for artist in artists:

        if artist["name"].lower() == ARTIST_NAME.lower():

            print(
                f"Artist gefunden: "
                f"{artist['name']}"
            )

            print(
                f"Artist ID: "
                f"{artist['id']}"
            )

            return artist

    # Falls kein exakter Treffer vorhanden ist
    print(
        f"Kein exakter Treffer für '{ARTIST_NAME}'."
    )

    print(
        f"Verwende stattdessen: "
        f"{artists[0]['name']}"
    )

    print(
        f"Artist ID: "
        f"{artists[0]['id']}"
    )

    return artists[0]


# ============================================================
# ALLE VERÖFFENTLICHUNGEN HOLEN
# ============================================================

def get_artist_albums(token, artist_id):

    print("Suche Veröffentlichungen...")

    all_albums = []

    url = (
        f"https://api.spotify.com/v1/artists/"
        f"{artist_id}/albums"
    )

    offset = 0

    while True:

        print(
            f"Lade Veröffentlichungen "
            f"(Offset {offset})..."
        )

        response = spotify_request(
            "GET",
            url,
            token,

            params={
                "include_groups": "album,single",
                "limit": 50,
                "offset": offset
            }
        )

        data = response.json()

        items = data.get(
            "items",
            []
        )

        all_albums.extend(items)

        if not data.get("next"):
            break

        offset += 50

        # Sicherheitslimit
        if offset >= 200:
            break

    print(
        f"Insgesamt {len(all_albums)} "
        f"Veröffentlichungen gefunden."
    )

    return all_albums


# ============================================================
# DATUM VERGLEICHEN
# ============================================================

def release_date_value(date_string):

    """
    Spotify kann folgende Datumsformate liefern:

    YYYY
    YYYY-MM
    YYYY-MM-DD

    Wir wandeln alles in YYYYMMDD um,
    damit sauber sortiert werden kann.
    """

    if not date_string:
        return 0

    parts = date_string.split("-")

    try:

        year = int(parts[0])

        month = (
            int(parts[1])
            if len(parts) >= 2
            else 1
        )

        day = (
            int(parts[2])
            if len(parts) >= 3
            else 1
        )

        return (
            year * 10000
            + month * 100
            + day
        )

    except Exception:
        return 0


# ============================================================
# NEUESTE VERÖFFENTLICHUNG
# ============================================================

def get_latest_release(token, artist_id):

    albums = get_artist_albums(
        token,
        artist_id
    )

    if not albums:
        return None

    # Nach Release-Datum sortieren
    albums.sort(
        key=lambda album: release_date_value(
            album.get("release_date")
        ),
        reverse=True
    )

    # Doppelte Alben entfernen
    unique_albums = []

    seen_ids = set()

    for album in albums:

        album_id = album.get("id")

        if not album_id:
            continue

        if album_id in seen_ids:
            continue

        seen_ids.add(album_id)

        unique_albums.append(album)

    if not unique_albums:
        return None

    newest_album = unique_albums[0]

    album_name = newest_album.get(
        "name",
        "Unbekannt"
    )

    release_date = newest_album.get(
        "release_date",
        "Unbekannt"
    )

    album_type = newest_album.get(
        "album_type",
        "Unbekannt"
    )

    album_id = newest_album.get(
        "id"
    )

    print("")
    print(
        f"Neueste Veröffentlichung: "
        f"{album_name}"
    )

    print(
        f"Datum: {release_date}"
    )

    print(
        f"Typ: {album_type}"
    )

    print(
        f"Album-ID: {album_id}"
    )

    # --------------------------------------------------------
    # Tracks der Veröffentlichung holen
    # --------------------------------------------------------

    tracks_url = (
        f"https://api.spotify.com/v1/albums/"
        f"{album_id}/tracks"
    )

    response = spotify_request(
        "GET",
        tracks_url,
        token,

        params={
            "limit": 50
        }
    )

    tracks = response.json().get(
        "items",
        []
    )

    if not tracks:
        print("Keine Tracks gefunden.")
        return None

    # Den ersten Track verwenden.
    # Bei Singles ist das normalerweise genau der Song.
    track = tracks[0]

    track_id = track.get("id")

    track_name = track.get(
        "name",
        "Unbekannt"
    )

    spotify_url = (
        track.get("external_urls", {})
        .get("spotify")
    )

    images = newest_album.get(
        "images",
        []
    )

    image_url = (
        images[0]["url"]
        if images
        else None
    )

    return {
        "id": track_id,
        "name": track_name,
        "url": spotify_url,
        "album": album_name,
        "release_date": release_date,
        "image": image_url,
        "album_type": album_type
    }


# ============================================================
# DISCORD EMBED
# ============================================================

def create_song_embed(track):

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


# ============================================================
# DISCORD NACHRICHT SENDEN
# ============================================================

async def send_discord_message(message_type, track=None):

    intents = discord.Intents.default()

    client = discord.Client(
        intents=intents
    )

    @client.event
    async def on_ready():

        print("")
        print(
            f"Discord verbunden als: "
            f"{client.user}"
        )

        try:

            channel = client.get_channel(
                int(DISCORD_CHANNEL_ID)
            )

            if channel is None:

                print(
                    "Channel nicht im Cache."
                )

                print(
                    "Lade Channel direkt..."
                )

                channel = await client.fetch_channel(
                    int(DISCORD_CHANNEL_ID)
                )

            print(
                f"Discord Channel gefunden: "
                f"{channel.name}"
            )

            # ------------------------------------------------
            # KEIN NEUER SONG
            # ------------------------------------------------

            if message_type == "no_new_song":

                await channel.send(
                    "Kein Neuer Song"
                )

                print(
                    ">>> 'Kein Neuer Song' gesendet."
                )

            # ------------------------------------------------
            # NEUER SONG
            # ------------------------------------------------

            elif message_type == "new_song":

                if track is None:
                    raise Exception(
                        "Track fehlt beim Senden."
                    )

                embed = create_song_embed(
                    track
                )

                await channel.send(
                    embed=embed
                )

                print(
                    ">>> Neuer Song gesendet!"
                )

        except Exception as error:

            print("")
            print(
                "FEHLER beim Senden an Discord:"
            )
            print(error)

        finally:

            await client.close()

    await client.start(
        DISCORD_TOKEN
    )


# ============================================================
# RELEASE CHECK
# ============================================================

async def check_for_new_song():

    print("")
    print("=" * 60)
    print("SPOTIFY RELEASE CHECK")
    print("=" * 60)

    print(
        f"Artist: {ARTIST_NAME}"
    )

    print(
        f"Manueller Start: {MANUAL_RUN}"
    )

    print("=" * 60)

    # --------------------------------------------------------
    # Spotify Token
    # --------------------------------------------------------

    token = get_spotify_token()

    # --------------------------------------------------------
    # Artist
    # --------------------------------------------------------

    artist = find_artist(
        token
    )

    artist_id = artist["id"]

    # --------------------------------------------------------
    # Neueste Veröffentlichung
    # --------------------------------------------------------

    track = get_latest_release(
        token,
        artist_id
    )

    if track is None:

        print(
            "Keine Veröffentlichung gefunden."
        )

        if MANUAL_RUN:

            await send_discord_message(
                "no_new_song"
            )

        return

    # --------------------------------------------------------
    # Track Informationen
    # --------------------------------------------------------

    print("")
    print(
        f"Track: {track['name']}"
    )

    print(
        f"Release: {track['release_date']}"
    )

    print(
        f"Album: {track['album']}"
    )

    print(
        f"Track-ID: {track['id']}"
    )

    # --------------------------------------------------------
    # State laden
    # --------------------------------------------------------

    state = load_state()

    last_track_id = state.get(
        "last_track_id"
    )

    print("")
    print(
        f"Gespeicherte Track-ID: "
        f"{last_track_id}"
    )

    print(
        f"Aktuelle Track-ID: "
        f"{track['id']}"
    )

    # --------------------------------------------------------
    # ERSTER START
    # --------------------------------------------------------

    if last_track_id is None:

        print("")
        print(
            "Noch kein Song im State gespeichert."
        )

        state["last_track_id"] = track["id"]

        save_state(
            state
        )

        if MANUAL_RUN:

            print(
                "Manueller Start -> "
                "kein neuer Song."
            )

            await send_discord_message(
                "no_new_song"
            )

        return

    # --------------------------------------------------------
    # KEIN NEUER SONG
    # --------------------------------------------------------

    if last_track_id == track["id"]:

        print("")
        print(
            "Kein neuer Song."
        )

        if MANUAL_RUN:

            print(
                "Manueller Start -> "
                "sende Nachricht."
            )

            await send_discord_message(
                "no_new_song"
            )

        return

    # --------------------------------------------------------
    # NEUER SONG
    # --------------------------------------------------------

    print("")
    print("=" * 60)
    print("!!! NEUER SONG GEFUNDEN !!!")
    print("=" * 60)

    print(
        f"Song: {track['name']}"
    )

    print(
        f"Release: {track['release_date']}"
    )

    # State aktualisieren
    state["last_track_id"] = track["id"]

    save_state(
        state
    )

    # Discord
    await send_discord_message(
        "new_song",
        track
    )


# ============================================================
# KONFIGURATION PRÜFEN
# ============================================================

def check_configuration():

    missing = []

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
            "Fehlende Environment Variables: "
            + ", ".join(missing)
        )


# ============================================================
# MAIN
# ============================================================

async def main():

    print("")
    print("=" * 60)
    print("BOT START")
    print("=" * 60)

    check_configuration()

    print(
        "Alle Environment Variables vorhanden."
    )

    await check_for_new_song()

    print("")
    print("=" * 60)
    print("BOT BEENDET")
    print("=" * 60)


if __name__ == "__main__":

    import asyncio

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "Bot manuell beendet."
        )

    except Exception as error:

        print("")
        print("=" * 60)
        print("FATALER FEHLER")
        print("=" * 60)
        print(error)
        print("=" * 60)

        raise

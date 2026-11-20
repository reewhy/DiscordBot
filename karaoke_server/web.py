"""Server web del karaoke: API HTTP + Socket.IO + frontend compilato.

Gira dentro lo stesso processo (e lo stesso event loop) del bot.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import aiohttp
import socketio
from aiohttp import web

from .rooms import Room, RoomManager
from .youtube import YouTubeError, YouTubeSearch

log = logging.getLogger("karaoke.web")

DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
VIDEO_ID = re.compile(r"^[\w-]{11}$")


@dataclass
class KaraokeSettings:
    client_id: str
    client_secret: str
    youtube_api_key: str
    dist_dir: Path  # cartella "dist" del frontend compilato (può non esistere in sviluppo)


def clip(value, n: int) -> str:
    return str("" if value is None else value)[:n]


def to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def create_app(settings: KaraokeSettings, system=None) -> web.Application:
    """`system` è un KaraokeSystem (database) oppure None per disattivare le statistiche."""
    sio = socketio.AsyncServer(async_mode="aiohttp", cors_allowed_origins="*")
    app = web.Application()
    sio.attach(app)

    youtube = YouTubeSearch(settings.youtube_api_key)
    sid_room: dict[str, str] = {}

    # ---------- statistiche ----------
    def record_play(room: Room, item: dict) -> None:
        if system is None or room.guild_id is None:
            return  # modalità sviluppo o statistiche spente
        singer_id = to_int(item["addedBy"].get("id"))
        if singer_id is None:
            return
        try:
            system.record_play(
                guild_id=room.guild_id,
                channel_id=room.channel_id,
                video_id=item["videoId"],
                title=item["title"],
                channel_title=item["channel"],
                singer_id=singer_id,
                singer_name=item["addedBy"].get("username", ""),
            )
        except Exception:
            log.exception("Impossibile salvare il brano nelle statistiche")

    rooms = RoomManager(on_track_start=record_play)

    # ---------- HTTP ----------
    async def http_session(app: web.Application):
        app["http"] = aiohttp.ClientSession()
        yield
        await app["http"].close()

    app.cleanup_ctx.append(http_session)

    async def token(request: web.Request) -> web.Response:
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Richiesta non valida"}, status=400)

        form = {
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
            "grant_type": "authorization_code",
            "code": str(body.get("code", "")),
        }
        try:
            async with request.app["http"].post(DISCORD_TOKEN_URL, data=form) as resp:
                data = await resp.json()
                if resp.status != 200:
                    return web.json_response(
                        {"error": data.get("error_description", "Scambio token fallito")}, status=400
                    )
        except aiohttp.ClientError:
            log.exception("Errore nello scambio del token")
            return web.json_response({"error": "Errore interno"}, status=500)
        return web.json_response({"access_token": data["access_token"]})

    async def search(request: web.Request) -> web.Response:
        q = request.query.get("q", "").strip()
        if len(q) < 2:
            return web.json_response({"results": []})
        try:
            results = await youtube.search(request.app["http"], q)
        except (YouTubeError, aiohttp.ClientError) as e:
            log.error("Ricerca YouTube fallita: %s", e)
            return web.json_response(
                {"error": "Ricerca YouTube non disponibile (quota o chiave API?)"}, status=502
            )
        return web.json_response({"results": results})

    app.router.add_post("/api/token", token)
    app.router.add_get("/api/search", search)

    # Frontend compilato (in sviluppo si usa il server di Vite, quindi può mancare).
    dist = settings.dist_dir
    if (dist / "index.html").exists():
        async def index(_request: web.Request) -> web.FileResponse:
            return web.FileResponse(dist / "index.html")

        app.router.add_get("/", index)
        if (dist / "assets").is_dir():
            app.router.add_static("/assets", dist / "assets")
    else:
        log.warning("Frontend non trovato in %s (esegui 'npm run build' nella cartella client)", dist)

    # ---------- Socket.IO ----------
    async def push(room: Room) -> None:
        await sio.emit("state", room.public_state(), room=room.instance_id)

    def room_of(sid: str) -> Room | None:
        rid = sid_room.get(sid)
        return rooms.get(rid) if rid else None

    @sio.on("join")
    async def on_join(sid, data=None):
        data = data if isinstance(data, dict) else {}
        rid = clip(data.get("instanceId"), 100)
        if not rid:
            return
        room = rooms.get_or_create(rid)
        room.guild_id = to_int(data.get("guildId")) or room.guild_id
        room.channel_id = to_int(data.get("channelId")) or room.channel_id

        await sio.enter_room(sid, rid)
        sid_room[sid] = rid

        # NB: l'utente arriva dal client. Per un uso pubblico verificalo con l'access token.
        user = data.get("user") if isinstance(data.get("user"), dict) else {}
        room.users[sid] = {
            "id": clip(user.get("id"), 40),
            "username": clip(user.get("username"), 40),
            "avatar": clip(user.get("avatar"), 200) or None,
        }
        await push(room)

    def action(event: str):
        """Registra un evento che modifica la stanza e poi manda lo stato a tutti."""
        def decorator(fn):
            @sio.on(event)
            async def handler(sid, *args):
                room = room_of(sid)
                if room is None:
                    return
                fn(room, sid, *args)
                await push(room)
            return fn
        return decorator

    @action("queue:add")
    def _add(room: Room, sid: str, track=None):
        if not isinstance(track, dict) or not VIDEO_ID.match(str(track.get("videoId", ""))):
            return
        user = room.users.get(sid)
        if not user:
            return
        room.add_track(
            {
                "videoId": track["videoId"],
                "title": clip(track.get("title"), 150),
                "channel": clip(track.get("channel"), 80),
            },
            user,
        )

    @action("queue:remove")
    def _remove(room: Room, sid: str, qid=None):
        room.remove_track(str(qid))

    @action("player:play")
    def _play(room: Room, sid: str, *_):
        room.play()

    @action("player:pause")
    def _pause(room: Room, sid: str, *_):
        room.pause()

    @action("player:seek")
    def _seek(room: Room, sid: str, position=0):
        room.seek(position)

    @action("player:next")
    def _next(room: Room, sid: str, *_):
        room.start_next()

    @action("player:ended")
    def _ended(room: Room, sid: str, qid=None):
        room.ended(str(qid))

    @sio.event
    async def disconnect(sid, *_):
        rid = sid_room.pop(sid, None)
        room = rooms.get(rid) if rid else None
        if room is None:
            return
        room.users.pop(sid, None)
        await push(room)
        rooms.drop_if_empty(rid)

    return app

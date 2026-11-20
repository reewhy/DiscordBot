"""Stato condiviso del karaoke: una stanza per ogni istanza di Activity."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class Room:
    instance_id: str
    guild_id: int | None = None
    channel_id: int | None = None
    queue: list[dict] = field(default_factory=list)
    current: dict | None = None
    status: str = "paused"          # "playing" | "paused"
    position: float = 0.0           # secondi, valido al momento updated_at
    updated_at: int = field(default_factory=now_ms)
    users: dict[str, dict] = field(default_factory=dict)   # sid -> utente
    # Chiamata ogni volta che un brano diventa quello in corso (serve per le statistiche).
    on_track_start: Callable[["Room", dict], None] | None = None

    # ---- lettura ----
    def live_position(self) -> float:
        if self.status != "playing":
            return self.position
        return self.position + (now_ms() - self.updated_at) / 1000

    def public_state(self) -> dict:
        unique = {u["id"]: u for u in self.users.values()}
        return {
            "queue": self.queue,
            "current": self.current,
            "status": self.status,
            "position": self.position,
            "updatedAt": self.updated_at,
            "serverNow": now_ms(),
            "users": list(unique.values()),
        }

    # ---- scrittura ----
    def _touch(self) -> None:
        self.updated_at = now_ms()

    def _set_current(self, item: dict | None) -> None:
        self.current = item
        self.status = "playing" if item else "paused"
        self.position = 0.0
        self._touch()
        if item and self.on_track_start:
            self.on_track_start(self, item)

    def start_next(self) -> None:
        self._set_current(self.queue.pop(0) if self.queue else None)

    def add_track(self, track: dict, user: dict) -> None:
        item = {"qid": str(uuid.uuid4()), **track, "addedBy": user}
        if self.current is None:
            self._set_current(item)
        else:
            self.queue.append(item)

    def remove_track(self, qid: str) -> None:
        self.queue = [t for t in self.queue if t["qid"] != qid]

    def play(self) -> None:
        if self.current and self.status != "playing":
            self.status = "playing"
            self._touch()

    def pause(self) -> None:
        if self.current and self.status != "paused":
            self.position = self.live_position()
            self.status = "paused"
            self._touch()

    def seek(self, position) -> None:
        if not self.current:
            return
        try:
            self.position = max(0.0, float(position))
        except (TypeError, ValueError):
            self.position = 0.0
        self._touch()

    def ended(self, qid: str) -> None:
        """Tutti i client mandano 'ended': si avanza solo se il brano è ancora quello corrente."""
        if self.current and self.current["qid"] == qid:
            self.start_next()


class RoomManager:
    def __init__(self, on_track_start: Callable[[Room, dict], None] | None = None):
        self._rooms: dict[str, Room] = {}
        self._on_track_start = on_track_start

    def get(self, instance_id: str) -> Room | None:
        return self._rooms.get(instance_id)

    def get_or_create(self, instance_id: str) -> Room:
        room = self._rooms.get(instance_id)
        if room is None:
            room = Room(instance_id=instance_id, on_track_start=self._on_track_start)
            self._rooms[instance_id] = room
        return room

    def drop_if_empty(self, instance_id: str) -> None:
        room = self._rooms.get(instance_id)
        if room and not room.users:
            del self._rooms[instance_id]

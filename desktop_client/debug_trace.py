from __future__ import annotations

import logging
from dataclasses import dataclass
from time import time


logger = logging.getLogger("atri_pet.behavior")


@dataclass(frozen=True)
class DebugTraceEvent:
    kind: str
    tick: int
    data: dict[str, object]
    timestamp: float


class DebugTrace:
    def __init__(self, enabled: bool = False):
        self.enabled = bool(enabled)
        self.events: list[DebugTraceEvent] = []

    def record(self, kind: str, tick: int, **data):
        if not self.enabled:
            return
        event = DebugTraceEvent(kind=kind, tick=int(tick), data=dict(data), timestamp=time())
        self.events.append(event)
        logger.debug("[behavior] %s tick=%s data=%s", kind, event.tick, event.data)

    def behavior_switch(self, tick: int, name: str | None, forced: bool):
        self.record("behavior_switch", tick, name=name or "", forced=forced)

    def action_switch(self, tick: int, name: str | None, forced: bool):
        self.record("action_switch", tick, name=name or "", forced=forced)

    def forced_behavior(self, tick: int, name: str):
        self.record("forced_behavior", tick, name=name)

    def forced_action(self, tick: int, name: str):
        self.record("forced_action", tick, name=name)

    def lost_ground(self, tick: int, behavior: str | None, action: str | None):
        self.record("lost_ground", tick, behavior=behavior or "", action=action or "")

    def fallback_fall(self, tick: int, name: str | None):
        self.record("fallback_fall", tick, name=name or "")

    def drag_start(self, tick: int, behavior: str | None):
        self.record("drag_start", tick, behavior=behavior or "")

    def drag_end(self, tick: int, thrown: bool):
        self.record("drag_end", tick, thrown=thrown)

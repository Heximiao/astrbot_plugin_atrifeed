from collections import deque
from dataclasses import dataclass


@dataclass
class OverrideRequest:
    kind: str
    name: str
    params: dict[str, object]
    priority: int = 100


class OverrideController:
    def __init__(self):
        self._queue: deque[OverrideRequest] = deque()

    def push_behavior(self, name: str, **params):
        self._queue.append(OverrideRequest(kind="behavior", name=name, params=params))

    def push_action(self, name: str, **params):
        self._queue.append(OverrideRequest(kind="action", name=name, params=params))

    def pop(self) -> OverrideRequest | None:
        if not self._queue:
            return None
        best = max(self._queue, key=lambda item: item.priority)
        self._queue.remove(best)
        return best

    def clear(self):
        self._queue.clear()

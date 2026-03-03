from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional, Sequence


class MatchMode(str, Enum):
    """Keyword matching strategy."""

    EXACT = "exact"
    STARTS_WITH = "starts_with"
    CONTAINS = "contains"


class PermissionLevel(str, Enum):
    """Keyword route permission level."""

    MEMBER = "member"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class KeywordRoute:
    """Maps a keyword to an action identifier."""

    keyword: str
    action: str
    permission: PermissionLevel = PermissionLevel.MEMBER


class KeywordRouter:
    """Routes message strings to actions based on keyword rules.

    This module is intentionally framework-agnostic so it can be unit-tested
    without AstrBot runtime dependencies.
    """

    def __init__(self, routes: Sequence[KeywordRoute]):
        self._routes = list(routes)
        self._routes_by_keyword_len_desc = sorted(
            self._routes, key=lambda r: len(r.keyword), reverse=True
        )

    def match(self, message: str, *, mode: MatchMode) -> Optional[str]:
        route = self.match_route(message, mode=mode)
        if route is None:
            return None
        return route.action

    def match_route(self, message: str, *, mode: MatchMode) -> Optional[KeywordRoute]:
        text = message.strip()
        if not text:
            return None

        routes: Iterable[KeywordRoute] = self._routes
        if mode in (MatchMode.CONTAINS, MatchMode.STARTS_WITH):
            routes = self._routes_by_keyword_len_desc

        for route in routes:
            if self._matches(text, route.keyword, mode):
                return route
        return None

    def match_command(self, message: str) -> Optional[str]:
        route = self.match_command_route(message)
        if route is None:
            return None
        return route.action

    def match_command_route(self, message: str) -> Optional[KeywordRoute]:
        text = self._normalize_command_text(message)
        if not text:
            return None

        for route in self._routes_by_keyword_len_desc:
            if text == route.keyword:
                return route

            if not text.startswith(route.keyword):
                continue

            next_index = len(route.keyword)
            if next_index >= len(text):
                return route

            next_char = text[next_index]
            if next_char.isspace() or next_char in {"@", "＠", "["}:
                return route

        return None

    @staticmethod
    def _normalize_command_text(message: str) -> str:
        text = message.strip()
        while text and text[0] in {"/", "!", "！"}:
            text = text[1:].lstrip()
        return text

    @staticmethod
    def _matches(text: str, keyword: str, mode: MatchMode) -> bool:
        if mode == MatchMode.EXACT:
            return text == keyword
        if mode == MatchMode.STARTS_WITH:
            return text.startswith(keyword)
        if mode == MatchMode.CONTAINS:
            return keyword in text
        raise ValueError(f"Unknown MatchMode: {mode}")

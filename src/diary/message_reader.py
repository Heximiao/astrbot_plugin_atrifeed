from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from astrbot.api import logger


@dataclass(slots=True)
class DiaryMessage:
    message_id: str
    sender_id: str
    sender_name: str
    timestamp: int
    text: str
    group_id: str
    is_bot: bool = False


class OneBotHistoryReader:
    """通过 AstrBot 已连接的 OneBot 客户端分页读取群历史。"""

    def __init__(self, bot: Any, bot_self_id: str = ""):
        self.bot = bot
        self.bot_self_id = str(bot_self_id or "")
        self._is_snowluma = False

    async def _detect_history_backend(self) -> None:
        try:
            version = await self.bot.call_action("get_version_info")
            app_name = str((version or {}).get("app_name", ""))
            self._is_snowluma = app_name.lower() == "snowluma"
        except Exception:
            self._is_snowluma = False

    async def fetch_group_messages(
        self, group_id: str, start_ts: int, end_ts: int, max_count: int = 1000
    ) -> list[DiaryMessage]:
        if not hasattr(self.bot, "call_action"):
            return []

        await self._detect_history_backend()

        chunk_size = 100
        anchor: str | int | None = None
        raw_messages: list[dict] = []
        seen_ids: set[str] = set()
        page = 0

        logger.info(
            "[日记] 开始拉取群历史: group=%s, range=%s~%s, max=%s",
            group_id,
            datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d %H:%M:%S"),
            datetime.fromtimestamp(end_ts).strftime("%Y-%m-%d %H:%M:%S"),
            max_count,
        )

        while len(raw_messages) < max_count:
            page += 1
            params: dict[str, Any] = {
                "group_id": int(group_id),
                "count": min(chunk_size, max_count - len(raw_messages)),
                "reverseOrder": True,
            }
            if anchor is not None:
                params["message_id" if self._is_snowluma else "message_seq"] = anchor
            if self._is_snowluma:
                params.pop("reverseOrder", None)

            result = None
            for attempt in range(1, 4):
                try:
                    result = await self.bot.call_action("get_group_msg_history", **params)
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if attempt == 3:
                        logger.warning("[日记] 群 %s 历史消息拉取失败: %s", group_id, exc)
                    else:
                        await asyncio.sleep(attempt)

            messages = result.get("messages", []) if isinstance(result, dict) else []
            if not messages:
                logger.info("[日记] 群 %s 第 %s 页为空，结束回溯", group_id, page)
                break

            oldest = min(messages, key=lambda item: int(item.get("time", 0) or 0))
            oldest_time = int(oldest.get("time", 0) or 0)
            for raw in messages:
                message_id = str(raw.get("message_id", "") or "")
                timestamp = int(raw.get("time", 0) or 0)
                if not message_id or message_id in seen_ids:
                    continue
                seen_ids.add(message_id)
                if start_ts <= timestamp <= end_ts:
                    raw_messages.append(raw)

            logger.info(
                "[日记] 群 %s 第 %s 页: 收到=%s, 当日有效累计=%s, 最早时间=%s",
                group_id,
                page,
                len(messages),
                len(raw_messages),
                datetime.fromtimestamp(oldest_time).strftime("%Y-%m-%d %H:%M:%S"),
            )

            if self._is_snowluma:
                new_anchor = oldest.get("message_id")
            else:
                new_anchor = (
                    oldest.get("message_seq")
                    or oldest.get("real_id")
                    or oldest.get("seq")
                    or oldest.get("message_id")
                )
            if oldest_time <= start_ts or new_anchor is None or str(new_anchor) == str(anchor):
                break
            anchor = new_anchor
            await asyncio.sleep(0.05)

        converted = [
            item
            for item in (self._convert_message(raw, str(group_id)) for raw in raw_messages)
            if item is not None
        ]
        converted.sort(key=lambda item: item.timestamp)
        logger.info(
            "[日记] 群 %s 历史拉取完成: 页数=%s, 原始有效=%s, 文本消息=%s",
            group_id,
            page,
            len(raw_messages),
            len(converted),
        )
        return converted

    def _convert_message(self, raw: dict, group_id: str) -> DiaryMessage | None:
        sender = raw.get("sender", {}) or {}
        sender_id = str(sender.get("user_id", raw.get("user_id", "")) or "")
        sender_name = str(sender.get("card") or sender.get("nickname") or sender_id or "某人")
        text = self._message_to_text(raw.get("message", raw.get("raw_message", "")))
        if not text.strip():
            return None
        return DiaryMessage(
            message_id=str(raw.get("message_id", "")),
            sender_id=sender_id,
            sender_name=sender_name,
            timestamp=int(raw.get("time", 0) or 0),
            text=text.strip(),
            group_id=group_id,
            is_bot=bool(self.bot_self_id and sender_id == self.bot_self_id),
        )

    @staticmethod
    def _message_to_text(message: Any) -> str:
        if isinstance(message, str):
            return message
        if not isinstance(message, list):
            return str(message or "")
        parts: list[str] = []
        placeholders = {
            "image": "[图片]",
            "record": "[语音]",
            "video": "[视频]",
            "face": "[表情]",
            "mface": "[表情]",
            "forward": "[转发消息]",
        }
        for segment in message:
            if not isinstance(segment, dict):
                continue
            seg_type = str(segment.get("type", ""))
            data = segment.get("data", {}) or {}
            if seg_type == "text":
                parts.append(str(data.get("text", "")))
            elif seg_type == "at":
                parts.append(f"@{data.get('name') or data.get('qq') or '某人'}")
            elif seg_type in placeholders:
                parts.append(placeholders[seg_type])
        return "".join(parts)

from __future__ import annotations

import asyncio
import random
import re
import time
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from astrbot.api import logger

from .message_reader import DiaryMessage, OneBotHistoryReader
from .prompt_builder import DEFAULT_DIARY_PROMPT, build_timeline, render_prompt
from .qzone import QzonePublisher
from .storage import DiaryStorage


class DiaryService:
    def __init__(self, plugin: Any):
        self.plugin = plugin
        self.context = plugin.context
        self.storage = DiaryStorage(plugin.data_dir)
        self.task: asyncio.Task | None = None
        self.run_lock = asyncio.Lock()
        self.bot: Any = None
        self.platform_id = ""

    def _config(self) -> dict:
        root = self.plugin.config or {}
        value = root.get("diary", {})
        return value if isinstance(value, dict) else {}

    def start_if_enabled(self) -> None:
        if self._config().get("enabled", False) and not self.task:
            self.task = asyncio.create_task(self._schedule_loop())
            logger.info("[日记] 定时服务已启动")

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _discover_onebot(self) -> bool:
        manager = getattr(self.context, "platform_manager", None)
        get_insts = getattr(manager, "get_insts", None)
        if not callable(get_insts):
            return False
        configured_id = str(self._config().get("platform_id", "") or "").strip()
        for platform in list(get_insts() or []):
            metadata = getattr(platform, "metadata", None)
            platform_id = str(
                getattr(metadata, "id", "")
                or (metadata.get("id", "") if isinstance(metadata, Mapping) else "")
            )
            if configured_id and platform_id != configured_id:
                continue
            get_client = getattr(platform, "get_client", None)
            client = get_client() if callable(get_client) else None
            client = client or getattr(platform, "bot", None) or getattr(platform, "client", None)
            if client and hasattr(client, "call_action"):
                self.bot = client
                self.platform_id = platform_id
                return True
        return False

    async def _schedule_loop(self) -> None:
        while True:
            try:
                config = self._config()
                timezone = ZoneInfo(str(config.get("timezone", "Asia/Shanghai")))
                now = datetime.now(timezone)
                hour, minute = map(int, str(config.get("schedule_time", "23:30")).split(":"))
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                await asyncio.sleep(max(1, (target - now).total_seconds()))
                if self._config().get("enabled", False):
                    await self.generate_daily_diary(target.strftime("%Y-%m-%d"))
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[日记] 定时循环异常，60 秒后重试")
                await asyncio.sleep(60)

    async def generate_daily_diary(self, date: str, force: bool = False) -> tuple[bool, str]:
        async with self.run_lock:
            started_at = time.monotonic()
            logger.info("[日记] 开始生成: date=%s, manual_force=%s", date, force)
            if not force and self.storage.was_generated(date):
                logger.info("[日记] %s 已有定时生成记录，跳过重复执行", date)
                return False, "当天日记已经生成，跳过重复执行"
            config = self._config()
            group_ids = self._parse_group_ids(config.get("target_groups", []))
            if not group_ids:
                logger.warning("[日记] 未配置目标QQ群，生成终止")
                return False, "未配置目标 QQ 群"
            if not self.bot and not await self._discover_onebot():
                logger.warning("[日记] 未发现可用OneBot平台，生成终止")
                return False, "未找到可用的 OneBot 平台连接"

            logger.info(
                "[日记] 任务配置: target_groups=%s, publish_qzone=%s, platform_id=%s",
                len(group_ids),
                bool(config.get("publish_qzone", True)),
                self.platform_id or "auto",
            )

            timezone = ZoneInfo(str(config.get("timezone", "Asia/Shanghai")))
            date_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone)
            start_ts = int(date_start.timestamp())
            end_ts = min(int((date_start + timedelta(days=1)).timestamp()), int(time.time()))
            login = await self.bot.call_action("get_login_info")
            bot_self_id = str((login or {}).get("user_id", ""))
            bot_name = str((login or {}).get("nickname", "") or "我")
            reader = OneBotHistoryReader(self.bot, bot_self_id)
            max_per_group = max(1, int(config.get("max_messages_per_group", 1000)))
            minimum_per_group = max(0, int(config.get("min_messages_per_group", 3)))

            messages: list[DiaryMessage] = []
            for group_index, group_id in enumerate(group_ids, 1):
                logger.info(
                    "[日记] 拉取目标群进度: %s/%s, group=%s",
                    group_index,
                    len(group_ids),
                    group_id,
                )
                group_messages = await reader.fetch_group_messages(
                    group_id, start_ts, end_ts, max_per_group
                )
                if len(group_messages) >= minimum_per_group:
                    messages.extend(group_messages)
                    logger.info(
                        "[日记] 群 %s 参与合并: messages=%s",
                        group_id,
                        len(group_messages),
                    )
                else:
                    logger.info(
                        "[日记] 群 %s 消息不足，跳过: %s/%s",
                        group_id,
                        len(group_messages),
                        minimum_per_group,
                    )
            messages.sort(key=lambda item: item.timestamp)
            if not config.get("include_bot_messages", True):
                messages = [message for message in messages if not message.is_bot]
            minimum = max(1, int(config.get("min_message_count", 3)))
            if len(messages) < minimum:
                logger.warning("[日记] 合并后消息不足: %s/%s", len(messages), minimum)
                return False, f"当天有效消息不足（{len(messages)}/{minimum}）"

            logger.info("[日记] 聊天记录合并完成: total_messages=%s", len(messages))

            weather = self._weather(messages, bool(config.get("enable_emotion_analysis", True)))
            date_with_weather = self._date_with_weather(date, weather)
            personality, persona_id = await self._personality(config, group_ids[0])
            timeline = build_timeline(messages, bot_name="我")
            target_length = min(8000, max(20, int(config.get("word_count", 200))))
            prompt = render_prompt(
                str(config.get("prompt_template", "") or DEFAULT_DIARY_PROMPT),
                personality=personality,
                date=date,
                time_desc="到现在为止" if datetime.now(timezone).strftime("%Y-%m-%d") == date else "这一天",
                timeline=timeline,
                target_length=target_length,
                date_with_weather=date_with_weather,
            )
            provider_id = str(config.get("provider_id", "") or "").strip()
            if not provider_id:
                umo = f"{self.platform_id}:GroupMessage:{group_ids[0]}"
                provider_id = await self.context.get_current_chat_provider_id(umo=umo)
            logger.info(
                "[日记] 即将请求大模型: provider=%s, persona=%s, prompt_chars=%s, timeline_chars=%s",
                provider_id or "default",
                persona_id or ("custom_override" if config.get("persona_prompt") else "session_default"),
                len(prompt),
                len(timeline),
            )
            llm_started_at = time.monotonic()
            response = await self.context.llm_generate(
                chat_provider_id=provider_id,
                prompt=prompt,
            )
            content = str(getattr(response, "completion_text", "") or "").strip()
            logger.info(
                "[日记] 大模型返回: elapsed=%.2fs, response_chars=%s, has_content=%s",
                time.monotonic() - llm_started_at,
                len(content),
                bool(content),
            )
            if not content:
                return False, "模型没有返回日记内容"
            content = self._truncate(content, target_length)
            logger.info("[日记] 日记正文处理完成: final_chars=%s", len(content))

            published = False
            publish_error = ""
            tid = ""
            if config.get("publish_qzone", True):
                published, publish_error, tid = await QzonePublisher(self.bot).publish(content)
            record = {
                "date": date,
                "diary_content": content,
                "word_count": len(content),
                "generation_time": time.time(),
                "weather": weather,
                "message_count": len(messages),
                "target_groups": group_ids,
                "persona_id": persona_id,
                "provider_id": provider_id,
                "is_published_qzone": published,
                "qzone_tid": tid,
                "status": "一切正常" if published or not config.get("publish_qzone", True) else "报错:发说说失败",
                "error_message": publish_error,
            }
            self.storage.save(record)
            logger.info(
                "[日记] 任务完成: date=%s, elapsed=%.2fs, published=%s, messages=%s",
                date,
                time.monotonic() - started_at,
                published,
                len(messages),
            )
            if config.get("publish_qzone", True) and not published:
                return True, f"{content}\n\n⚠️ 日记已生成，但QQ空间发布失败：{publish_error}"
            return True, content

    async def publish_saved_diary(self, date: str, index: int = 0) -> tuple[bool, str]:
        record_item = self.storage.get_record(date, index)
        if not record_item:
            return False, "没有找到指定日记"
        path, record = record_item
        content = str(record.get("diary_content", "") or "").strip()
        if not content:
            return False, "该日记没有可发布的正文"
        if not self.bot and not await self._discover_onebot():
            return False, "未找到可用的 OneBot 平台连接"
        success, error, tid = await QzonePublisher(self.bot).publish(content)
        record["is_published_qzone"] = success
        record["qzone_tid"] = tid
        record["qzone_publish_time"] = time.time() if success else None
        record["status"] = "一切正常" if success else "报错:发说说失败"
        record["error_message"] = error
        self.storage.update_record(path, record)
        return (True, f"QQ空间发布成功，tid={tid}") if success else (False, error)

    def status_text(self) -> str:
        config = self._config()
        enabled = bool(config.get("enabled", False))
        groups = self._parse_group_ids(config.get("target_groups", []))
        publish = bool(config.get("publish_qzone", True))
        schedule = str(config.get("schedule_time", "23:30"))
        timezone_name = str(config.get("timezone", "Asia/Shanghai"))
        next_run = "未启用"
        if enabled:
            try:
                timezone = ZoneInfo(timezone_name)
                now = datetime.now(timezone)
                hour, minute = map(int, schedule.split(":"))
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if target <= now:
                    target += timedelta(days=1)
                next_run = target.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                next_run = "时间配置无效"
        return (
            "📖 日记状态\n"
            f"功能开关：{'开启' if enabled else '关闭'}\n"
            f"QQ空间：{'生成后发布' if publish else '仅保存本地'}\n"
            f"目标群：{len(groups)} 个\n"
            f"执行时间：{schedule} ({timezone_name})\n"
            f"下次执行：{next_run}"
        )

    async def debug_history(self, date: str) -> tuple[bool, str]:
        """实际拉取配置群的指定日期消息，仅返回统计，不调用大模型。"""
        config = self._config()
        group_ids = self._parse_group_ids(config.get("target_groups", []))
        if not group_ids:
            return False, "未配置目标 QQ 群"
        if not self.bot and not await self._discover_onebot():
            return False, "未找到可用的 OneBot 平台连接"
        timezone = ZoneInfo(str(config.get("timezone", "Asia/Shanghai")))
        date_start = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone)
        start_ts = int(date_start.timestamp())
        end_ts = min(int((date_start + timedelta(days=1)).timestamp()), int(time.time()))
        login = await self.bot.call_action("get_login_info")
        bot_id = str((login or {}).get("user_id", ""))
        bot_name = str((login or {}).get("nickname", "") or "未知")
        reader = OneBotHistoryReader(self.bot, bot_id)
        max_per_group = max(1, int(config.get("max_messages_per_group", 1000)))
        details: list[str] = []
        total_user = 0
        total_bot = 0
        for index, group_id in enumerate(group_ids, 1):
            logger.info("[日记调试] 拉取群进度: %s/%s, group=%s", index, len(group_ids), group_id)
            messages = await reader.fetch_group_messages(group_id, start_ts, end_ts, max_per_group)
            bot_count = sum(message.is_bot for message in messages)
            user_count = len(messages) - bot_count
            total_bot += bot_count
            total_user += user_count
            details.append(f"- 群 {group_id}: 用户{user_count}条, Bot{bot_count}条")
        text = (
            f"🔍 日记消息读取调试 ({date})\n\n"
            f"🤖 Bot信息：\n- QQ号: {bot_id or '未知'}\n- 昵称: {bot_name}\n\n"
            f"📊 目标群统计：\n- 配置群: {len(group_ids)}个\n"
            f"- 用户消息: {total_user}条\n- Bot消息: {total_bot}条\n\n"
            f"💬 群聊详情：\n" + "\n".join(details)
        )
        return True, text

    async def _personality(self, config: dict, group_id: str) -> tuple[str, str]:
        override = str(config.get("persona_prompt", "") or "").strip()
        persona_id = str(config.get("persona_id", "") or "").strip()
        if override:
            return override, persona_id
        manager = getattr(self.context, "persona_manager", None)
        if manager and persona_id:
            try:
                persona = await manager.get_persona(persona_id)
                prompt = str(getattr(persona, "system_prompt", "") or "").strip()
                if prompt:
                    return prompt, persona_id
            except Exception as exc:
                logger.warning("[日记] 读取人格 %s 失败: %s", persona_id, exc)
        if manager:
            try:
                umo = f"{self.platform_id}:GroupMessage:{group_id}"
                persona = await manager.get_default_persona_v3(umo=umo)
                if isinstance(persona, Mapping):
                    prompt = str(persona.get("prompt") or persona.get("system_prompt") or "").strip()
                else:
                    prompt = str(
                        getattr(persona, "prompt", "")
                        or getattr(persona, "system_prompt", "")
                    ).strip()
                if prompt:
                    return prompt, persona_id
            except Exception as exc:
                logger.warning("[日记] 读取默认人格失败: %s", exc)
        return "一个机器人", persona_id

    @staticmethod
    def _parse_group_ids(value: Any) -> list[str]:
        values = value if isinstance(value, list) else re.split(r"[,，\s]+", str(value or ""))
        result = []
        for item in values:
            group_id = str(item).strip()
            if group_id.startswith("group:"):
                group_id = group_id[6:]
            if group_id.isdigit() and group_id not in result:
                result.append(group_id)
        return result

    @staticmethod
    def _weather(messages: list[DiaryMessage], enabled: bool) -> str:
        if not enabled:
            return "多云"
        content = " ".join(item.text for item in messages)
        happy = sum(word in content for word in ["哈哈", "笑", "开心", "高兴", "棒", "好", "赞", "爱", "喜欢"])
        sad = sum(word in content for word in ["难过", "伤心", "哭", "痛苦", "失望"])
        angry = sum(word in content for word in ["无语", "醉了", "服了", "烦", "气", "怒"])
        if happy >= 3:
            return "晴"
        if happy >= 1:
            return "多云转晴"
        if sad >= 2:
            return "雨"
        if angry >= 2:
            return "阴"
        return random.choice(["多云", "阴", "多云转晴"])

    @staticmethod
    def _date_with_weather(date: str, weather: str) -> str:
        value = datetime.strptime(date, "%Y-%m-%d")
        weekday = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][value.weekday()]
        return f"{value.year}年{value.month}月{value.day}日,{weekday},{weather}。"

    @staticmethod
    def _truncate(text: str, max_length: int) -> str:
        if len(text) <= max_length:
            return text
        for index in range(max_length - 1, max_length // 2, -1):
            if text[index] in "。！？~":
                return text[: index + 1]
        return text[: max_length - 3] + "..."

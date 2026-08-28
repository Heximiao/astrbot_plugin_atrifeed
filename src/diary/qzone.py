from __future__ import annotations

from typing import Any

import httpx
from astrbot.api import logger


class QzonePublisher:
    def __init__(self, bot: Any):
        self.bot = bot

    @staticmethod
    def _gtk(p_skey: str) -> str:
        value = 5381
        for char in p_skey:
            value += (value << 5) + ord(char)
        return str(value & 2147483647)

    async def publish(self, content: str) -> tuple[bool, str, str]:
        """返回 (成功, 错误信息, tid)。"""
        try:
            logger.info("[日记] 开始发布QQ空间: 正文字数=%s", len(content))
            login = await self.bot.call_action("get_login_info")
            uin = str((login or {}).get("user_id", ""))
            cookie_result = await self.bot.call_action(
                "get_cookies", domain="user.qzone.qq.com"
            )
            cookie_text = str((cookie_result or {}).get("cookies", ""))
            cookies = {}
            for pair in cookie_text.split(";"):
                if "=" in pair:
                    key, value = pair.strip().split("=", 1)
                    cookies[key] = value
            p_skey = cookies.get("p_skey", "")
            if not uin or not p_skey:
                logger.warning("[日记] QQ空间Cookie无效: uin=%s, has_p_skey=%s", bool(uin), bool(p_skey))
                return False, "未能从当前 OneBot 连接获取有效 QQ 空间 Cookie", ""

            url = "https://user.qzone.qq.com/proxy/domain/taotao.qzone.qq.com/cgi-bin/emotion_cgi_publish_v6"
            data = {
                "syn_tweet_verson": "1",
                "paramstr": "1",
                "who": "1",
                "con": content,
                "feedversion": "1",
                "ver": "1",
                "ugc_right": "1",
                "to_sign": "0",
                "hostuin": uin,
                "code_version": "1",
                "format": "json",
                "qzreferrer": f"https://user.qzone.qq.com/{uin}",
            }
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    url,
                    params={"g_tk": self._gtk(p_skey), "uin": uin},
                    data=data,
                    cookies=cookies,
                    headers={
                        "referer": f"https://user.qzone.qq.com/{uin}",
                        "origin": "https://user.qzone.qq.com",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    },
                )
            if response.status_code != 200:
                logger.warning("[日记] QQ空间发布接口返回 HTTP %s", response.status_code)
                return False, f"QQ 空间接口返回 HTTP {response.status_code}", ""
            result = response.json()
            tid = str(result.get("tid", "")) if isinstance(result, dict) else ""
            if tid:
                logger.info("[日记] QQ空间发布成功: tid=%s", tid)
                return True, "", tid
            logger.warning("[日记] QQ空间接口未返回tid: %s", result)
            return False, f"QQ 空间发布失败: {result}", ""
        except Exception as exc:
            logger.exception("[日记] QQ 空间发布异常")
            return False, str(exc), ""

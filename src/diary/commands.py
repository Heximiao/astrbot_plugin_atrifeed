from __future__ import annotations

from datetime import datetime, timedelta
from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
import astrbot.api.message_components as Comp

from ..utils.utils import can_use_diary_command


async def check_diary_permission(plugin, event: AstrMessageEvent) -> bool:
    conf = plugin.config if plugin.config else (plugin.context.get_config() or {})
    return await can_use_diary_command(event, conf)

def normalize_diary_date(value: str = "") -> str:
    if not value:
        return datetime.now().strftime("%Y-%m-%d")
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    raise ValueError("日期格式错误")

async def run_diary_generate(plugin, event: AstrMessageEvent, date: str = ""):
    """手动生成一篇全局日记。"""
    event.stop_event()
    if not await check_diary_permission(plugin, event):
        yield event.plain_result("❌ 您没有权限使用日记管理指令。")
        return
    try:
        target_date = normalize_diary_date(date)
    except ValueError:
        yield event.plain_result("❌ 日期格式错误，请使用 YYYY-MM-DD。")
        return
    logger.info(
        "[日记] 收到手动生成指令: date=%s, sender=%s, group=%s",
        target_date,
        event.get_sender_id(),
        event.get_group_id() or "private",
    )
    # 进度消息必须直接发送，不能先 yield。某些结果装饰插件会在处理
    # 第一条 yield 结果后停止事件传播，导致后面的日记生成逻辑不再执行。
    await event.send(event.plain_result(f"🔄 正在生成 {target_date} 的日记，请稍候……"))
    logger.info("[日记] 手动生成进度消息已发送，开始执行核心生成流程")
    success, message = await plugin.diary_service.generate_daily_diary(target_date, force=True)
    prefix = "✅" if success else "❌"
    if success and plugin.diary_service.last_rendered_image_url:
        rendered_image = plugin.diary_service.last_rendered_image_url
        image_component = (
            Comp.Image.fromURL(rendered_image)
            if rendered_image.startswith(("http://", "https://"))
            else Comp.Image.fromFileSystem(rendered_image)
        )
        components = [image_component]
        if "⚠️" in message:
            warning = "⚠️" + message.split("⚠️", 1)[1]
            components.append(Comp.Plain(f"\n{warning}"))
        yield event.chain_result(components)
        return
    yield event.plain_result(f"{prefix} {message}")

async def run_diary_list(plugin, event: AstrMessageEvent, param: str = ""):
    """显示基础概览、指定日期概况或全部详细统计。"""
    event.stop_event()
    if not await check_diary_permission(plugin, event):
        yield event.plain_result("❌ 您没有权限使用日记管理指令。")
        return
    all_records = plugin.diary_service.storage.list_all()
    if not all_records:
        yield event.plain_result("📭 还没有任何日记记录。")
        return

    if param.strip().lower() == "all":
        diaries = [record for _, record in all_records]
        total_words = sum(int(item.get("word_count", 0) or 0) for item in diaries)
        published = sum(bool(item.get("is_published_qzone", False)) for item in diaries)
        dates = sorted(str(item.get("date", "")) for item in diaries if item.get("date"))
        longest = max(diaries, key=lambda item: int(item.get("word_count", 0) or 0))
        shortest = min(diaries, key=lambda item: int(item.get("word_count", 0) or 0))
        latest = datetime.fromtimestamp(float(diaries[0].get("generation_time", 0)))
        week_start = datetime.now().date() - timedelta(days=datetime.now().weekday())
        weekly = [
            item for item in diaries
            if datetime.fromtimestamp(float(item.get("generation_time", 0))).date() >= week_start
        ]
        weekly_words = sum(int(item.get("word_count", 0) or 0) for item in weekly)
        weekly_published = sum(bool(item.get("is_published_qzone", False)) for item in weekly)
        text = (
            "📚 日记概览\n\n📊 详细统计：\n"
            f"📖 总日记数: {len(diaries)}篇\n"
            f"📝 总字数: {total_words}字 (平均: {total_words // len(diaries)}字/篇)\n"
            f"📅 日期范围: {dates[0]} ~ {dates[-1]} ({len(set(dates))}天)\n"
            f"📱 发布统计: {published}篇成功, {len(diaries)-published}篇未发布/失败 "
            f"(成功率: {published / len(diaries) * 100:.1f}%)\n"
            f"🕐 最近生成: {latest:%Y-%m-%d %H:%M}\n"
            f"⏰ 下次定时: {plugin.diary_service.status_text().split('下次执行：')[-1]}\n\n"
            "📈 本周统计：\n"
            f"📝 本周平均: {weekly_words // len(weekly) if weekly else 0}字/篇\n"
            f"📱 本周发布: {weekly_published}/{len(weekly)}篇成功\n"
            f"🔥 最长日记: {longest.get('date', '无')} ({longest.get('word_count', 0)}字)\n"
            f"📏 最短日记: {shortest.get('date', '无')} ({shortest.get('word_count', 0)}字)"
        )
        yield event.plain_result(text)
        return

    if param.strip():
        try:
            target_date = normalize_diary_date(param)
        except ValueError:
            yield event.plain_result("❌ 参数应为 all 或 YYYY-MM-DD 日期。")
            return
        records = plugin.diary_service.storage.list_by_date(target_date)
        if not records:
            yield event.plain_result(f"📭 没有找到 {target_date} 的日记。")
            return
        total_words = sum(int(item.get("word_count", 0) or 0) for _, item in records)
        published = sum(bool(item.get("is_published_qzone", False)) for _, item in records)
        lines = [f"📅 {target_date} 日记概况：", ""]
        for index, (_, record) in enumerate(records, 1):
            generated = datetime.fromtimestamp(float(record.get("generation_time", 0)))
            state = "✅已发布" if record.get("is_published_qzone", False) else "❌未发布"
            lines.append(f"{index}. {generated:%H:%M} ({record.get('word_count', 0)}字) {state}")
        first_time = datetime.fromtimestamp(float(records[0][1].get("generation_time", 0)))
        last_time = datetime.fromtimestamp(float(records[-1][1].get("generation_time", 0)))
        lines.extend([
            "", "📊 当天统计：",
            f"📝 总字数: {total_words}字 (平均: {total_words // len(records)}字/篇)",
            f"📱 发布状态: {published}篇成功, {len(records)-published}篇未发布/失败",
            f"🕐 最早生成: {first_time:%H:%M}", f"🕐 最新生成: {last_time:%H:%M}",
            "", f"使用 /日记查看 {target_date} 编号 查看正文。",
        ])
        yield event.plain_result("\n".join(lines))
        return

    total_words = sum(int(item.get("word_count", 0) or 0) for _, item in all_records)
    recent_lines = []
    for _, record in all_records[:10]:
        state = "✅已发布" if record.get("is_published_qzone", False) else "❌未发布"
        recent_lines.append(f"📅 {record.get('date', '无')} ({record.get('word_count', 0)}字) {state}")
    yield event.plain_result(
        "📚 日记概览：\n\n📊 统计信息：\n"
        f"📖 总日记数: {len(all_records)}篇\n📝 总字数: {total_words}字\n"
        f"📏 平均字数: {total_words // len(all_records)}字/篇\n"
        f"📅 最新日记: {all_records[0][1].get('date', '无')}\n\n"
        "📋 最近日记 (10篇)：\n" + "\n".join(recent_lines) +
        "\n\n💡 使用 /日记列表 日期 查看当天概况，或 /日记列表 all 查看详细统计。"
    )

async def run_diary_view(plugin, event: AstrMessageEvent, date: str = "", index: int = 0):
    """查看指定日期的一篇日记；不写编号时查看最新一篇。"""
    event.stop_event()
    try:
        target_date = normalize_diary_date(date)
    except ValueError:
        yield event.plain_result("❌ 日期格式错误，请使用 YYYY-MM-DD。")
        return
    records = plugin.diary_service.storage.list_by_date(target_date)
    if not records:
        yield event.plain_result(f"📭 没有找到 {target_date} 的日记。")
        return
    if index <= 0:
        lines = [f"📅 {target_date} 的日记列表："]
        for number, (_, record) in enumerate(records, 1):
            generated = datetime.fromtimestamp(float(record.get("generation_time", 0)))
            state = "✅已发布" if record.get("is_published_qzone", False) else "❌未发布"
            lines.append(f"{number}. {generated:%H:%M}｜{record.get('word_count', 0)}字｜{state}")
        lines.append(f"\n输入 /日记查看 {target_date} 编号 查看具体内容。")
        yield event.plain_result("\n".join(lines))
        return
    item = plugin.diary_service.storage.get_record(target_date, index)
    if not item:
        yield event.plain_result("❌ 编号无效，请输入正确编号。")
        return
    _, record = item
    published = "已发布QQ空间" if record.get("is_published_qzone", False) else "未发布QQ空间"
    image_url = await plugin.diary_service.render_diary_image(record)
    if image_url:
        yield event.image_result(image_url)
        return
    yield event.plain_result(
        f"📖 {target_date}｜{record.get('word_count', 0)}字｜{published}\n\n"
        f"{record.get('diary_content', '')}"
    )

async def run_diary_publish(plugin, event: AstrMessageEvent, date: str = "", index: int = 0):
    """将一篇已保存日记发布到QQ空间。"""
    event.stop_event()
    if not await check_diary_permission(plugin, event):
        yield event.plain_result("❌ 您没有权限使用日记管理指令。")
        return
    try:
        target_date = normalize_diary_date(date)
    except ValueError:
        yield event.plain_result("❌ 日期格式错误，请使用 YYYY-MM-DD。")
        return
    success, message = await plugin.diary_service.publish_saved_diary(target_date, index)
    yield event.plain_result(f"{'✅' if success else '❌'} {message}")

async def run_diary_status(plugin, event: AstrMessageEvent):
    """查看日记配置与下次执行时间。"""
    event.stop_event()
    if not await check_diary_permission(plugin, event):
        yield event.plain_result("❌ 您没有权限使用日记管理指令。")
        return
    yield event.plain_result(plugin.diary_service.status_text())

async def run_diary_debug(plugin, event: AstrMessageEvent, date: str = ""):
    """实际拉取指定日期群历史并显示消息统计，不调用大模型。"""
    event.stop_event()
    if not await check_diary_permission(plugin, event):
        yield event.plain_result("❌ 您没有权限使用日记管理指令。")
        return
    try:
        target_date = normalize_diary_date(date)
    except ValueError:
        yield event.plain_result("❌ 日期格式错误，请使用 YYYY-MM-DD。")
        return
    await event.send(event.plain_result(f"🔍 正在检查 {target_date} 的群历史读取情况……"))
    success, message = await plugin.diary_service.debug_history(target_date)
    yield event.plain_result(f"{'✅' if success else '❌'} {message}")

async def run_diary_help(plugin, event: AstrMessageEvent):
    """显示日记管理指令帮助。"""
    event.stop_event()
    if not await check_diary_permission(plugin, event):
        yield event.plain_result("❌ 您没有权限使用日记管理指令。")
        return
    yield event.plain_result(
        "📖 日记功能帮助\n\n"
        "/日记生成 [日期] - 生成指定日期日记，默认今天\n"
        "/日记列表 - 基础概览和最近10篇\n"
        "/日记列表 [日期] - 指定日期概况\n"
        "/日记列表 all - 全部详细统计\n"
        "/日记查看 [日期] - 显示当天日记列表\n"
        "/日记查看 [日期] [编号] - 查看具体正文\n"
        "/日记发布 [日期] [编号] - 发布或补发QQ空间\n"
        "/日记状态 - 查看配置和下次执行时间\n"
        "/日记调试 [日期] - 检查群历史读取统计\n"
        "/日记帮助 - 显示本帮助\n\n"
        "日期支持 YYYY-MM-DD、YYYY/M/D 或 YYYY.M.D；未填日期时默认今天。"
        "注：只有日记查看功能所有人都可以使用"
    )


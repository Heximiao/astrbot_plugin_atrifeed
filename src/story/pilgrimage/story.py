import os
import yaml
from astrbot.api import logger
import astrbot.api.message_components as Comp

class StoryManager:
    def __init__(self, curr_dir): 
        self.curr_dir = curr_dir
        self.script_path = os.path.join(curr_dir, "src", "story", "pilgrimage", "script.yaml")
        self.story_data = self._load_script()
    
    def _load_script(self):
        try:
            with open(self.script_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载剧情脚本失败: {e}")
            return {"nodes": {}}

    async def run_logic(self, event, db, action, selection=None):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        
        # 1. 获取进度
        progress = db.get_story_progress(user_id, group_id)
        if not progress:
             return event.plain_result("🔭 你还没有开始巡礼呢，请先发送『/开始巡礼』。")

        curr_id = progress.get('current_node')
        unlocked_str = progress.get('unlocked_nodes') or ""
        unlocked = unlocked_str.split(',') if unlocked_str else []
        
        node = self.story_data['nodes'].get(curr_id)
        if not node:
            return event.plain_result(f"❌ 剧情数据丢失（节点：{curr_id}）")

        target_id = None
        note = ""

        # 2. 处理交互
        if action == "next":
            if "choices" in node:
                return await self._render(event, node, note="⚠️ 还没做出选择呢，请先选择一个分支。")
            target_id = node.get("next")
            if not target_id:
                return event.plain_result("🌅 当前剧情已完结，敬请期待后续更新！")

        elif action == "select":
            if "choices" not in node:
                return event.plain_result("这里不需要选择，请直接发送『继续前进』。")
            
            try:
                # 1. 确保选择数字合法
                idx = int(str(selection).strip()) - 1
                if idx < 0 or idx >= len(node['choices']):
                    raise IndexError
                
                selected_choice = node['choices'][idx]
                
                # 2. 消耗检查
                cost = selected_choice.get('cost', {})
                if 'stamina' in cost:
                    economy_data = db.get_user_economy(user_id, group_id)
                    
                    # --- 双重保险逻辑 ---
                    if isinstance(economy_data, dict):
                        curr_stamina = economy_data.get('stamina', 0)
                    else:
                        # 万一数据库还是返回了元组 (stamina, coin)
                        curr_stamina = economy_data[0] 
                    
                    if curr_stamina < cost['stamina']:
                        return event.plain_result(f"❌ 体力不足！需要 {cost['stamina']}，当前剩余 {curr_stamina}。")
                    
                    db.update_user_economy(user_id, group_id, stamina=-cost['stamina'])

                target_id = selected_choice['next']
                
            except (ValueError, IndexError):
                return event.plain_result(f"❓ 选项无效。请输入 1-{len(node['choices'])} 之间的数字。")
        # 3. 跳转逻辑
        if target_id:
            if target_id not in unlocked: unlocked.append(target_id)
            db.update_story_progress(user_id, group_id, target_id, ",".join(unlocked))
            
            new_node = self.story_data['nodes'].get(target_id)
            if not new_node: return event.plain_result(f"❌ 找不到节点 {target_id}")

            # --- 奖励检查 ---
            reward = new_node.get('reward', {})
            if 'crab_coin' in reward:
                db.update_user_economy(user_id, group_id, crab_coin=reward['crab_coin'])
                note = f"🎁 恭喜！你获得了 {reward['crab_coin']} 枚螃蟹币！\n\n"

            return await self._render(event, new_node, note=note)

    async def _render(self, event, node_data, note=""):
        """构建富媒体消息链：文字在前，图片在后"""
        text = node_data.get('text', '')
        image_url = node_data.get('image_url', '')
        chain = []
        
        # 1. 先构建并添加文字正文（包括 note 和 choices）
        display_text = f"{note}{text}"
        if "choices" in node_data:
            choice_text = "\n".join([f"【{i+1}】{c['text']}" for i, c in enumerate(node_data['choices'])])
            display_text += f"\n\n{choice_text}\n\n(回复：/选择 数字)"
        
        chain.append(Comp.Plain(display_text))
            
        # 2. 后添加插图（图片会显示在文字下方）
        if image_url: 
            chain.append(Comp.Image.fromURL(image_url))
        
        return event.chain_result(chain)

    async def start_story(self, event, db):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        fav, _ = db.get_user_state(user_id, group_id)
        if fav < 200:
            return event.plain_result(f"❤️ 好感度不足({fav}/200)。\n亚托莉：『我想和更亲近的人一起去。』")

        ticket_count = db.get_user_item_quantity(user_id, group_id, "机票")
        if ticket_count <= 0:
            return event.plain_result("🎫 你的背包里没有【机票】哦！")

        db.consume_item(user_id, group_id, "机票")
        db.update_story_progress(user_id, group_id, "part1", "part1")
        return await self._render(event, self.story_data['nodes'].get("part1"), note="✈️ 登机成功！\n\n")
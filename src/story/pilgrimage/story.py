import os
import yaml
from astrbot.api import logger
import astrbot.api.message_components as Comp

class StoryManager:
    def __init__(self, curr_dir):
        self.script_path = os.path.join(curr_dir, "src", "story", "pilgrimage", "script.yaml")
        self.story_data = self._load_script()

    def _load_script(self):
        with open(self.script_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    async def run_logic(self, event, db, action, selection=None):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        
        # 1. 获取进度
        progress = db.get_story_progress(user_id, group_id)
        curr_id = progress['current_node']
        if not curr_id:
            return event.plain_result("🔭 你还没有开始巡礼呢，请发送『/开始巡礼』。")
        
        unlocked = progress['unlocked_nodes'].split(',') if progress['unlocked_nodes'] else []
        
        node = self.story_data['nodes'].get(curr_id)
        if not node:
            return event.plain_result("❌ 剧情数据丢失，请联系管理员。")

        target_id = None
        note = ""

        # 2. 处理逻辑
        if action == "next":
            # 【强制选择逻辑】：如果当前节点有 choices，禁止使用“继续前进”
            if "choices" in node:
                return await self._render(event, node, note="⚠️ 还没做出选择呢，请先选择一个分支。")
            
            target_id = node.get("next")
            if not target_id:
                return event.plain_result("🌅 当前剧情已完结，敬请期待后续更新！")

        elif action == "select":
            if "choices" not in node:
                return event.plain_result("这里不需要选择，请直接发送『继续前进』。")
            
            try:
                idx = int(selection) - 1
                if idx < 0 or idx >= len(node['choices']):
                    raise IndexError
                
                selected_choice = node['choices'][idx]
                
                # --- 消耗检查 ---
                cost = selected_choice.get('cost', {})
                if 'stamina' in cost:
                    # 使用从 AtriShopDB 继承的获取经济方法
                    economy = db.get_user_economy(user_id, group_id)
                    if economy['stamina'] < cost['stamina']:
                        return event.plain_result(f"❌ 体力不足！需要 {cost['stamina']}，当前剩余 {economy['stamina']}。")
                    # 扣除体力
                    db.update_user_economy(user_id, group_id, stamina=-cost['stamina'])

                target_id = selected_choice['next']
            except (ValueError, IndexError):
                return event.plain_result("❓ 选项无效。请输入正确的数字，例如：/选择 1")

        # 3. 执行跳转与奖励
        if target_id:
            # 更新解锁列表
            if target_id not in unlocked:
                unlocked.append(target_id)
            
            # 更新进度到数据库
            db.update_story_progress(user_id, group_id, target_id, ",".join(unlocked))
            
            # 获取新节点数据
            new_node = self.story_data['nodes'].get(target_id)
            if not new_node:
                return event.plain_result(f"❌ 错误：找不到剧情节点 {target_id}")

            # --- 奖励发放 ---
            reward = new_node.get('reward', {})
            if 'crab_coin' in reward:
                db.update_user_economy(user_id, group_id, crab_coin=reward['crab_coin'])
                note = f"🎁 恭喜！你获得了 {reward['crab_coin']} 枚螃蟹币！\n"

            return await self._render(event, new_node, note=note)

    async def _render(self, event, node_data, note=""):
        """构建富媒体消息链"""
        text = node_data.get('text', '')
        image_url = node_data.get('image_url', '')
        
        chain = []
        
        # 1. 优先放图片
        if image_url:
            chain.append(Comp.Image.fromURL(image_url))
            
        # 2. 组合文字内容
        display_text = f"{note}{text}" if note else text
        
        # 3. 如果有选项，把选项拼接到文字末尾
        if "choices" in node_data:
            choice_text = "\n".join([f"【{i+1}】{c['text']}" for i, c in enumerate(node_data['choices'])])
            display_text += f"\n\n{choice_text}\n\n(回复：/选择 数字)"
            
        chain.append(Comp.Plain(display_text))
        
        return event.chain_result(chain)
    
    async def start_story(self, event, db):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        
        # 1. 获取用户好感度 (从 user_state 获取第一个值)
        fav, _ = db.get_user_state(user_id, group_id)
        
        # 2. 检查好感度门槛
        if fav < 200:
            return event.plain_result(f"❤️ 好感度不足（当前：{fav}/200）。\n亚托莉：『这种远距离旅行...我想和更亲近的人一起去。』")

        # 3. 检查机票持有情况
        ticket_count = db.get_user_item_quantity(user_id, group_id, "机票")
        if ticket_count <= 0:
            return event.plain_result("🎫 你的背包里没有【机票】哦！\n请去商店购买机票后再来找我吧~")

        # 4. 消耗机票并开启剧情
        # 使用你数据库中现有的 consume_item 方法
        item_data, status = db.consume_item(user_id, group_id, "机票")
        if not item_data:
            return event.plain_result("❌ 登机失败，请检查你的背包。")

        # 5. 重置或获取初始进度
        # 如果是第一次开始，强制设置回 part1
        db.update_story_progress(user_id, group_id, "part1", "part1")
        
        # 6. 渲染第一章内容
        first_node = self.story_data['nodes'].get("part1")
        return await self._render(event, first_node, note="✈️ 登机成功！目的地：铫子市！一段难忘的巡礼之旅开始了...\n\n")
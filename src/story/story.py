import os
import yaml
from astrbot.api import logger
import astrbot.api.message_components as Comp

class StoryManager:
    def __init__(self, curr_dir): 
        self.curr_dir = curr_dir
        self.stories = {} # 格式: { "story_id": {yaml_content} }
        self._load_all_scripts()
    
    def _load_all_scripts(self):
        """自动扫描 src/story/ 目录下所有 yaml 剧本"""
        base_path = os.path.join(self.curr_dir, "src", "story")
        if not os.path.exists(base_path):
            os.makedirs(base_path)
            return
            
        for root, dirs, files in os.walk(base_path):
            for file in files:
                if file.endswith((".yaml", ".yml")):
                    try:
                        with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                            data = yaml.safe_load(f)
                            if data and "story_id" in data:
                                self.stories[data["story_id"]] = data
                                logger.info(f"✅ 剧本加载成功: {data['story_id']} ({file})")
                    except Exception as e:
                        logger.error(f"❌ 加载脚本 {file} 失败: {e}")

    async def run_logic(self, event, db, action, selection=None, story_id="main_pilgrimage"):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()

        story_data = self.stories.get(story_id)
        if not story_data:
            return event.plain_result(f"❌ 剧本数据 {story_id} 未加载。")

        # 1. 获取数据库进度
        progress = db.get_story_progress(user_id, group_id, story_id)
        if not progress:
             return event.plain_result("🔭 你还没有开始这段剧情呢，请先发送指令开启。")

        curr_id = progress.get('current_node')
        unlocked_str = progress.get('unlocked_nodes') or ""
        unlocked = unlocked_str.split(',') if unlocked_str else []
        
        node = story_data['nodes'].get(curr_id)
        if not node:
            return event.plain_result(f"❌ 找不到当前节点：{curr_id}")

        target_id = None
        note = ""

        # 2. 交互处理
        if action == "next":
            if "choices" in node:
                return await self._render(event, node, note="⚠️ 请先做出选择。", title=node.get('title'))
            target_id = node.get("next")
            if not target_id: return event.plain_result("🎉 本章节已完结！")

        elif action == "select":
            if "choices" not in node:
                return event.plain_result("这里不需要选择，请发送『继续前进』。")
            try:
                idx = int(str(selection).strip()) - 1
                selected_choice = node['choices'][idx]
                
                # 消耗检查
                cost = selected_choice.get('cost', {})
                if 'stamina' in cost:
                    eco = db.get_user_economy(user_id, group_id)
                    curr_stamina = eco.get('stamina', 0) if isinstance(eco, dict) else eco[0]
                    if curr_stamina < cost['stamina']:
                        return event.plain_result(f"❌ 体力不足！需要 {cost['stamina']}，当前剩余 {curr_stamina}。")
                    db.update_user_economy(user_id, group_id, stamina=-cost['stamina'])

                target_id = selected_choice['next']
            except (ValueError, IndexError):
                return event.plain_result("❓ 选项无效，请输入正确的数字。")

        # 3. 节点跳转与存档
        if target_id:
            if target_id not in unlocked: unlocked.append(target_id)
            db.update_story_progress(user_id, group_id, story_id, target_id, ",".join(unlocked))
            
            new_node = story_data['nodes'].get(target_id)
            if not new_node: return event.plain_result(f"❌ 剧情断链：节点 {target_id} 未定义")

            # 奖励逻辑
            reward = new_node.get('reward', {})
            if 'crab_coin' in reward:
                db.update_user_economy(user_id, group_id, crab_coin=reward['crab_coin'])
                note = f"🎁 获得螃蟹币 x{reward['crab_coin']}！\n\n"

            return await self._render(event, new_node, note=note, title=new_node.get('title'))

    async def start_story(self, event, db, story_id="main_pilgrimage"):
        user_id = event.get_sender_id()
        group_id = event.get_group_id()
        
        story_data = self.stories.get(story_id)
        if not story_data:
            return event.plain_result(f"❌ 剧本 {story_id} 未加载。")

        progress = db.get_story_progress(user_id, group_id, story_id)
        
        # 预设解锁列表
        unlocked_nodes_str = ""

        if progress:
            # 【逻辑 A】老玩家：继承已解锁的所有节点
            note = "🔄 已检测到巡礼记录，正在重置到起始点（已解锁进度已保留）...\n\n"
            unlocked_nodes_str = progress.get('unlocked_nodes') or ""
        else:
            # 【逻辑 B】新玩家：鉴权 & 扣票
            fav, _ = db.get_user_state(user_id, group_id)
            if fav < 200:
                return event.plain_result(f"❤️ 好感度不足({fav}/200)。")

            ticket_count = db.get_user_item_quantity(user_id, group_id, "机票")
            if ticket_count <= 0:
                return event.plain_result("🎒 你的背包里还没有机票哦！")
            
            db.consume_item(user_id, group_id, "机票")
            note = "✈️ 验证通过，机票已使用！\n\n"
            # 新玩家的解锁列表初始只有起始节点
            # 注意：这里后面会统一处理起始节点的添加

        # 2. 确定起始节点
        start_node_id = story_data.get('start_node') or list(story_data['nodes'].keys())[0]
        node = story_data['nodes'].get(start_node_id)
        
        # 3. 维护 unlocked_nodes 列表
        # 将 start_node_id 加入解锁列表（如果原先字符串里没有的话）
        unlocked_list = unlocked_nodes_str.split(',') if unlocked_nodes_str else []
        if start_node_id not in unlocked_list:
            unlocked_list.append(start_node_id)
        
        final_unlocked_str = ",".join(unlocked_list)

        # 4. 更新数据库：重置当前位置到起点，但保留/更新解锁列表
        db.update_story_progress(user_id, group_id, story_id, start_node_id, final_unlocked_str)

        return await self._render(event, node, note=note, title=node.get('title'))

    async def _render(self, event, node_data, note="", title=""):
        """支持多图渲染的逻辑"""
        text = node_data.get('text', '')
        # 兼容处理：优先找 images 列表，找不到则看有没有旧的 image_url
        images = node_data.get('images', []) 
        if not images and node_data.get('image_url'):
            images = [node_data.get('image_url')]

        title_header = f"【{title}】\n" if title else ""
        display_text = f"{note}{title_header}{text}"
        
        if "choices" in node_data:
            choice_text = "\n".join([f"({i+1}) {c['text']}" for i, c in enumerate(node_data['choices'])])
            display_text += f"\n\n{choice_text}\n\n(回复：/选择 数字)"
        
        # 构建消息链
        chain = [Comp.Plain(display_text)]
        
        # 遍历图片列表，全部加入消息链
        for url in images:
            if url:
                chain.append(Comp.Image.fromURL(url))
                
        return event.chain_result(chain)
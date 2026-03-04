import os
import random
from astrbot.api.event import AstrMessageEvent
import astrbot.api.message_components as Comp

async def yield_random_pic(event: AstrMessageEvent, curr_dir: str):
    pic_dir = os.path.join(curr_dir, "pic/emoji")
    if os.path.exists(pic_dir):
        valid_pics = [
            f for f in os.listdir(pic_dir) 
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))
        ]
        if valid_pics:
            pick = random.choice(valid_pics)
            yield event.image_result(os.path.join(pic_dir, pick))

async def send_combined_msg(event: AstrMessageEvent, text: str, pic_path: str = None):
    """
    将文字和图片组合成一条消息链发送
    :param event: AstrMessageEvent 实例
    :param text: 要发送的文字
    :param pic_path: 本地图片路径 (可选)
    """
    chain = [Comp.Plain(text)]
    if pic_path and os.path.exists(pic_path):
        chain.append(Comp.Image.fromFileSystem(pic_path))
    
    yield event.chain_result(chain)

async def get_pic_path(curr_dir: str, folder_types: list = ["emoji"]):
    """
    只获取路径，不发送。
    folder_types: ['rocket', 'emoji', 'bad', 'scare', 'angry']
    """
    path_map = {
        "rocket": os.path.join(curr_dir, "pic", "emoji", "rocket"),
        "emoji": os.path.join(curr_dir, "pic", "emoji"),
        "bad": os.path.join(curr_dir, "pic", "emoji", "bad"), 
        "scare": os.path.join(curr_dir, "pic", "emoji", "scare"),
        "angry": os.path.join(curr_dir, "pic", "emoji", "angry")
    }
    all_valid_pics = []
    for folder_type in folder_types:
        target_dir = path_map.get(folder_type)
        if target_dir and os.path.exists(target_dir):
            for f in os.listdir(target_dir):
                full_path = os.path.join(target_dir, f)
                if os.path.isfile(full_path) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    all_valid_pics.append(full_path)
    return random.choice(all_valid_pics) if all_valid_pics else None

async def yield_random_folder_pic(event: AstrMessageEvent, curr_dir: str, folder_types: list):
    """
    folder_types: 指定要抽取的类型，例如 ['pic', 'emoji', 'bad']
    """
    all_valid_pics = []
    
    # 根据你的描述映射实际路径
    path_map = {
        "rocket": os.path.join(curr_dir, "pic", "emoji", "rocket"),
        "emoji": os.path.join(curr_dir, "pic", "emoji"),
        "bad": os.path.join(curr_dir, "pic", "emoji", "bad"), 
        "scare": os.path.join(curr_dir, "pic", "emoji", "scare"),
        "angry": os.path.join(curr_dir, "pic", "emoji", "angry")
    }
    
    for folder_type in folder_types:
        target_dir = path_map.get(folder_type)
        
        if target_dir and os.path.exists(target_dir):
            # 仅读取当前文件夹下的文件，不递归读取子文件夹（避免重复）
            for f in os.listdir(target_dir):
                full_path = os.path.join(target_dir, f)
                if os.path.isfile(full_path) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    all_valid_pics.append(full_path)
    
    if all_valid_pics:
        pick = random.choice(all_valid_pics)
        yield event.image_result(pick)

async def run_feed_crab_logic(event: AstrMessageEvent, db, curr_dir: str):
    uid, gid = event.get_sender_id(), event.get_group_id()
    
    if db.check_today_fed(uid, gid, "🦀"):
        if random.random() < 0.3:
            text = "呜哇......是美食，高性能......高性能其实还能再吃一顿的......嘿嘿嘿...(流口水)"
        else:
            text = "谢谢你，不过亚托莉今天吃饱啦！"
        
        pic = await get_pic_path(curr_dir, ["emoji"])
        async for res in send_combined_msg(event, text, pic):
            yield res
        return

    db.record_feeding(uid, gid, "🦀")
    fav_gain = 3 if db.check_continuous_crab(uid, gid) else 2
    bonus_msg = "\n触发了连续投喂奖励！好感度已经额外+1了！" if fav_gain == 3 else ""
    db.update_favorability(uid, gid, fav_gain)
    
    text = f"是螃蟹！螃蟹很美味，美味就是高兴！好感度+{fav_gain}{bonus_msg}"
    pic = await get_pic_path(curr_dir, ["emoji"])
    
    async for res in send_combined_msg(event, text, pic):
        yield res

async def run_feed_fruit_logic(event: AstrMessageEvent, db, curr_dir: str):
    uid, gid = event.get_sender_id(), event.get_group_id()
    msg = event.message_str
    
    # 识别 emoji 类型
    feed_type = None
    for emoji in ["🍓", "🍉", "🍎", "🍜", "🍧", "🍔", "🍕", "🍱", "🍄", "🍭", "🍙"]:
        if emoji in msg:
            feed_type = emoji
            break
    
    if not feed_type: return

    if db.check_today_fed(uid, gid, feed_type):
        if random.random() < 0.3: # 20% 概率
            #yield event.plain_result("呜哇......是美食，高性能......高性能确实还能再吃一顿的......")
            text = "呜哇......是美食，高性能......高性能其实还能再吃一顿的......嘿嘿嘿...(流口水)"
            pic = await get_pic_path(curr_dir, ["emoji"])
            async for res in send_combined_msg(event, text, pic):
                yield res
            return
        #yield event.plain_result("谢谢你，不过亚托莉今天吃饱啦！")
        text = "谢谢你，不过亚托莉今天吃饱啦！"
        pic = await get_pic_path(curr_dir, ["emoji"])
        async for res in send_combined_msg(event, text, pic):
            yield res
        return

    db.record_feeding(uid, gid, feed_type)
    db.update_favorability(uid, gid, 1)
    
    if feed_type in ["🍄"]:
        # 设定 30% 的概率中毒
        if random.random() < 0.2: 
            # 中毒了：把刚才加的 1 分扣掉，再额外扣 1 分，总计好感表现为 -1
            db.update_favorability(uid, gid, -2) 
            #yield event.plain_result("哇！是漂亮的蘑菇...诶？呜哇...头好晕...这蘑菇有毒！亚托莉要宕机了... (好感度-1)")
            text = "哇！是漂亮的蘑菇...诶？呜哇...头好晕...这蘑菇有毒！亚托莉要宕机了... (好感度-1)"
            pic = await get_pic_path(curr_dir, ["bad"])
            #async for res in yield_random_folder_pic(event, curr_dir, ["bad"]):
            async for res in send_combined_msg(event, text, pic):
                yield res
            return # 直接结束，不再走后面的正常逻辑
    if feed_type in ["🍜"]:
        #yield event.plain_result("呜哇！是热腾腾的拉面！（抢来吃掉）亚托莉动力满点！好感度+1")
        text = "呜哇！是热腾腾的拉面！（抢来吃掉）亚托莉动力满点！好感度+1"
    elif feed_type in ["🍓"]:
        #yield event.plain_result("哇，是草莓！（抢来吃掉），好感度+1")
        text = "哇，是草莓！（抢来吃掉），好感度+1"
    elif feed_type in ["🍉"]:
        #yield event.plain_result("哇，是可口的西瓜！（抢来吃掉），好感度+1")
        text = "哇，是可口的西瓜！（抢来吃掉），好感度+1"
    elif feed_type in ["🍎"]:
        #yield event.plain_result("哇唔，是苹果！看起来很好吃耶！好感度+1")
        text = "哇唔，是苹果！看起来很好吃耶！好感度+1"
    elif feed_type in ["🍧"]:
        #yield event.plain_result("哇唔，是冰凉凉的冰淇淋！看起来很好吃耶！（抢来吃掉）好感度+1")
        text = "哇唔，是冰凉凉的冰淇淋！看起来很好吃耶！（抢来吃掉）好感度+1"
    elif feed_type in ["🍱"]:
        #yield event.plain_result("哇!精致的便当！嘿嘿嘿~亚托莉会好好品尝的~ 好感度+1")
        text = "哇!精致的便当！嘿嘿嘿~亚托莉会好好品尝的~ 好感度+1"
    elif feed_type in ["🍔"]:
        #yield event.plain_result("哇！是汉堡包！咬一口满嘴都是肉汁！好感度+1")
        text = "哇！是汉堡包！咬一口满嘴都是肉汁！好感度+1"
    elif feed_type in ["🍙"]:
        #yield event.plain_result("唔~是饭团！看着好好吃！不过我才不想工作~！好感度+1")
        text = "唔~是饭团！看着好好吃！不过我才不想工作~！好感度+1"
    else:
        #yield event.plain_result("哇，看起来很好吃耶！（抢来吃掉）好感度+1")
        text = "哇，看起来很好吃耶！（抢来吃掉）好感度+1"
    pic = await get_pic_path(curr_dir, ["emoji"])
    async for res in send_combined_msg(event, text, pic):
        yield res
    return

async def run_star_effect_logic(event: AstrMessageEvent):
    yield event.plain_result("哇，亮闪闪的，好漂亮。")

async def run_no_smoke_logic(event: AstrMessageEvent, curr_dir: str):
    yield event.plain_result("不许抽烟！抽烟是坏习惯！")
    yield event.plain_result("看我的！火——箭——拳——！")
    async for res in yield_random_folder_pic(event, curr_dir, ["rocket"]):
        yield res

async def run_poop_effect_logic(event: AstrMessageEvent, db, curr_dir: str):
    uid, gid = event.get_sender_id(), event.get_group_id()
    
    # 1. 记录并获取这是累计第几次
    count = db.record_poop_and_get_count(uid, gid)
    # 2. 无限增长算法逻辑
    if count <= 3:
        penalty = 1
    else:
        # 这里的 m 对应你观察到的差值阶梯 (4-5次为m=2, 6-7次为m=3...)
        m = count // 2
        # 使用求和公式实现阶梯增长: (m*(m+1))/2
        penalty = (m * (m + 1)) // 2
        
    # 3. 执行扣分 (传入负值)
    db.update_favorability(uid, gid, -penalty)
    yield event.plain_result(f"呜...亚托莉真的生气了！这是第 {count} 次...好感度大减 {penalty}！")
    
    async for res in yield_random_folder_pic(event, curr_dir, ["bad"]):
        yield res
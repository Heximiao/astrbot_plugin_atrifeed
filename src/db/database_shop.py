import sqlite3
import time
from astrbot.api import logger
from .database import AtriDB

class AtriShopDB(AtriDB):
    def __init__(self, db_path):
        # 调用父类初始化，确保基础表和路径都已准备好
        super().__init__(db_path)
        self._init_shop_tables()
        self._seed_initial_items()

    def _init_shop_tables(self):
        """初始化商店相关表"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            
            # 1. 商店商品表
            cursor.execute('''CREATE TABLE IF NOT EXISTS shop_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_name TEXT NOT NULL UNIQUE,
                item_icon TEXT,
                item_type TEXT,
                price INTEGER NOT NULL,
                effect_value INTEGER DEFAULT 0,
                description TEXT,
                is_active INTEGER DEFAULT 1
            )''')

            # 2. 用户背包表
            cursor.execute('''CREATE TABLE IF NOT EXISTS user_inventory (
                user_id TEXT,
                group_id TEXT,
                item_name TEXT,
                quantity INTEGER DEFAULT 1,
                PRIMARY KEY (user_id, group_id, item_name)
            )''')

            # 3. 购买日志表
            cursor.execute('''CREATE TABLE IF NOT EXISTS shop_purchase_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                group_id TEXT,
                item_name TEXT,
                price INTEGER,
                quantity INTEGER,
                timestamp INTEGER
            )''')
            conn.commit()

    def _seed_initial_items(self):
        """初始化预设商品数据"""
        # 格式: (名称, 图标, 类型, 价格, 效果值, 描述)
        initial_items = [
            ("蛋包饭", "🍳", "food", 50, 13, "热腾腾的蛋包饭，可以增加体力值"),
            ("机票", "✈️", "tool", 600, 0, "或许可以去更远的地方进行圣地巡礼？（开启剧情的关键道具）"),
            ("新鞋子", "👟", "apparel", 150, 13, "换上新鞋子，增加好感度"),
            ("新衣服", "👗", "apparel", 200, 15, "给亚托莉买的新衣服,增加好感度"),
            ("菠萝", "🍍", "food", 30, 5, "新鲜的菠萝，可以增加体力值。"),
            ("烟花", "🎆", "tool", 200, 25, "在夜晚绽放的美丽，能大幅提升好感。"),
            ("奶茶", "🧋", "food", 25, 4, "现代人的续命水，增加体力值")
        ]
        
        with self._get_conn() as conn:
            cursor = conn.cursor()
            for item in initial_items:
                # 使用 ON CONFLICT 进行更新 (UPSERT)
                cursor.execute('''
                    INSERT INTO shop_items 
                    (item_name, item_icon, item_type, price, effect_value, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(item_name) DO UPDATE SET
                        item_icon = excluded.item_icon,
                        item_type = excluded.item_type,
                        price = excluded.price,
                        effect_value = excluded.effect_value,
                        description = excluded.description
                ''', item)
            conn.commit()

    def get_all_items(self):
        """获取所有在售商品"""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM shop_items WHERE is_active = 1")
            return [dict(row) for row in cur.fetchall()]

    def get_user_inventory(self, user_id, group_id):
        """获取用户背包"""
        group_id = self._format_gid(group_id)
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT i.item_name, s.item_icon, i.quantity, s.description 
                FROM user_inventory i
                JOIN shop_items s ON i.item_name = s.item_name
                WHERE i.user_id = ? AND i.group_id = ? AND i.quantity > 0
            ''', (user_id, group_id))
            return cur.fetchall()
    
    def get_item_by_name(self, item_name):
        """获取单个商品详情"""
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM shop_items WHERE item_name = ?", (item_name,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_user_item_quantity(self, user_id, group_id, item_name):
        """获取用户背包中某个物品的数量"""
        group_id = self._format_gid(group_id)
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT quantity FROM user_inventory WHERE user_id = ? AND group_id = ? AND item_name = ?", 
                        (user_id, group_id, item_name))
            row = cur.fetchone()
            return row[0] if row else 0

    def buy_item(self, user_id, group_id, item_name, quantity=1, max_limit=20):
        """购买商品逻辑 (合并版：含上限检查+日志记录)"""
        group_id = self._format_gid(group_id)
        now = int(time.time())
        
        # 1. 检查商品是否存在
        item = self.get_item_by_name(item_name)
        if not item or not item['is_active']:
            return False, f"商店里好像没有 {item_name} 呢..."
        
        # 2. 检查背包上限
        current_qty = self.get_user_item_quantity(user_id, group_id, item_name)
        if current_qty + quantity > max_limit:
            return False, f"哎呀，背包里的 {item_name} 太多了（上限 {max_limit} 个），先用掉一些吧！"

        # 3. 检查余额 & 执行交易
        total_cost = item['price'] * quantity
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT crab_coin FROM user_economy WHERE user_id = ? AND group_id = ?", (user_id, group_id))
            econ_row = cur.fetchone()
            
            if not econ_row or econ_row[0] < total_cost:
                return False, f"你的螃蟹币不够呢... 需要 {total_cost} 枚，你只有 {econ_row[0] if econ_row else 0} 枚。"

            try:
                # 扣钱
                cur.execute("UPDATE user_economy SET crab_coin = crab_coin - ? WHERE user_id = ? AND group_id = ?", 
                            (total_cost, user_id, group_id))
                
                # 进背包
                cur.execute('''
                    INSERT INTO user_inventory (user_id, group_id, item_name, quantity)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id, group_id, item_name) 
                    DO UPDATE SET quantity = quantity + excluded.quantity
                ''', (user_id, group_id, item_name, quantity))

                # === 关键：补回被你弄丢的写日志逻辑 ===
                cur.execute('''
                    INSERT INTO shop_purchase_log (user_id, group_id, item_name, price, quantity, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (user_id, group_id, item_name, item['price'], quantity, now))
                # ====================================

                conn.commit()
                return True, f"成功购买了 {quantity} 个 {item_name}！花费了 {total_cost} 螃蟹币。"
            except Exception as e:
                conn.rollback()
                logger.error(f"购买失败: {e}")
                return False, "交易发生了一点小故障..."
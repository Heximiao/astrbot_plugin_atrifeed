import sqlite3
import time
from .database_shop import AtriShopDB

class AtriStoryDB(AtriShopDB):
    def __init__(self, db_path):
        super().__init__(db_path)
        self._init_story_tables()

    def _init_story_tables(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS user_story_progress (
                user_id TEXT,
                group_id TEXT,
                current_node TEXT,
                unlocked_nodes TEXT DEFAULT 'part1',
                last_update INTEGER,
                PRIMARY KEY (user_id, group_id)
            )''')
            conn.commit()

    def get_story_progress(self, user_id, group_id):
        group_id = self._format_gid(group_id)
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM user_story_progress WHERE user_id = ? AND group_id = ?", 
                        (user_id, group_id))
            row = cur.fetchone()
            return dict(row) if row else None

    def update_story_progress(self, user_id, group_id, node_id, unlocked_str):
        group_id = self._format_gid(group_id)
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute('''REPLACE INTO user_story_progress 
                           (user_id, group_id, current_node, unlocked_nodes, last_update)
                           VALUES (?, ?, ?, ?, ?)''', 
                        (user_id, group_id, node_id, unlocked_str, int(time.time())))
            conn.commit()

    def update_user_economy(self, user_id, group_id, stamina=0, crab_coin=0):
        """通用更新用户数值的方法"""
        group_id = self._format_gid(group_id)
        with self._get_conn() as conn:
            cur = conn.cursor()
            # 检查用户是否存在，不存在则初始化
            cur.execute("SELECT 1 FROM user_economy WHERE user_id = ? AND group_id = ?", (user_id, group_id))
            if not cur.fetchone():
                cur.execute("INSERT INTO user_economy (user_id, group_id, stamina, crab_coin) VALUES (?, ?, 100, 0)", 
                            (user_id, group_id))
            
            # 使用自增/自减方式更新
            cur.execute('''UPDATE user_economy 
                           SET stamina = stamina + ?, 
                               crab_coin = crab_coin + ? 
                           WHERE user_id = ? AND group_id = ?''', 
                        (stamina, crab_coin, user_id, group_id))
            conn.commit()
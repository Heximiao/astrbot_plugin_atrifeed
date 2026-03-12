# src/db/database_story.py
import sqlite3
import time
from .database_shop import AtriShopDB

class AtriStoryDB(AtriShopDB):
    def __init__(self, db_path):
        # 初始化父类（Shop 和 Base DB）
        super().__init__(db_path)
        self._init_story_tables()

    def _init_story_tables(self):
        """初始化剧情进度表"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS user_story_progress (
                user_id TEXT,
                group_id TEXT,
                current_node TEXT DEFAULT 'part1',
                unlocked_nodes TEXT DEFAULT 'part1',
                last_update INTEGER,
                PRIMARY KEY (user_id, group_id)
            )''')
            conn.commit()

    def get_story_progress(self, user_id, group_id):
        """获取或初始化用户剧情进度"""
        group_id = self._format_gid(group_id)
        with self._get_conn() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM user_story_progress WHERE user_id = ? AND group_id = ?", 
                       (user_id, group_id))
            row = cur.fetchone()
            if not row:
                now = int(time.time())
                cur.execute('''INSERT INTO user_story_progress 
                             (user_id, group_id, current_node, unlocked_nodes, last_update) 
                             VALUES (?, ?, ?, ?, ?)''',
                            (user_id, group_id, 'part1', 'part1', now))
                conn.commit()
                return {"current_node": "part1", "unlocked_nodes": "part1"}
            return dict(row)

    def update_story_progress(self, user_id, group_id, node_id, unlocked_str):
        """更新进度"""
        group_id = self._format_gid(group_id)
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute('''UPDATE user_story_progress 
                           SET current_node = ?, unlocked_nodes = ?, last_update = ?
                           WHERE user_id = ? AND group_id = ?''', 
                        (node_id, unlocked_str, int(time.time()), user_id, group_id))
            conn.commit()
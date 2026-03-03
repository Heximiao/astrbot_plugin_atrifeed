import sqlite3
import os
import time
from datetime import datetime
from astrbot.api import logger

class AtriDB:
    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()
        self._upgrade_db()
        self.cleanup_old_logs()

    def _upgrade_db(self):
        """用于在不删除数据库的情况下，动态增加新列"""
        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                # 尝试给 feed_stats 增加 poop_count 列
                cursor.execute("ALTER TABLE feed_stats ADD COLUMN poop_count INTEGER DEFAULT 0")
                conn.commit()
                logger.info("[Atri] 数据库升级成功：已为 feed_stats 表增加 poop_count 列。")
            except sqlite3.OperationalError:
                # 如果列已经存在，SQLite 会报错，我们直接忽略即可
                pass
            try:
                cursor.execute("ALTER TABLE user_state ADD COLUMN forgiven_count INTEGER DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                pass
            for food in ["hamburger", "pizza", "bento", "mushroom", "lollipop"]:
                try:
                    cursor.execute(f"ALTER TABLE feed_stats ADD COLUMN {food}_count INTEGER DEFAULT 0")
                    conn.commit()
                except sqlite3.OperationalError:
                    pass
            try:
                cursor.execute("ALTER TABLE feed_stats ADD COLUMN riceball_count INTEGER DEFAULT 0")
                conn.commit()
            except sqlite3.OperationalError:
                pass

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            # 1. 核心状态表
            cursor.execute('''CREATE TABLE IF NOT EXISTS user_state (
                user_id TEXT, group_id TEXT,
                favorability INTEGER DEFAULT 10,
                is_blocked INTEGER DEFAULT 0,
                forgiven_count INTEGER DEFAULT 0,
                first_seen_time INTEGER,
                PRIMARY KEY (user_id, group_id))''')
            
            # 2. 投喂记录表 (30天行为记录)
            cursor.execute('''CREATE TABLE IF NOT EXISTS feed_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT, group_id TEXT,
                feed_type TEXT, timestamp INTEGER, feed_date TEXT)''')

            # 3. 累计统计表 (各食物次数)
            cursor.execute('''CREATE TABLE IF NOT EXISTS feed_stats (
                user_id TEXT, group_id TEXT,
                total_count INTEGER DEFAULT 0,
                strawberry_count INTEGER DEFAULT 0, watermelon_count INTEGER DEFAULT 0,
                apple_count INTEGER DEFAULT 0, noodle_count INTEGER DEFAULT 0,
                shavedice_count INTEGER DEFAULT 0, crab_count INTEGER DEFAULT 0,
                poop_count INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, group_id))''')
            conn.commit()

    def _format_gid(self, group_id):
        """内部方法：统一私聊和群聊的 ID 格式"""
        return str(group_id) if group_id else "PRIVATE"
    
    def get_user_state(self, user_id, group_id):
            group_id = self._format_gid(group_id)
            with self._get_conn() as conn:
                cur = conn.cursor()
                cur.execute("SELECT favorability, is_blocked FROM user_state WHERE user_id=? AND group_id=?", (user_id, group_id))
                row = cur.fetchone()
                if not row:
                    # 关键：这里不再执行 INSERT，直接返回默认好感度 10 和未拉黑状态 0
                    return 10, 0
                return row
            
    def cleanup_old_logs(self, days=30):
        """删除指定天数之前的投喂记录"""
        # 计算 30 天前的时间戳 (秒)
        limit_timestamp = int(time.time()) - (days * 24 * 60 * 60)
        try:
            with self._get_conn() as conn:
                cur = conn.cursor()
                # 根据 timestamp 字段删除
                cur.execute("DELETE FROM feed_log WHERE timestamp < ?", (limit_timestamp,))
                deleted_count = cur.rowcount
                if deleted_count > 0:
                    logger.info(f"[Atri] 已自动清理 {deleted_count} 条超过 {days} 天的旧记录。")
                conn.commit()
        except Exception as e:
            logger.error(f"[Atri] 清理旧日志失败: {e}")
            
    def _ensure_user_exists(self, cursor, user_id, group_id):
        """内部辅助方法：确保用户存在，若不存在则创建"""
        cursor.execute("SELECT user_id FROM user_state WHERE user_id=? AND group_id=?", (user_id, group_id))
        if not cursor.fetchone():
            now = int(time.time())
            cursor.execute("INSERT INTO user_state (user_id, group_id, favorability, first_seen_time) VALUES (?, ?, 10, ?)", 
                           (user_id, group_id, now))
            cursor.execute("INSERT INTO feed_stats (user_id, group_id) VALUES (?, ?)", (user_id, group_id))

    def update_favorability(self, user_id, group_id, delta):
            group_id = self._format_gid(group_id)
            with self._get_conn() as conn:
                cur = conn.cursor()
                # 更新前先确保用户存在
                self._ensure_user_exists(cur, user_id, group_id)
                
                cur.execute("UPDATE user_state SET favorability = favorability + ? WHERE user_id=? AND group_id=?", (delta, user_id, group_id))
                cur.execute("SELECT favorability FROM user_state WHERE user_id=? AND group_id=?", (user_id, group_id))
                fav = cur.fetchone()[0]
                if fav < 5:
                    cur.execute("UPDATE user_state SET is_blocked = 1 WHERE user_id=? AND group_id=?", (user_id, group_id))
                else:
                    cur.execute("UPDATE user_state SET is_blocked = 0 WHERE user_id=? AND group_id=?", (user_id, group_id))
                conn.commit()
                return fav

    def unblock_user(self, user_id, group_id):
        """用户道歉成功，全局撤销拉黑状态并重置好感度"""
        with self._get_conn() as conn:
            # 去掉 WHERE 里的 group_id 限制，这样该用户在所有群的黑名单都会被抹去
            conn.execute("""
                UPDATE user_state 
                SET is_blocked = 0, favorability = 10 
                WHERE user_id = ?
            """, (user_id,))
            conn.commit()

    def check_today_fed(self, user_id, group_id, feed_type):
        group_id = self._format_gid(group_id)
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT id FROM feed_log WHERE user_id=? AND group_id=? AND feed_type=? AND feed_date=?", (user_id, group_id, feed_type, today))
            return cur.fetchone() is not None

    def record_feeding(self, user_id, group_id, feed_type):
            group_id = self._format_gid(group_id)
            now = int(time.time())
            today = datetime.now().strftime("%Y-%m-%d")
            limit_ts = int(time.time()) - (30 * 24 * 60 * 60)
            with self._get_conn() as conn:
                cur = conn.cursor()
                # 记录前先确保用户存在
                self._ensure_user_exists(cur, user_id, group_id)
                
                cur.execute("INSERT INTO feed_log (user_id, group_id, feed_type, timestamp, feed_date) VALUES (?, ?, ?, ?, ?)", 
                            (user_id, group_id, feed_type, now, today))
                cur.execute("DELETE FROM feed_log WHERE timestamp < ?", (limit_ts,))
                mapping = {"🍓": "strawberry_count", "🍉": "watermelon_count", 
                           "🍎": "apple_count", "🍜": "noodle_count", "🍧": "shavedice_count", "🦀": "crab_count",
                           "🍔": "hamburger_count", "🍕": "pizza_count", "🍱": "bento_count", 
                            "🍄": "mushroom_count", "🍭": "lollipop_count","🍙": "riceball_count"}
                col = mapping.get(feed_type, "total_count")
                cur.execute(f"UPDATE feed_stats SET total_count = total_count + 1, {col} = {col} + 1 WHERE user_id=? AND group_id=?", (user_id, group_id))
                conn.commit()

    def check_continuous_crab(self, user_id, group_id):
        """检查过去4天是否每天都喂了螃蟹"""
        group_id = self._format_gid(group_id)
        import datetime as dt
        days = []
        for i in range(4):
            days.append((dt.datetime.now() - dt.timedelta(days=i)).strftime("%Y-%m-%d"))
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT feed_date FROM feed_log WHERE user_id=? AND group_id=? AND feed_type='🦀' AND feed_date IN (?,?,?,?)", 
                        (user_id, group_id, *days))
            return len(cur.fetchall()) >= 4

    def clear_daily_log(self):
        today = datetime.now().strftime("%Y-%m-%d")
        with self._get_conn() as conn:
            conn.execute("DELETE FROM feed_log WHERE feed_date=?", (today,))

    def record_poop_and_get_count(self, user_id, group_id):
        """记录一次便便，并返回累计次数"""
        group_id = self._format_gid(group_id)
        with self._get_conn() as conn:
            cur = conn.cursor()
            self._ensure_user_exists(cur, user_id, group_id)
            # 更新 poop_count
            cur.execute("UPDATE feed_stats SET poop_count = poop_count + 1 WHERE user_id=? AND group_id=?", (user_id, group_id))
            # 获取更新后的次数
            cur.execute("SELECT poop_count FROM feed_stats WHERE user_id=? AND group_id=?", (user_id, group_id))
            count = cur.fetchone()[0]
            conn.commit()
            return count
        
    def reset_poop_count(self, user_id, group_id):
        """道歉成功后，将便便次数清零"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE feed_stats SET poop_count = 0 WHERE user_id=? AND group_id=?", (user_id, group_id))
            conn.commit()

    def increase_forgiven_and_check_global(self, user_id, group_id):
        """增加原谅次数并检查是否触发全局拉黑"""
        group_id = self._format_gid(group_id)
        with self._get_conn() as conn:
            cur = conn.cursor()
            # 1. 增加当前群的原谅次数
            cur.execute("UPDATE user_state SET forgiven_count = forgiven_count + 1 WHERE user_id=? AND group_id=?", (user_id, group_id))
            # 2. 查询该用户在所有群的累计原谅次数
            cur.execute("SELECT SUM(forgiven_count) FROM user_state WHERE user_id=?", (user_id,))
            res = cur.fetchone()
            total_forgiven = res[0] if res and res[0] else 0
            conn.commit()
            return total_forgiven
        
    def check_user_global_block(self, user_id) -> bool:
        """查询该用户在任何群是否存在拉黑记录或好感度锁死"""
        with self._get_conn() as conn:
            cur = conn.cursor()
            # 逻辑：只要该用户在任何一个群 blocked=1，或者好感度 <= -100 (锁死状态)
            cur.execute("""
                SELECT COUNT(*) FROM user_state 
                WHERE user_id = ? AND (is_blocked = 1 OR favorability <= -100)
            """, (user_id,))
            count = cur.fetchone()[0]
            return count > 0

# 数据库表说明：
# user_state：长期核心数据
# feed_log：30 天行为记录
# feed_stats：各食物累计次数
# 

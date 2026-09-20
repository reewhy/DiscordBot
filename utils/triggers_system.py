import mysql.connector
from utils.database import BaseDatabase

class TriggersSystem(BaseDatabase):
    def __init__(self, host, user, password, database):
        super().__init__(host, user, password, database)
        self.create_table()

    def create_table(self):
        cursor = self.get_cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS triggers (
                trigger_id INT AUTO_INCREMENT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                trigger_text VARCHAR(255) NOT NULL,
                response TEXT NOT NULL,
                match_mode VARCHAR(20) NOT NULL DEFAULT 'contains',
                INDEX idx_guild (guild_id)
            )
        """)
        self.conn.commit()
        cursor.close()

    def add_trigger(self, guild_id: int, trigger_text: str, response: str, match_mode: str = "contains") -> int:
        cursor = self.get_cursor()
        cursor.execute("""
            INSERT INTO triggers (guild_id, trigger_text, response, match_mode)
            VALUES (%s, %s, %s, %s)
        """, (guild_id, trigger_text.lower(), response, match_mode))
        self.conn.commit()
        last_id = cursor.lastrowid
        cursor.close()
        return last_id

    def remove_trigger(self, guild_id: int, trigger_id: int) -> bool:
        cursor = self.get_cursor()
        cursor.execute("""
            DELETE FROM triggers 
            WHERE trigger_id = %s AND guild_id = %s
        """, (trigger_id, guild_id))
        self.conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()
        return deleted

    def get_triggers(self, guild_id: int):
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT trigger_id, trigger_text, response, match_mode 
            FROM triggers 
            WHERE guild_id = %s
            ORDER BY trigger_id ASC
        """, (guild_id,))
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def clear_triggers(self, guild_id: int) -> int:
        cursor = self.get_cursor()
        cursor.execute("DELETE FROM triggers WHERE guild_id = %s", (guild_id,))
        self.conn.commit()
        count = cursor.rowcount
        cursor.close()
        return count
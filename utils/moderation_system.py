from discord import guild
import discord
import mysql.connector
from datetime import datetime

class ModerationSystem:
    def __init__(self, host, user, password, database):
        self.conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        self.create_table()

    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS banned(
                        user_id BIGINT,
                        guild_id BIGINT,
                        reason TEXT,
                        unban_time DATETIME,
                        PRIMARY KEY(user_id, guild_id)
                    )
                       """)
        cursor.close()
    
    def tempban(self, user_id, guild_id, reason, unban_time):
        cursor = self.conn.cursor()
        cursor.execute("""
                    REPLACE INTO banned (user_id, guild_id, reason, unban_time)
                    VALUES(%s, %s, %s, %s)
                       """, (user_id, guild_id, reason, unban_time))
        self.conn.commit()
        cursor.close()

    def fetch_next_unban(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, guild_id, unban_time FROM banned ORDER BY unban_time ASC LIMIT 1")
        row = cursor.fetchone()
        cursor.close()
        return row

    def fetch_expired_bans(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, guild_id FROM banned WHERE unban_time <= %s", (datetime.utcnow()))
        rows = cursor.fetchall()
        cursor.close()

        return rows

    def delete_expired_bans(self):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM banned WHERE unban_time <= %s", (datetime.utcnow()))
        self.conn.commit()
        cursor.close()

    def pardon(self, user_id, guild_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM banned WHERE user_id=%s AND guild_id=%s", (user_id, guild_id))
        self.conn.commit()
        
        removed = cursor.rowcount > 0

        cursor.close()
        return removed


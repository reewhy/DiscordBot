from discord import guild
import discord
import mysql.connector

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

    def get_user(self, user_id, guild_id):
        cursor = self.conn.cursor()
        cursor.execute("SELECT reason, unban_time FROM banned WHERE user_id=%s AND guild_id=%s", (user_id, guild_id))
        result = cursor.fetchone()
        cursor.close()
        return result

    def ban_user(self, user: discord.Member, guild_id, reason: str = "", unban_time: str = "2100-01-01 23:59:59"):
        user.ban(reason=reason)

        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO banned (user_id, guild_id, reason, unban_time) VALUES (%s, %s, %s, %s)", (user.id, guild_id, reason, unban_time))
        
        self.conn.commit()
        cursor.close()

    def unban_user(self, user: discord.Member, guild_id, reason: str = ""):
        user = self.get_user(user.id, guild_id)

        if user is None:
            return 0
        
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM banned WHERE user_id=%s AND guild_id=%s", (user.id, guild_id))
        self.conn.commit()
        cursor.close()

        return 1


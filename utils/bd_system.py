import mysql.connector

from utils.database import BaseDatabase


class BirthdaySystem(BaseDatabase):
    def __init__(self, host, user, password, database):
        super().__init__(host, user, password, database)
        self.create_table()

    def create_table(self):
        cursor = self.get_cursor()

        cursor.execute("""
                CREATE TABLE IF NOT EXISTS birthdays(
                    user_id BIGINT,
                    birthday DATE,
                    PRIMARY KEY(user_id))
        """)

        # Tiene traccia degli auguri già inviati, per evitare doppioni dopo un riavvio del bot
        cursor.execute("""
                CREATE TABLE IF NOT EXISTS birthday_announcements(
                    guild_id BIGINT,
                    user_id BIGINT,
                    announced_on DATE,
                    PRIMARY KEY(guild_id, user_id, announced_on))
        """)
        self.conn.commit()
        cursor.close()

    def set_birthday(self, user_id, birthday):
        cursor = self.get_cursor()
        cursor.execute("""
                       INSERT INTO birthdays (user_id, birthday)
                       VALUES (%s, %s) ON DUPLICATE KEY
                       UPDATE birthday = %s
                       """, (user_id, birthday, birthday))

        self.conn.commit()
        cursor.close()

    def remove_birthday(self, user_id):
        cursor = self.get_cursor()
        cursor.execute(
            """
            DELETE
            FROM birthdays
            WHERE user_id = %s""",
            (user_id,),
        )
        self.conn.commit()
        cursor.close()

    def get_birthday(self, user_id):
        cursor = self.get_cursor()
        cursor.execute("""
                       SELECT birthday FROM birthdays WHERE user_id = %s""", (user_id,))
        result = cursor.fetchone()
        cursor.close()

        if result:
            return result
        return None

    def get_birthdays(self, date):
        cursor = self.get_cursor()
        cursor.execute(
            """
            SELECT user_id
            FROM birthdays
            WHERE DAY(birthday) = %s
              AND MONTH(birthday) = %s
            """,
            (date.day, date.month),
        )

        result = cursor.fetchall()
        cursor.close()

        return result if result else []

    # ------------------------------------------------------------------
    # Tracciamento degli annunci
    # ------------------------------------------------------------------
    def was_announced(self, guild_id, user_id, date):
        cursor = self.get_cursor()
        cursor.execute(
            """
            SELECT 1
            FROM birthday_announcements
            WHERE guild_id = %s
              AND user_id = %s
              AND announced_on = %s
            """,
            (guild_id, user_id, date),
        )
        result = cursor.fetchone()
        cursor.close()
        return result is not None

    def mark_announced(self, guild_id, user_id, date):
        cursor = self.get_cursor()
        cursor.execute(
            """
            INSERT IGNORE INTO birthday_announcements (guild_id, user_id, announced_on)
            VALUES (%s, %s, %s)
            """,
            (guild_id, user_id, date),
        )
        self.conn.commit()
        cursor.close()

    def cleanup_announcements(self, before_date):
        """Elimina le registrazioni degli annunci precedenti a before_date."""
        cursor = self.get_cursor()
        cursor.execute(
            "DELETE FROM birthday_announcements WHERE announced_on < %s",
            (before_date,),
        )
        self.conn.commit()
        cursor.close()
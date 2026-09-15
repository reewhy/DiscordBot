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
            WHERE DAY (birthday) = %s
              AND MONTH (birthday) = %s
            """,
            (date.day, date.month),
        )

        result = cursor.fetchall()
        cursor.close()

        return result if result else []
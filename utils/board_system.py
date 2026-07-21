import mysql.connector

class BoardSystem:
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
                        CREATE TABLE IF NOT EXISTS board(
                            message_id BIGINT,
                            reactions INT,
                            boarded INT,
                            PRIMARY KEY (message_id))
        """)
        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS board_config(
                            min_reactions INT)
        """)
        cursor.close()

    def set_min_reactions(self, num):
        cursor = self.conn.cursor(buffered = True)

        cursor.execute("""
            SELECT min_reactions FROM board_config
                """)

        result = cursor.fetchone()

        if result:
            cursor.execute("""
                UPDATE board_config SET min_reactions = %s
                    """, (num,))
        else:
            cursor.execute("""
            INSERT INTO board_config (min_reactions) VALUES (%s)
                """, (num,))

        self.conn.commit()
        cursor.close()

    def get_min_reactions(self):
        cursor = self.conn.cursor(buffered = True)

        cursor.execute("""
            SELECT * FROM board_config
        """)

        result = cursor.fetchone()

        if result:
            cursor.close()
            return result
        else:
            cursor.close()
            self.set_min_reactions(1)

    def add_reaction(self, message_id):
        cursor = self.conn.cursor(buffered = True)

        cursor.execute("""
            SELECT * FROM board WHERE message_id = %s
        """, (message_id,))

        result = cursor.fetchone()

        if result:
            cursor.execute("""
                           UPDATE board SET reactions = reactions + 1 WHERE message_id = %s
                           """, (message_id,))
        else:
            cursor.execute("""
                           INSERT INTO board (message_id, reactions) VALUES (%s, %s)""", (message_id, 1))
        self.conn.commit()
        cursor.close()

    def remove_reaction(self, message_id):
        print("not implemented")
        # prendi il messaggio
        # controlla se ha reazione
        # se non ha reazioni, return
        # se ha reazioni, eliminane una
        # se ha 0 reazioni, eliminare dalla board

    def add_boarded(self, message_id):
        cursor = self.conn.cursor(buffered = True)

        cursor.execute("""
            UPDATE board SET boarded = 1 WHERE message_id = %s""", (message_id,))

        self.conn.commit()
        cursor.close()

    def get_reactions(self, message_id):
        cursor = self.conn.cursor(buffered = True)

        cursor.execute("""
            SELECT reactions FROM board WHERE message_id = %s
        """, (message_id,))

        result = cursor.fetchone()

        return result
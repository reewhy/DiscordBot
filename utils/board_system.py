import mysql.connector

from utils.database import BaseDatabase


class BoardSystem(BaseDatabase):
    def __init__(self, host, user, password, database):
        super().__init__(host, user, password, database)
        self.create_table()

    def create_table(self):
        cursor = self.get_cursor()

        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS board
                       (
                           message_id
                           BIGINT,
                           reactions
                           INT,
                           boarded
                           BIGINT,
                           PRIMARY
                           KEY
                       (
                           message_id
                       )
                           )
                       """)

        # Modificata per salvare le impostazioni per ogni singolo server (guild_id)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS board_config
                       (
                           guild_id
                           BIGINT,
                           channel_id
                           BIGINT,
                           min_reactions
                           INT
                           DEFAULT
                           1,
                           PRIMARY
                           KEY
                       (
                           guild_id
                       )
                           )
                       """)
        cursor.close()

    # --- NUOVI METODI PER IL CANALE DELLA BOARD ---
    def set_board_channel(self, guild_id, channel_id):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT guild_id FROM board_config WHERE guild_id = %s", (guild_id,))

        if cursor.fetchone():
            cursor.execute("""
                           UPDATE board_config
                           SET channel_id = %s
                           WHERE guild_id = %s
                           """, (channel_id, guild_id))
        else:
            cursor.execute("""
                           INSERT INTO board_config (guild_id, channel_id, min_reactions)
                           VALUES (%s, %s, 1)
                           """, (guild_id, channel_id))

        self.conn.commit()
        cursor.close()

    def get_board_channel(self, guild_id):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT channel_id FROM board_config WHERE guild_id = %s", (guild_id,))
        result = cursor.fetchone()
        cursor.close()

        if result:
            return result[0]
        return None

    # --- METODI AGGIORNATI PER LE REAZIONI (Ora basati sul guild_id) ---
    def set_min_reactions(self, guild_id, num):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT guild_id FROM board_config WHERE guild_id = %s", (guild_id,))

        if cursor.fetchone():
            cursor.execute("UPDATE board_config SET min_reactions = %s WHERE guild_id = %s", (num, guild_id))
        else:
            cursor.execute("INSERT INTO board_config (guild_id, min_reactions) VALUES (%s, %s)", (guild_id, num))

        self.conn.commit()
        cursor.close()

    def get_min_reactions(self, guild_id):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT min_reactions FROM board_config WHERE guild_id = %s", (guild_id,))
        result = cursor.fetchone()
        cursor.close()

        if result:
            return result[0]

        # Valore di default se non impostato
        return 1

    # --- METODI DEI MESSAGGI (Invariati) ---
    def add_reaction(self, message_id):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT * FROM board WHERE message_id = %s", (message_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE board SET reactions = reactions + 1 WHERE message_id = %s", (message_id,))
        else:
            cursor.execute("INSERT INTO board (message_id, reactions) VALUES (%s, %s)", (message_id, 1))
        self.conn.commit()
        cursor.close()

    def remove_reaction(self, message_id):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT reactions FROM board WHERE message_id = %s", (message_id,))
        result = cursor.fetchone()
        if not result:
            cursor.close()
            return

        current_reactions = result[0]
        if current_reactions > 1:
            cursor.execute("UPDATE board SET reactions = reactions - 1 WHERE message_id = %s", (message_id,))
        else:
            cursor.execute("DELETE FROM board WHERE message_id = %s", (message_id,))
        self.conn.commit()
        cursor.close()

    def add_boarded(self, message_id, board_index):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("UPDATE board SET boarded = %s WHERE message_id = %s", (board_index, message_id))
        self.conn.commit()
        cursor.close()

    def get_boarded(self, message_id):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT boarded FROM board WHERE message_id = %s", (message_id,))
        result = cursor.fetchone()
        cursor.close()
        return result if result else 0

    def remove_boarded(self, message_id):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("UPDATE board SET boarded = 0 WHERE message_id = %s", (message_id,))
        self.conn.commit()
        cursor.close()

    def get_reactions(self, message_id):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT reactions FROM board WHERE message_id = %s", (message_id,))
        result = cursor.fetchone()
        cursor.close()
        return result
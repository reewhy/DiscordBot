import mysql.connector

class ServerSystem:
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
                        CREATE TABLE IF NOT EXISTS channels(
                            guild_id BIGINT,
                            channel_id BIGINT,
                            description varchar(100),
                            PRIMARY KEY(guild_id, channel_id))
                       """)
        cursor.execute("""
                        CREATE TABLE IF NOT EXISTS descriptions(
                            guild_id BIGINT,
                            description TEXT,
                            PRIMARY KEY(guild_id))
                        """)
        cursor.close()

    def add_channel(self, guild_id, channel_id, description = ""):
        cursor = self.conn.cursor(buffered = True)
        
        cursor.execute(
            """
            SELECT guild_id FROM channels WHERE guild_id = %s AND description = %s
            """, (guild_id, description)
        )

        result = cursor.fetchone()

        if result:
            cursor.execute("""
                UPDATE channels SET channel_id = %s WHERE guild_id = %s AND description = %s
            """, (channel_id, guild_id, description))
        else:
            cursor.execute("""
                            INSERT INTO channels VALUES(%s, %s, %s)
                        """, (guild_id, channel_id, description))
        self.conn.commit()
        cursor.close()

    def set_description(self, guild_id, description):
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT guild_id FROM descriptions WHERE guild_id = %s
        """, (guild_id, ))

        result = cursor.fetchone()

        if result:
            cursor.execute(
                """
                UPDATE descriptions SET description = %s WHERE guild_id = %s
                """, (description, guild_id)
            )
        else:
            cursor.execute(
                """
                INSERT INTO descriptions VALUES(%s, %s)
                """, (guild_id, description)
            )

        self.conn.commit()
        cursor.close()

    def get_description(self, guild_id):
        cursor = self.conn.cursor(buffered = True)
        cursor.execute(
            """
            SELECT description FROM descriptions WHERE guild_id = %s
            """, (guild_id, )
        )
        result = cursor.fetchone()[0]
        
        if not result:
            result = (f"Benvenuto %u!\nTi diamo il benvenuto nel nostro magnifico server.\nSpero tu ti possa trovare a tuo agio.", )
            set_description(guild_id, result)

        cursor.close()
        return result

    def get_level_channel(self, guild_id):
        cursor = self.conn.cursor(buffered = True)
        cursor.execute("""
                        SELECT channel_id FROM channels WHERE guild_id = %s AND description="level"
                       """, (guild_id,))
        result = cursor.fetchone()
        cursor.close()
        return result

    def get_announce_channel(self, guild_id):
        cursor = self.conn.cursor(buffered = True)
        cursor.execute("""
                        SELECT channel_id FROM channels WHERE guild_id = %s AND description="announce"
                       """, (guild_id,))
        result = cursor.fetchone()
        cursor.close()
        return result

    def get_channels(self, guild_id):
        cursor = self.conn.cursor()
        cursor.execute("""
                        SELECT channel_id, description FROM channels WHERE guild_id = %s AND description NOT IN ('level', 'announce')
                       """, (guild_id,))
        result = cursor.fetchall()
        cursor.close()
        return result

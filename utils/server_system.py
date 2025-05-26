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
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS onjoin(
                role_id BIGINT,
                guild_id BIGINT,
                PRIMARY KEY(role_id, guild_id))
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS level_roles(
                guild_id BIGINT,
                role_id BIGINT,
                level INT,
                PRIMARY KEY(guild_id, role_id))
            """
        )
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

    def set_role(self, guild_id, role_id):
        cursor = self.conn.cursor(buffered = True)
        cursor.execute(
            """
            SELECT guild_id FROM onjoin WHERE guild_id = %s AND role_id = %s
            """, (guild_id, role_id)
        )

        result = cursor.fetchone()

        if result:
            cursor.execute(
                """
                UPDATE onjoin SET role_id = %s WHERE guild_id = %s
                """, (role_id, guild_id)
            )
        else:
            cursor.execute(
                """
                INSERT INTO onjoin VALUES(%s, %s)
                """, (role_id, guild_id)
            )
        self.conn.commit()
        cursor.close()

    def get_role(self, guild_id):
        cursor = self.conn.cursor(buffered = True)
        cursor.execute("""
                        SELECT role_id FROM onjoin WHERE guild_id = %s
                       """, (guild_id,))
        result = cursor.fetchone()
        return result
    
    def add_role(self, guild_id, role_id, level):
        cursor = self.conn.cursor(buffered = True)
        cursor.execute(
            """
            SELECT role_id FROM level_roles WHERE guild_id = %s AND role_id = %s
            """, (guild_id, role_id)
        )
        result = cursor.fetchone()

        if result:
            cursor.execute(
                """
                UPDATE level_roles SET level = %s WHERE guild_id = %s AND role_id = %s
                """, (level, guild_id, role_id)
            )
        else:
            cursor.execute(
                """
                INSERT INTO level_roles VALUES(%s, %s, %s)
                """, (guild_id, role_id, level)
            )
        self.conn.commit()
        cursor.close()

    def get_all_roles(self, guild_id, level):
        cursor = self.conn.cursor(buffered = True)

        cursor.execute(
            """
            SELECT role_id FROM level_roles WHERE guild_id = %s AND level = %s
            """, (guild_id, level)
        )

        result = cursor.fetchall()
        return result

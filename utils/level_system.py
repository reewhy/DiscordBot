import mysql.connector

class LevelSystem:
    """
    Communication with MySQL database for level management.

    Attributes:
        host (str): Database server hostname,
        user (str): Database server username,
        password (str): The amount of cats you want /ᐠ˵- ⩊ -˵マ.
        database (str): Database name in the server.
    """
    def __init__(self, host, user, password, database):
        """
        Initialize the level system and connects to the database.

        Args:
            host (str): Database server hostname.
            user (str): Database server username.
            password (str): The amount of cats you want /ᐠ˵- ⩊ -˵マ.
            database (str): Database name in the server.
        """
        self.conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        self.create_table()

    def create_table(self):
        """
        Creates the table if it doesn't exist

        Database structure:
            
        +------------+--------+-------+
        | Field Name |  Type  | Extra |
        +------------+--------+-------+
        | user_id    | BIGINT | {PK}  |
        | guild_id   | BIGINT | {PK}  |
        | XP         | INT    |       |
        | level      | INT    |       |
        +------------+--------+-------+


        """
        cursor = self.conn.cursor()
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS levels(
                        user_id BIGINT,
                        guild_id BIGINT,
                        xp INT DEFAULT 0,
                        level INT DEFAULT 0,
                        PRIMARY KEY(user_id, guild_id)
                    )
                        
                       """)
        cursor.close()

    def get_user(self, user_id, guild_id):
        """
        Get user from database.

        Args:
            user_id (int): User uinque identifier.
            guild_id (int): Server ID.

        Returns:
            xp (int): User's XP.
            level (int): User's level
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT xp, level FROM levels WHERE user_id = %s AND guild_id = %s", (user_id, guild_id))
        result = cursor.fetchone()
        cursor.close()
        return result

    def add_xp(self, user_id, guild_id, amount):
        """
        Add XP to user.

        Args:
            user_id (int): User identifier.
            guild_id (int): Server id.
            amount (int): Amount of XP to add.

        Returns:
            int: New level reached by user.
        """
        user = self.get_user(user_id, guild_id)
        # Create an user if it didn't exist before
        if user is None:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO levels (user_id, guild_id, xp) VALUES (%s, %s, %s)", (user_id, guild_id, amount))
            self.conn.commit()
            cursor.close()
            return 1
        
        xp, level = user
        xp += amount
        new_level = level

        if xp >= level * 100:
            xp = 0
            new_level += 1

        cursor = self.conn.cursor()
        cursor.execute("""
                REPLACE INTO levels (user_id, guild_id, xp, level)
                VALUES (%s, %s, %s, %s)
                       """, (user_id, guild_id, xp, new_level))
        self.conn.commit()
        cursor.close()

        return new_level

    def add_levels(self, user_id, guild_id, amount):
        """
        Add levels to user.

        Args:
            user_id (int): User identifier.
            guild_id (int): Server id.
            amount (int): Amount of levels to add.

        Returns:
            int: New user's level.
        """
        user = self.get_user(user_id, guild_id)
        # Create an user if it didn't exist before
        if user is None:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO levels (user_id, guild_id, level) VALUES (%s, %s, %s)", (user_id, guild_id, amount))
            self.conn.commit()
            cursor.close()
            return 1
        
        xp, level = user
        level += amount

        cursor = self.conn.cursor()
        cursor.execute("""
                REPLACE INTO levels (user_id, guild_id, xp, level)
                VALUES (%s, %s, %s, %s)
                       """, (user_id, guild_id, xp, level))
        self.conn.commit()
        cursor.close()

        return level


    def set_level(self, user_id, guild_id, value):
        """
        Set user's level

        Args:
            user_id (int): User identifier.
            guild_id (int): Server ID.
            value (int): New value for user's level.

        Returns:
            int: New user level.
        """
        user = self.get_user(user_id, guild_id)
        if user is None:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO levels (user_id, guild_id, level) VALUES (%s, %s, %s)", (user_id,  guild_id, value))
            self.conn.commit()
            cursor.close()
            return 1
        
        xp, level = user
        
        cursor = self.conn.cursor()
        cursor.execute("""
                    REPLACE INTO levels (user_id, guild_id, xp, level)
                    VALUES (%s, %s, %s, %s)
                        """, (user_id, guild_id, xp, value))
        self.conn.commit()
        cursor.close()

        return value

    def set_xp(self, user_id, guild_id, value):
        """
        Set user's XP.

        Args:
            user_id (int): User identifier.
            guild_id (int): Server ID.
            value (int): New value for user's XP.

        Returns:
            int: New user's XP.
        """
        user = self.get_user(user_id, guild_id)
        if user is None:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO levels (user_id, guild_id, xp) VALUES (%s, %s, %s)", (user_id,  guild_id, value))
            self.conn.commit()
            cursor.close()
            return 1
        
        xp, level = user
        
        cursor = self.conn.cursor()
        cursor.execute("""
                    REPLACE INTO levels (user_id, guild_id, xp, level)
                    VALUES (%s, %s, %s, %s)
                        """, (user_id, guild_id, value, level))
        self.conn.commit()
        cursor.close()

        return value

    def reset_level(self, user_id, guild_id):
        """
        Reset a user

        Args:
            user_id (int): User identifier.
            guild_id (int): Server ID.

        Returns:
            bool: if true it's a success, if false the user doesn't exist yet.
        """
        user = self.get_user(user_id, guild_id)

        if user is None:
            return False
        cursor = self.conn.cursor()
        cursor.execute("""
                DELETE FROM levels WHERE user_id = %s AND guild_id = %s
                       """, (user_id, guild_id))

        self.conn.commit()
        cursor.close()

        return True


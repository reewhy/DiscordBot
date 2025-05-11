import mysql.connector

class LevelSystem:
    """
    A system to manage user levels and experience points (XP) in a Discord server using a MySQL database.

    This class handles communication with a MySQL database to manage user XP and levels within a specified Discord guild.
    It supports functionality such as adding XP, setting levels, and resetting user data.

    Attributes:
        conn (mysql.connector.connection.MySQLConnection): The MySQL database connection object.
    """
    def __init__(self, host, user, password, database):
        """
        Initializes the LevelSystem instance and establishes a connection to the MySQL database.

        Args:
            host (str): The hostname or IP address of the MySQL server.
            user (str): The username for authenticating with the MySQL server.
            password (str): The password for authenticating with the MySQL server.
            database (str): The name of the database to connect to.

        This constructor also creates the necessary table in the database if it doesn't exist already.
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
        Creates the `levels` table in the database if it doesn't already exist.

        This table stores user data for level management, including:
        - user_id: The unique ID of the user.
        - guild_id: The ID of the Discord guild (server) where the user is active.
        - xp: The experience points (XP) of the user.
        - level: The level of the user.

        Returns:
            None
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
        Retrieves the XP and level of a user from the database.

        Args:
            user_id (int): The unique ID of the user.
            guild_id (int): The ID of the guild (Discord server) where the user is active.

        Returns:
            tuple: A tuple containing the user's XP and level, or `None` if the user doesn't exist in the database.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT xp, level FROM levels WHERE user_id = %s AND guild_id = %s", (user_id, guild_id))
        result = cursor.fetchone()
        cursor.close()
        return result

    def add_xp(self, user_id, guild_id, amount):
        """
        Adds experience points (XP) to a user's current total and levels them up if necessary.

        Args:
            user_id (int): The unique ID of the user.
            guild_id (int): The ID of the guild (Discord server) where the user is active.
            amount (int): The amount of XP to add to the user's total.

        Returns:
            int: The new level of the user after the XP is added.
        """
        user = self.get_user(user_id, guild_id)
        
        # If the user doesn't exist in the database, create a new entry with the given XP.
        if user is None:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO levels (user_id, guild_id, xp) VALUES (%s, %s, %s)", (user_id, guild_id, amount))
            self.conn.commit()
            cursor.close()
            return 1  # The user starts at level 1
        
        xp, level = user
        xp += amount
        new_level = level

        # Check if the XP exceeds the threshold for leveling up.
        if xp >= level * 100:
            xp = 0  # Reset XP after leveling up.
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
        Adds a specified number of levels directly to a user's current level.

        Args:
            user_id (int): The unique ID of the user.
            guild_id (int): The ID of the guild (Discord server) where the user is active.
            amount (int): The number of levels to add to the user's current level.

        Returns:
            int: The new level of the user after the levels are added.
        """
        user = self.get_user(user_id, guild_id)
        
        # If the user doesn't exist in the database, create a new entry with the specified level.
        if user is None:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO levels (user_id, guild_id, level) VALUES (%s, %s, %s)", (user_id, guild_id, amount))
            self.conn.commit()
            cursor.close()
            return amount  # The user starts at the specified level
        
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
        Sets a specific level for a user in the database.

        Args:
            user_id (int): The unique ID of the user.
            guild_id (int): The ID of the guild (Discord server) where the user is active.
            value (int): The level to set for the user.

        Returns:
            int: The new level of the user.
        """
        user = self.get_user(user_id, guild_id)
        
        if user is None:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO levels (user_id, guild_id, level) VALUES (%s, %s, %s)", (user_id, guild_id, value))
            self.conn.commit()
            cursor.close()
            return value  # The user starts at the specified level
        
        xp, _ = user
        
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
        Sets a specific amount of XP for a user in the database.

        Args:
            user_id (int): The unique ID of the user.
            guild_id (int): The ID of the guild (Discord server) where the user is active.
            value (int): The amount of XP to set for the user.

        Returns:
            int: The new XP value for the user.
        """
        user = self.get_user(user_id, guild_id)
        
        if user is None:
            cursor = self.conn.cursor()
            cursor.execute("INSERT INTO levels (user_id, guild_id, xp) VALUES (%s, %s, %s)", (user_id, guild_id, value))
            self.conn.commit()
            cursor.close()
            return value  # The user starts with the specified XP
        
        level, _ = user
        
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
        Resets a user's level and XP by removing their entry from the database.

        Args:
            user_id (int): The unique ID of the user.
            guild_id (int): The ID of the guild (Discord server) where the user is active.

        Returns:
            bool: `True` if the user was successfully reset (removed from the database), `False` if the user doesn't exist.
        """
        user = self.get_user(user_id, guild_id)

        if user is None:
            return False  # User does not exist
        
        cursor = self.conn.cursor()
        cursor.execute("""
                DELETE FROM levels WHERE user_id = %s AND guild_id = %s
                       """, (user_id, guild_id))

        self.conn.commit()
        cursor.close()

        return True

from discord import guild
import discord
import mysql.connector
from datetime import datetime

class ModerationSystem:
    """
    A system to manage temporary bans in a Discord server using a MySQL database.

    This class handles communication with a MySQL database to manage temporary bans for users in a Discord guild.
    It supports functionality such as banning users, unbanning users after a specified time, fetching information about 
    the next unban, and deleting expired bans.

    Attributes:
        conn (mysql.connector.connection.MySQLConnection): The MySQL database connection object.
    """
    def __init__(self, host, user, password, database):
        """
        Initializes the ModerationSystem instance and establishes a connection to the MySQL database.

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
        Creates the `banned` table in the database if it doesn't already exist.

        This table stores information about users who are temporarily banned, including:
        - user_id: The ID of the banned user.
        - guild_id: The ID of the Discord server (guild) where the user is banned.
        - reason: The reason for the temporary ban.
        - unban_time: The time at which the user will be unbanned.

        Returns:
            None
        """
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
        """
        Bans a user temporarily by inserting their information into the `banned` table.

        Args:
            user_id (int): The ID of the user to ban.
            guild_id (int): The ID of the guild (Discord server) where the user is being banned.
            reason (str): The reason for the ban.
            unban_time (datetime): The time at which the user will be automatically unbanned.

        Returns:
            None
        """
        cursor = self.conn.cursor()
        cursor.execute("""
                    REPLACE INTO banned (user_id, guild_id, reason, unban_time)
                    VALUES(%s, %s, %s, %s)
                       """, (user_id, guild_id, reason, unban_time))
        self.conn.commit()
        cursor.close()

    def fetch_next_unban(self):
        """
        Retrieves the next user who is scheduled to be unbanned.

        This method queries the `banned` table for the user with the earliest `unban_time`.

        Returns:
            tuple: A tuple containing the user ID, guild ID, and unban time of the next user to be unbanned,
                   or `None` if no user is found.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, guild_id, unban_time FROM banned ORDER BY unban_time ASC LIMIT 1")
        row = cursor.fetchone()
        cursor.close()
        return row

    def fetch_expired_bans(self):
        """
        Fetches all users whose temporary ban has expired.

        This method queries the `banned` table for all users where the `unban_time` is less than or equal to the current time.

        Returns:
            list: A list of tuples, each containing the user ID and guild ID of a user whose ban has expired.
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT user_id, guild_id FROM banned WHERE unban_time <= %s", (datetime.utcnow(),))
        rows = cursor.fetchall()
        cursor.close()

        return rows

    def delete_expired_bans(self):
        """
        Deletes all expired bans from the `banned` table.

        This method removes entries from the table where the `unban_time` is less than or equal to the current time.

        Returns:
            None
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM banned WHERE unban_time <= %s", (datetime.utcnow(),))
        self.conn.commit()
        cursor.close()

    def pardon(self, user_id, guild_id):
        """
        Pardons (removes) a user's temporary ban before the scheduled unban time.

        Args:
            user_id (int): The ID of the user to pardon (remove the ban).
            guild_id (int): The ID of the guild (Discord server) where the user is being pardoned.

        Returns:
            bool: `True` if the user was successfully pardoned (removed from the `banned` table), 
                  `False` if no ban was found for the user in the specified guild.
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM banned WHERE user_id=%s AND guild_id=%s", (user_id, guild_id))
        self.conn.commit()
        
        removed = cursor.rowcount > 0

        cursor.close()
        return removed

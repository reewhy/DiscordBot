import mysql.connector

class RoleSystem:
    """
    A system to manage self-roles messages in a Discord server using a MySQL database.

    This class handles communication with a MySQL database to manage self-roles messages within a specified Discord guild.
    It supports functionality such as creating a message, adding selectable roles to said message and edit the messages already created.

    Attributes:
        conn (mysql.connector.connection.MySQLConnection): The MySQL database connection object.
    """
    def __init__(self, host, user, password, database):
        """
        Initializes the RoleSystem instance and establishes a connection to the MySQL database.

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
            database=database,
            charset='utf8mb4',
            use_unicode = True
        )
        self.create_table()

    def create_table(self):
        """
        Creates the `messages` and `roles` tables in the database if it doesn't already exist.

        `messages` stores messages data for self-roles management, including:
        - id: The unique ID of the message.

        `roles` stores all the message's roles for self-roles management, including:
        - id: The unique ID of the roles.
        - emoji: Emoji that identifies said role.
        - message: Reference the message the role is related to.


        Returns:
            None
        """
        cursor = self.conn.cursor()
        cursor.execute("""
                    CREATE TABLE IF NOT EXISTS messages(
                        message_id BIGINT,
                        PRIMARY KEY(message_id)
                    );
                    
                       """)
        cursor.execute("""
                   CREATE TABLE IF NOT EXISTS roles(
                        role_id BIGINT,
                        emoji VARCHAR(100),
                        message BIGINT,
                        PRIMARY KEY (role_id, message),
                        FOREIGN KEY (message) REFERENCES messages(message_id)
                    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin; 
                     """)
        cursor.close()
    
    def create_message(self, message_id: int):
        """
        Add a message in the `messages` table.

        Args:
            message_id (int): Unique ID of message.
        
        Returns:
            boolean: True for success, False for failure
        """
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO messages(message_id) VALUES(%s)", (message_id,))
        self.conn.commit()
        cursor.close()

    def reset(self):
        """
        Reset `roles` table
        """
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM roles")
        self.conn.commit()
        cursor.close()

    def get_role(self, message_id: int, emoji: str) -> int:
        """
        Returns a role based on a message id

        Args:
            message_id (int): Unique ID of message.
            emoji (int): Emoji of wanted role.
    
        Returns:
            int: Role id
        """

        print(f"Getting: {emoji}")
        cursor = self.conn.cursor(buffered = True)
        cursor.execute("SELECT role_id FROM roles WHERE message=%s AND BINARY emoji=%s", (message_id, emoji))

        result = cursor.fetchone()
        return result
    
    def add_role(self, message_id: int, role_id: int, emoji: int):
        """
        Add a new role to a message.

        Args:
            message_id (int): Unique ID of message.
            role_id (int): Unique ID of the role.
            emoji (int): Emoji that identifies the role.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
                        INSERT INTO roles(role_id, emoji, message)
                        VALUES (%s, %s, %s)
                       """, (role_id, emoji, message_id))
        self.conn.commit()
        cursor.close()


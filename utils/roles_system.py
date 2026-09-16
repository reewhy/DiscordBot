import mysql.connector
from utils.database import BaseDatabase

class RoleSystem(BaseDatabase):
    """
    A system to manage self-roles messages in a Discord server using a MySQL database.
    """
    def __init__(self, host, user, password, database):
        super().__init__(
            host=host,
            user=user,
            password=password,
            database=database,
            charset='utf8mb4',
            use_unicode=True
        )
        self.create_table()

    def create_table(self):
        cursor = self.get_cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages(
                message_id BIGINT PRIMARY KEY,
                multiselect BOOLEAN DEFAULT TRUE
            );
        """)
        # In case the table already existed without the column
        try:
            cursor.execute("""
                ALTER TABLE messages ADD COLUMN multiselect BOOLEAN DEFAULT TRUE;
            """)
        except mysql.connector.Error:
            pass  # Column already exists

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roles(
                role_id BIGINT,
                emoji VARCHAR(100),
                message BIGINT,
                PRIMARY KEY (role_id, message),
                FOREIGN KEY (message) REFERENCES messages(message_id) ON DELETE CASCADE
            ) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin;
        """)
        self.conn.commit()
        cursor.close()

    def ensure_message(self, message_id: int):
        """Ensures the message row exists in messages table so foreign keys work."""
        cursor = self.get_cursor()
        cursor.execute("""
            INSERT IGNORE INTO messages(message_id, multiselect)
            VALUES (%s, TRUE)
        """, (message_id,))
        self.conn.commit()
        cursor.close()

    def set_multiselect(self, message_id: int, enabled: bool):
        """Enables or disables multiselect for a specific message."""
        self.ensure_message(message_id)
        cursor = self.get_cursor()
        cursor.execute("""
            UPDATE messages
            SET multiselect = %s
            WHERE message_id = %s
        """, (enabled, message_id))
        self.conn.commit()
        cursor.close()

    def is_multiselect(self, message_id: int) -> bool:
        """Returns True if the message allows multiple roles, False for single-choice."""
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT multiselect FROM messages WHERE message_id = %s", (message_id,))
        row = cursor.fetchone()
        cursor.close()
        if row is not None:
            return bool(row[0])
        return True

    def get_role(self, message_id: int, emoji: str):
        """Returns the role_id mapped to the emoji on a given message."""
        cursor = self.get_cursor(buffered=True)
        cursor.execute("""
            SELECT role_id FROM roles
            WHERE message = %s AND BINARY emoji = %s
        """, (message_id, str(emoji)))
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else None

    def get_all_roles_for_message(self, message_id: int) -> list[dict]:
        """Returns all roles and their emojis configured for a message."""
        cursor = self.get_cursor(buffered=True)
        cursor.execute("""
            SELECT role_id, emoji FROM roles
            WHERE message = %s
        """, (message_id,))
        rows = cursor.fetchall()
        cursor.close()
        return [{"role_id": row[0], "emoji": row[1]} for row in rows]

    def add_role(self, message_id: int, role_id: int, emoji: str):
        """Adds a new role mapping to a message."""
        self.ensure_message(message_id)
        cursor = self.get_cursor()
        cursor.execute("""
            INSERT INTO roles(role_id, emoji, message)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE emoji = VALUES(emoji)
        """, (role_id, str(emoji), message_id))
        self.conn.commit()
        cursor.close()

    def get_emoji(self, message_id: int, role_id: int) -> str | None:
        """Gets the emoji mapped to a role on a message."""
        cursor = self.get_cursor()
        cursor.execute("""
            SELECT emoji FROM roles
            WHERE message = %s AND role_id = %s
        """, (message_id, role_id))
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else None

    def remove_role(self, message_id: int, role_id: int):
        """Removes a role mapping from a message."""
        cursor = self.get_cursor()
        cursor.execute("""
            DELETE FROM roles
            WHERE message = %s AND role_id = %s
        """, (message_id, role_id))
        self.conn.commit()
        cursor.close()

    def reset(self):
        """Clears all role mappings."""
        cursor = self.get_cursor()
        cursor.execute("DELETE FROM roles")
        cursor.execute("DELETE FROM messages")
        self.conn.commit()
        cursor.close()
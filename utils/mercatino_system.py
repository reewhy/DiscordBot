from decimal import Decimal

from utils.database import BaseDatabase


class MercatinoSystem(BaseDatabase):
    def __init__(self, host, user, password, database):
        super().__init__(host, user, password, database)
        self.create_tables()

    # ------------------------------------------------------------------
    # SCHEMA
    # ------------------------------------------------------------------
    def create_tables(self):
        cursor = self.get_cursor()

        # Un thread del forum = un annuncio. Il thread_id coincide con l'id
        # del messaggio iniziale, quindi basta questo come chiave.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mercatino_posts (
                thread_id        BIGINT NOT NULL,
                guild_id         BIGINT NOT NULL,
                forum_id         BIGINT NOT NULL,
                author_id        BIGINT NULL,
                author_name      VARCHAR(100) NULL,
                author_avatar    VARCHAR(512) NULL,
                title            VARCHAR(100) NOT NULL,
                content          MEDIUMTEXT NULL,
                tags             VARCHAR(255) NULL,           -- nomi dei tag separati da virgola
                image_url        VARCHAR(1024) NULL,          -- prima immagine (copertina)
                attachments      INT NOT NULL DEFAULT 0,
                jump_url         VARCHAR(255) NULL,
                message_count    INT NOT NULL DEFAULT 0,
                archived         TINYINT(1) NOT NULL DEFAULT 0,
                locked           TINYINT(1) NOT NULL DEFAULT 0,
                active           TINYINT(1) NOT NULL DEFAULT 1,  -- 0 = thread cancellato
                created_at       DATETIME NULL,
                last_activity_at DATETIME NULL,
                updated_at       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                 ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (thread_id),
                KEY idx_author (guild_id, author_id),
                KEY idx_active (guild_id, active, created_at)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mercatino_attachments (
                thread_id    BIGINT NOT NULL,
                position     INT NOT NULL,
                url          VARCHAR(1024) NOT NULL,
                filename     VARCHAR(255) NULL,
                content_type VARCHAR(100) NULL,
                PRIMARY KEY (thread_id, position)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        cursor.close()

    # ------------------------------------------------------------------
    # HELPER
    # ------------------------------------------------------------------
    def _query(self, sql, params=()):
        """SELECT -> lista di dict (Decimal convertiti in int)."""
        cursor = self.get_cursor(buffered=True)
        cursor.execute(sql, params)
        cols = [c[0] for c in cursor.description]
        rows = []
        for row in cursor.fetchall():
            rows.append({
                col: (int(val) if isinstance(val, Decimal) else val)
                for col, val in zip(cols, row)
            })
        cursor.close()
        return rows

    def _execute(self, sql, params=()):
        cursor = self.get_cursor(buffered=True)
        cursor.execute(sql, params)
        self.conn.commit()
        cursor.close()

    # ------------------------------------------------------------------
    # SCRITTURA
    # ------------------------------------------------------------------
    def upsert_post(self, data: dict):
        """Crea/aggiorna un annuncio. `data` usa i nomi colonna di mercatino_posts."""
        cols = list(data)
        placeholders = ", ".join(["%s"] * len(cols))
        updates = ", ".join(f"{c} = VALUES({c})" for c in cols if c != "thread_id")
        sql = (
            f"INSERT INTO mercatino_posts ({', '.join(cols)}, active) "
            f"VALUES ({placeholders}, 1) "
            f"ON DUPLICATE KEY UPDATE {updates}, active = 1"
        )
        self._execute(sql, tuple(data.values()))

    def replace_attachments(self, thread_id, attachments: list[dict]):
        """Sostituisce gli allegati di un annuncio (url, filename, content_type)."""
        cursor = self.get_cursor(buffered=True)
        cursor.execute("DELETE FROM mercatino_attachments WHERE thread_id = %s", (thread_id,))
        if attachments:
            cursor.executemany(
                "INSERT INTO mercatino_attachments (thread_id, position, url, filename, content_type) "
                "VALUES (%s, %s, %s, %s, %s)",
                [(thread_id, i, a["url"], a["filename"], a["content_type"])
                 for i, a in enumerate(attachments)]
            )
        self.conn.commit()
        cursor.close()

    def deactivate_post(self, thread_id):
        self._execute("UPDATE mercatino_posts SET active = 0 WHERE thread_id = %s", (thread_id,))

    # ------------------------------------------------------------------
    # LETTURA (restituiscono dict, riusabili da un'API web)
    # ------------------------------------------------------------------
    def get_post(self, thread_id):
        rows = self._query("SELECT * FROM mercatino_posts WHERE thread_id = %s", (thread_id,))
        return rows[0] if rows else None

    def get_posts(self, guild_id, author_id=None, active_only=True, limit=50, offset=0):
        sql = "SELECT * FROM mercatino_posts WHERE guild_id = %s"
        params = [guild_id]
        if active_only:
            sql += " AND active = 1"
        if author_id:
            sql += " AND author_id = %s"
            params.append(author_id)
        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params += [limit, offset]
        return self._query(sql, tuple(params))

    def get_attachments(self, thread_id):
        return self._query("""
            SELECT url, filename, content_type FROM mercatino_attachments
            WHERE thread_id = %s ORDER BY position
        """, (thread_id,))

    def get_active_ids(self, guild_id):
        rows = self._query("SELECT thread_id FROM mercatino_posts WHERE guild_id = %s AND active = 1",
                           (guild_id,))
        return {r["thread_id"] for r in rows}
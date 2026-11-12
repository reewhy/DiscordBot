from datetime import datetime, timedelta, timezone
from decimal import Decimal

from utils.database import BaseDatabase


def utcnow() -> datetime:
    """Datetime UTC 'naive' (come lo vuole MySQL DATETIME)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class BoardSystem(BaseDatabase):
    def __init__(self, host, user, password, database):
        super().__init__(host, user, password, database)
        self.create_table()
        self.create_stats_tables()

    # ------------------------------------------------------------------
    # SCHEMA
    # ------------------------------------------------------------------
    def create_table(self):
        cursor = self.get_cursor()
        # Tabella "legacy": contatore reazioni + id del messaggio nella board
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS board (
                message_id BIGINT,
                reactions  INT,
                boarded    BIGINT,
                author_id  BIGINT,
                PRIMARY KEY (message_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS board_config (
                guild_id      BIGINT,
                channel_id    BIGINT,
                min_reactions INT DEFAULT 1,
                PRIMARY KEY (guild_id)
            )
        """)
        cursor.close()

    def create_stats_tables(self):
        cursor = self.get_cursor()

        # Snapshot di ogni messaggio finito nella Hall of Shame.
        # Contiene TUTTO quello che serve per mostrarlo/statisticarlo
        # senza dover più fare fetch_message su Discord (e senza bot, per l'API web).
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS board_posts (
                message_id         BIGINT NOT NULL,           -- messaggio originale
                guild_id           BIGINT NOT NULL,
                channel_id         BIGINT NOT NULL,           -- canale originale
                author_id          BIGINT NULL,
                author_name        VARCHAR(100) NULL,
                author_avatar      VARCHAR(512) NULL,
                content            MEDIUMTEXT NULL,
                image_url          VARCHAR(1024) NULL,
                attachments        INT NOT NULL DEFAULT 0,
                jump_url           VARCHAR(255) NULL,
                board_channel_id   BIGINT NULL,
                board_message_id   BIGINT NULL,               -- messaggio nel canale board
                stars              INT NOT NULL DEFAULT 0,    -- stelle attuali
                peak_stars         INT NOT NULL DEFAULT 0,    -- massimo storico
                active             TINYINT(1) NOT NULL DEFAULT 1,  -- 0 = tolto dalla board
                message_created_at DATETIME NULL,
                boarded_at         DATETIME NULL,
                updated_at         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                                   ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (message_id),
                KEY idx_author (guild_id, author_id),
                KEY idx_stars (guild_id, active, stars),
                KEY idx_board_msg (board_message_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Chi ha messo la stella a cosa (idempotente: una riga per utente/messaggio)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS board_stars (
                message_id BIGINT NOT NULL,
                user_id    BIGINT NOT NULL,
                starred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (message_id, user_id),
                KEY idx_user (user_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        cursor.close()

    # ------------------------------------------------------------------
    # HELPER
    # ------------------------------------------------------------------
    def _query(self, sql, params=()):
        """SELECT -> lista di dict (Decimal convertiti in int: pronti per JSON)."""
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
    # CONFIG BOARD
    # ------------------------------------------------------------------
    def set_board_channel(self, guild_id, channel_id):
        self._execute("""
            INSERT INTO board_config (guild_id, channel_id, min_reactions)
            VALUES (%s, %s, 1)
            ON DUPLICATE KEY UPDATE channel_id = VALUES(channel_id)
        """, (guild_id, channel_id))

    def get_board_channel(self, guild_id):
        rows = self._query("SELECT channel_id FROM board_config WHERE guild_id = %s", (guild_id,))
        return rows[0]["channel_id"] if rows else None

    def set_min_reactions(self, guild_id, num):
        self._execute("""
            INSERT INTO board_config (guild_id, min_reactions)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE min_reactions = VALUES(min_reactions)
        """, (guild_id, num))

    def get_min_reactions(self, guild_id):
        rows = self._query("SELECT min_reactions FROM board_config WHERE guild_id = %s", (guild_id,))
        return rows[0]["min_reactions"] if rows else 1

    # ------------------------------------------------------------------
    # TABELLA LEGACY `board` (invariata, il resto del bot continua a usarla)
    # ------------------------------------------------------------------
    def add_reaction(self, message_id):
        self._execute("""
            INSERT INTO board (message_id, reactions) VALUES (%s, 1)
            ON DUPLICATE KEY UPDATE reactions = reactions + 1
        """, (message_id,))

    def remove_reaction(self, message_id):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT reactions FROM board WHERE message_id = %s", (message_id,))
        result = cursor.fetchone()
        if not result:
            cursor.close()
            return
        if result[0] > 1:
            cursor.execute("UPDATE board SET reactions = reactions - 1 WHERE message_id = %s", (message_id,))
        else:
            cursor.execute("DELETE FROM board WHERE message_id = %s", (message_id,))
        self.conn.commit()
        cursor.close()

    def add_boarded(self, message_id, board_index, author_id):
        self._execute("UPDATE board SET boarded = %s, author_id = %s WHERE message_id = %s",
                      (board_index, author_id, message_id))

    def get_boarded(self, message_id):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT boarded FROM board WHERE message_id = %s", (message_id,))
        result = cursor.fetchone()
        cursor.close()
        return result if result else 0

    def remove_boarded(self, message_id):
        self._execute("UPDATE board SET boarded = 0 WHERE message_id = %s", (message_id,))

    def get_reactions(self, message_id):
        cursor = self.get_cursor(buffered=True)
        cursor.execute("SELECT reactions FROM board WHERE message_id = %s", (message_id,))
        result = cursor.fetchone()
        cursor.close()
        return result

    def get_legacy_row(self, message_id):
        rows = self._query("SELECT reactions, boarded, author_id FROM board WHERE message_id = %s",
                           (message_id,))
        return rows[0] if rows else None

    def sync_legacy_board(self, message_id, reactions, boarded, author_id):
        """Allinea la tabella legacy (usata dai contatori) ai dati reali."""
        self._execute("""
            INSERT INTO board (message_id, reactions, boarded, author_id)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE reactions = VALUES(reactions),
                                    boarded   = VALUES(boarded),
                                    author_id = VALUES(author_id)
        """, (message_id, reactions, boarded, author_id))

    # ------------------------------------------------------------------
    # SCRITTURA STATISTICHE
    # ------------------------------------------------------------------
    def upsert_post(self, data: dict):
        """Crea/aggiorna lo snapshot di un post. `data` usa i nomi colonna di board_posts."""
        cols = list(data)
        placeholders = ", ".join(["%s"] * len(cols))
        updates = ", ".join(f"{c} = VALUES({c})" for c in cols if c != "message_id")
        sql = (
            f"INSERT INTO board_posts ({', '.join(cols)}, peak_stars, active) "
            f"VALUES ({placeholders}, %s, 1) "
            f"ON DUPLICATE KEY UPDATE {updates}, "
            f"peak_stars = GREATEST(peak_stars, VALUES(peak_stars)), active = 1"
        )
        self._execute(sql, tuple(data.values()) + (data.get("stars", 0),))

    def set_post_stars(self, message_id, stars):
        """Aggiorna le stelle (no-op se il post non è nella board)."""
        self._execute("""
            UPDATE board_posts
            SET stars = %s, peak_stars = GREATEST(peak_stars, %s)
            WHERE message_id = %s
        """, (stars, stars, message_id))

    def deactivate_post(self, message_id):
        self._execute("UPDATE board_posts SET active = 0 WHERE message_id = %s", (message_id,))

    def deactivate_by_board_message(self, board_message_id):
        self._execute("UPDATE board_posts SET active = 0 WHERE board_message_id = %s", (board_message_id,))

    def add_star_user(self, message_id, user_id):
        self._execute("INSERT IGNORE INTO board_stars (message_id, user_id, starred_at) VALUES (%s, %s, %s)",
                      (message_id, user_id, utcnow()))

    def remove_star_user(self, message_id, user_id):
        self._execute("DELETE FROM board_stars WHERE message_id = %s AND user_id = %s", (message_id, user_id))

    def replace_stars(self, message_id, user_ids):
        """Sostituisce l'elenco di chi ha messo la stella (usato dal sync)."""
        cursor = self.get_cursor(buffered=True)
        cursor.execute("DELETE FROM board_stars WHERE message_id = %s", (message_id,))
        if user_ids:
            now = utcnow()
            cursor.executemany(
                "INSERT IGNORE INTO board_stars (message_id, user_id, starred_at) VALUES (%s, %s, %s)",
                [(message_id, uid, now) for uid in user_ids]
            )
        self.conn.commit()
        cursor.close()

    # ------------------------------------------------------------------
    # LETTURA STATISTICHE (riusabili dall'API web: restituiscono dict)
    # ------------------------------------------------------------------
    def get_post(self, message_id):
        rows = self._query("SELECT * FROM board_posts WHERE message_id = %s", (message_id,))
        return rows[0] if rows else None

    def get_top_posts(self, guild_id, limit=10):
        return self._query("""
            SELECT * FROM board_posts
            WHERE guild_id = %s AND active = 1
            ORDER BY stars DESC, boarded_at ASC
            LIMIT %s
        """, (guild_id, limit))

    def get_user_posts(self, guild_id, author_id):
        return self._query("""
            SELECT * FROM board_posts
            WHERE guild_id = %s AND author_id = %s AND active = 1
            ORDER BY stars DESC, boarded_at ASC
        """, (guild_id, author_id))

    def get_author_ranking(self, guild_id, limit=None):
        sql = """
            SELECT author_id,
                   MAX(author_name) AS author_name,
                   SUM(stars)       AS total_stars,
                   COUNT(*)         AS total_posts
            FROM board_posts
            WHERE guild_id = %s AND active = 1 AND author_id IS NOT NULL
            GROUP BY author_id
            ORDER BY total_stars DESC, total_posts ASC
        """
        params = [guild_id]
        if limit:
            sql += " LIMIT %s"
            params.append(limit)
        return self._query(sql, tuple(params))

    def get_guild_stats(self, guild_id):
        week_ago = utcnow() - timedelta(days=7)
        rows = self._query("""
            SELECT COUNT(*)                          AS total_posts,
                   COALESCE(SUM(stars), 0)           AS total_stars,
                   COALESCE(MAX(stars), 0)           AS max_stars,
                   COUNT(DISTINCT author_id)         AS unique_authors,
                   COALESCE(SUM(boarded_at >= %s), 0) AS posts_last_7d
            FROM board_posts
            WHERE guild_id = %s AND active = 1
        """, (week_ago, guild_id))
        return rows[0]

    def get_top_givers(self, guild_id, limit=5):
        return self._query("""
            SELECT s.user_id, COUNT(*) AS stars_given
            FROM board_stars s
            JOIN board_posts p ON p.message_id = s.message_id
            WHERE p.guild_id = %s AND p.active = 1
            GROUP BY s.user_id
            ORDER BY stars_given DESC
            LIMIT %s
        """, (guild_id, limit))

    def get_active_board_ids(self, guild_id):
        """[(message_id, board_message_id)] dei post attivi, per il sync."""
        rows = self._query("SELECT message_id, board_message_id FROM board_posts "
                           "WHERE guild_id = %s AND active = 1", (guild_id,))
        return [(r["message_id"], r["board_message_id"]) for r in rows]
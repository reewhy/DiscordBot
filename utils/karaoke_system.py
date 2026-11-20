from decimal import Decimal

from utils.database import BaseDatabase


class KaraokeSystem(BaseDatabase):
    def __init__(self, host, user, password, database):
        super().__init__(host, user, password, database)
        self.create_tables()

    # ------------------------------------------------------------------
    # SCHEMA
    # ------------------------------------------------------------------
    def create_tables(self):
        cursor = self.get_cursor()
        # Una riga per ogni brano andato in scena.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS karaoke_plays (
                id            BIGINT NOT NULL AUTO_INCREMENT,
                guild_id      BIGINT NOT NULL,
                channel_id    BIGINT NULL,
                video_id      VARCHAR(16) NOT NULL,
                title         VARCHAR(150) NOT NULL,
                channel_title VARCHAR(100) NULL,
                singer_id     BIGINT NOT NULL,
                singer_name   VARCHAR(100) NULL,
                played_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                KEY idx_guild_time (guild_id, played_at),
                KEY idx_singer (guild_id, singer_id),
                KEY idx_video (guild_id, video_id)
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
    def record_play(self, guild_id, channel_id, video_id, title, channel_title, singer_id, singer_name):
        self._execute(
            "INSERT INTO karaoke_plays "
            "(guild_id, channel_id, video_id, title, channel_title, singer_id, singer_name) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (guild_id, channel_id, video_id, title[:150], (channel_title or "")[:100],
             singer_id, (singer_name or "")[:100]),
        )

    # ------------------------------------------------------------------
    # LETTURA
    # ------------------------------------------------------------------
    def top_songs(self, guild_id, limit=10):
        return self._query("""
            SELECT video_id, MAX(title) AS title, COUNT(*) AS plays
            FROM karaoke_plays
            WHERE guild_id = %s
            GROUP BY video_id
            ORDER BY plays DESC, MAX(played_at) DESC
            LIMIT %s
        """, (guild_id, limit))

    def top_singers(self, guild_id, limit=10):
        return self._query("""
            SELECT singer_id, MAX(singer_name) AS singer_name, COUNT(*) AS plays
            FROM karaoke_plays
            WHERE guild_id = %s
            GROUP BY singer_id
            ORDER BY plays DESC, MAX(played_at) DESC
            LIMIT %s
        """, (guild_id, limit))

    def recent(self, guild_id, limit=10):
        return self._query("""
            SELECT video_id, title, singer_id, singer_name, played_at
            FROM karaoke_plays
            WHERE guild_id = %s
            ORDER BY played_at DESC
            LIMIT %s
        """, (guild_id, limit))

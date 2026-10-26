from utils.database import BaseDatabase


class UsciteSystem(BaseDatabase):
    _PROPOSTA_COLS = ("id", "guild_id", "message_id", "creator_id", "title", "event_ts", "place",
                      "description", "image_url", "has_file", "reservation", "warning", "kaomoji",
                      "status", "kind", "final_poll")
    _EDITABLE = {"title", "event_ts", "place", "description", "image_url",
                 "has_file", "reservation", "warning", "status", "final_poll"}

    def __init__(self, host, user, password, database):
        super().__init__(host, user, password, database)
        self.create_table()

    def create_table(self):
        cursor = self.get_cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS uscite (
                id INT PRIMARY KEY AUTO_INCREMENT,
                guild_id BIGINT NOT NULL,
                thread_id BIGINT NOT NULL,
                poll_message_id BIGINT NOT NULL,
                creator_id BIGINT NOT NULL,
                title VARCHAR(100) NOT NULL,
                event_ts BIGINT NOT NULL,
                reminder_ts BIGINT NOT NULL,
                sent BOOLEAN NOT NULL DEFAULT FALSE
            ) DEFAULT CHARSET=utf8mb4
        """)

        # Migrazioni per tabelle già esistenti
        for col in (
            "final_poll_message_id BIGINT NOT NULL DEFAULT 0",
            "list_message_id BIGINT NOT NULL DEFAULT 0",
            "final_enabled BOOLEAN NOT NULL DEFAULT TRUE",
        ):
            try:
                cursor.execute(f"ALTER TABLE uscite ADD COLUMN {col}")
            except Exception:
                pass  # colonna già presente

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposte_uscite (
                id INT PRIMARY KEY AUTO_INCREMENT,
                guild_id BIGINT NOT NULL,
                message_id BIGINT NOT NULL,
                creator_id BIGINT NOT NULL,
                title VARCHAR(100) NOT NULL,
                event_ts BIGINT NOT NULL,
                place VARCHAR(300) NOT NULL,
                description TEXT,
                image_url VARCHAR(1000) NOT NULL DEFAULT '',
                has_file BOOLEAN NOT NULL DEFAULT FALSE,
                reservation BOOLEAN NOT NULL DEFAULT FALSE,
                warning VARCHAR(200) NOT NULL DEFAULT '',
                kaomoji VARCHAR(64) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                UNIQUE KEY (message_id)
            ) DEFAULT CHARSET=utf8mb4
        """)

        try:
            cursor.execute("ALTER TABLE proposte_uscite ADD COLUMN kind VARCHAR(10) NOT NULL DEFAULT 'LIVE'")
        except Exception:
            pass  # colonna già presente

        try:
            cursor.execute("ALTER TABLE proposte_uscite ADD COLUMN final_poll BOOLEAN NOT NULL DEFAULT TRUE")
        except Exception:
            pass  # colonna già presente

        self.conn.commit()
        cursor.close()

    def drop_tables(self):
        cursor = self.get_cursor()
        cursor.execute("DROP TABLE IF EXISTS uscite")
        cursor.execute("DROP TABLE IF EXISTS proposte_uscite")
        self.conn.commit()
        cursor.close()

    # --- USCITE PUBBLICATE ---
    def add_uscita(self, guild_id, thread_id, poll_message_id, creator_id, title, event_ts, reminder_ts,
                   sent=False, final_poll_message_id=0, list_message_id=0, final_enabled=True):
        cursor = self.get_cursor()
        cursor.execute(
            """
            INSERT INTO uscite (guild_id, thread_id, poll_message_id, creator_id, title, event_ts,
                                reminder_ts, sent, final_poll_message_id, list_message_id, final_enabled)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (guild_id, thread_id, poll_message_id, creator_id, title, event_ts,
             reminder_ts, sent, final_poll_message_id, list_message_id, final_enabled),
        )
        self.conn.commit()
        cursor.close()

    def get_due(self, now_ts: int):
        """Uscite con conferma attiva il cui sondaggio deve ancora partire e il cui orario è già passato."""
        cursor = self.get_cursor()
        cursor.execute(
            """
            SELECT id, guild_id, thread_id, poll_message_id, title, event_ts
            FROM uscite
            WHERE sent = FALSE AND final_enabled = TRUE AND reminder_ts <= %s
            """,
            (now_ts,),
        )
        results = cursor.fetchall()
        cursor.close()
        return results

    def mark_sent(self, uscita_id: int):
        cursor = self.get_cursor()
        cursor.execute("UPDATE uscite SET sent = TRUE WHERE id = %s", (uscita_id,))
        self.conn.commit()
        cursor.close()

    def get_by_thread(self, thread_id: int):
        """(id, poll_message_id, event_ts, sent) per il thread indicato, o None."""
        cursor = self.get_cursor()
        cursor.execute(
            "SELECT id, poll_message_id, event_ts, sent FROM uscite WHERE thread_id = %s",
            (thread_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        return row

    def is_final_enabled(self, thread_id: int) -> bool:
        """True se per questo thread è prevista la conferma (default True se il thread non esiste)."""
        cursor = self.get_cursor()
        cursor.execute("SELECT final_enabled FROM uscite WHERE thread_id = %s", (thread_id,))
        row = cursor.fetchone()
        cursor.close()
        return bool(row[0]) if row else True

    def set_final_poll(self, uscita_id: int, message_id: int):
        cursor = self.get_cursor()
        cursor.execute("UPDATE uscite SET final_poll_message_id = %s WHERE id = %s", (message_id, uscita_id))
        self.conn.commit()
        cursor.close()

    def set_list_message(self, uscita_id: int, message_id: int):
        cursor = self.get_cursor()
        cursor.execute("UPDATE uscite SET list_message_id = %s WHERE id = %s", (message_id, uscita_id))
        self.conn.commit()
        cursor.close()

    def get_by_poll_message(self, message_id: int):
        """(id, thread_id, poll_message_id, final_poll_message_id, list_message_id, title) o None."""
        cursor = self.get_cursor()
        cursor.execute(
            """
            SELECT id, thread_id, poll_message_id, final_poll_message_id, list_message_id, title
            FROM uscite
            WHERE poll_message_id = %s OR final_poll_message_id = %s
            """,
            (message_id, message_id),
        )
        row = cursor.fetchone()
        cursor.close()
        return row

    # --- PROPOSTE ---
    def add_proposta(self, guild_id, message_id, creator_id, title, event_ts, place, description,
                     image_url, has_file, reservation, warning, kaomoji, kind="LIVE", final_poll=True):
        cursor = self.get_cursor()
        cursor.execute(
            """
            INSERT INTO proposte_uscite (guild_id, message_id, creator_id, title, event_ts, place,
                                         description, image_url, has_file, reservation, warning, kaomoji,
                                         kind, final_poll)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (guild_id, message_id, creator_id, title, event_ts, place, description,
             image_url, has_file, reservation, warning, kaomoji, kind, final_poll),
        )
        self.conn.commit()
        cursor.close()

    def get_proposta(self, message_id: int):
        cursor = self.get_cursor()
        cursor.execute(
            f"SELECT {', '.join(self._PROPOSTA_COLS)} FROM proposte_uscite WHERE message_id = %s",
            (message_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        if not row:
            return None
        p = dict(zip(self._PROPOSTA_COLS, row))
        for k in ("has_file", "reservation", "final_poll"):
            p[k] = bool(p[k])
        p["description"] = p["description"] or ""
        return p

    def update_proposta(self, proposta_id: int, **fields):
        fields = {k: v for k, v in fields.items() if k in self._EDITABLE}
        if not fields:
            return
        sets = ", ".join(f"{k} = %s" for k in fields)
        cursor = self.get_cursor()
        cursor.execute(f"UPDATE proposte_uscite SET {sets} WHERE id = %s", (*fields.values(), proposta_id))
        self.conn.commit()
        cursor.close()
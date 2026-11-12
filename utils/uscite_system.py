from utils.database import BaseDatabase


class UsciteSystem(BaseDatabase):
    _PROPOSTA_COLS = ("id", "guild_id", "message_id", "creator_id", "title", "event_ts", "place",
                      "description", "image_url", "has_file", "reservation", "warning", "kaomoji",
                      "status", "kind", "final_poll")
    _EDITABLE = {"title", "event_ts", "place", "description", "image_url",
                 "has_file", "reservation", "warning", "status", "final_poll"}

    # Colonne della tabella `uscite` esposte all'API (ordine = ordine del SELECT)
    _USCITA_COLS = ("id", "guild_id", "channel_id", "thread_id", "poll_message_id",
                    "final_poll_message_id", "list_message_id", "discord_event_id",
                    "creator_id", "kind", "title", "description", "place", "image_url",
                    "reservation", "warning", "kaomoji", "event_ts", "reminder_ts",
                    "final_enabled", "sent", "created_ts")

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
            # --- dati completi dell'evento (per l'API) ---
            "kind VARCHAR(10) NOT NULL DEFAULT 'LIVE'",          # LIVE | ONLINE
            "channel_id BIGINT NOT NULL DEFAULT 0",              # canale in cui è stato pubblicato il post
            "description TEXT NULL",
            "place VARCHAR(300) NOT NULL DEFAULT ''",
            "image_url VARCHAR(1000) NOT NULL DEFAULT ''",
            "reservation BOOLEAN NOT NULL DEFAULT FALSE",
            "warning VARCHAR(200) NOT NULL DEFAULT ''",
            "kaomoji VARCHAR(64) NOT NULL DEFAULT ''",
            "discord_event_id BIGINT NOT NULL DEFAULT 0",        # evento programmato di Discord (0 = nessuno)
            "created_ts BIGINT NOT NULL DEFAULT 0",              # quando è stata pubblicata/importata
        ):
            try:
                cursor.execute(f"ALTER TABLE uscite ADD COLUMN {col}")
            except Exception:
                pass  # colonna già presente

        # Indici utili alle query dell'API (ignorati se già esistenti)
        for idx in (
            "CREATE INDEX idx_uscite_thread ON uscite (thread_id)",
            "CREATE INDEX idx_uscite_event_ts ON uscite (event_ts)",
        ):
            try:
                cursor.execute(idx)
            except Exception:
                pass

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
                   sent=False, final_poll_message_id=0, list_message_id=0, final_enabled=True,
                   kind="LIVE", channel_id=0, description="", place="", image_url="",
                   reservation=False, warning="", kaomoji="", discord_event_id=0, created_ts=0):
        cursor = self.get_cursor()
        cursor.execute(
            """
            INSERT INTO uscite (guild_id, thread_id, poll_message_id, creator_id, title, event_ts,
                                reminder_ts, sent, final_poll_message_id, list_message_id, final_enabled,
                                kind, channel_id, description, place, image_url, reservation, warning,
                                kaomoji, discord_event_id, created_ts)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (guild_id, thread_id, poll_message_id, creator_id, title, event_ts,
             reminder_ts, sent, final_poll_message_id, list_message_id, final_enabled,
             kind, channel_id, description, place, image_url, reservation, warning,
             kaomoji, discord_event_id, created_ts),
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

    # --- LETTURE PER L'API ---
    def _uscita_row_to_dict(self, row) -> dict:
        u = dict(zip(self._USCITA_COLS, row))
        for k in ("reservation", "final_enabled", "sent"):
            u[k] = bool(u[k])
        u["description"] = u["description"] or ""
        return u

    def get_uscita_full(self, thread_id: int):
        """Tutti i dati dell'uscita (dict) o None."""
        cursor = self.get_cursor()
        cursor.execute(
            f"SELECT {', '.join(self._USCITA_COLS)} FROM uscite WHERE thread_id = %s",
            (thread_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        return self._uscita_row_to_dict(row) if row else None

    def list_uscite(self, guild_id=None, kind=None, from_ts=None, to_ts=None, limit=100, offset=0):
        """Elenco filtrabile, ordinato per data dell'evento (più recenti prima)."""
        where, params = [], []
        if guild_id is not None:
            where.append("guild_id = %s")
            params.append(guild_id)
        if kind:
            where.append("kind = %s")
            params.append(kind)
        if from_ts is not None:
            where.append("event_ts >= %s")
            params.append(from_ts)
        if to_ts is not None:
            where.append("event_ts <= %s")
            params.append(to_ts)
        clause = f"WHERE {' AND '.join(where)}" if where else ""

        cursor = self.get_cursor()
        cursor.execute(
            f"SELECT {', '.join(self._USCITA_COLS)} FROM uscite {clause} "
            "ORDER BY event_ts DESC LIMIT %s OFFSET %s",
            (*params, limit, offset),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [self._uscita_row_to_dict(r) for r in rows]

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
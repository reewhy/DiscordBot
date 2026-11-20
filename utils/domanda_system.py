from datetime import datetime, timezone

from utils.database import BaseDatabase


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DomandaSystem(BaseDatabase):
    """
    Stati di una domanda:  pending -> approved -> used   (oppure pending -> rejected)
    Stati di una settimana: open -> closed
    """

    def __init__(self, host, user, password, database):
        super().__init__(host, user, password, database)
        self.create_table()

    # ------------------------------------------------------------------
    # Helper interno: esegue una query, fa commit (così ogni lettura vede
    # dati freschi) e restituisce il risultato nel formato richiesto.
    # ------------------------------------------------------------------
    def _run(self, query, params=(), fetch=None):
        cursor = self.get_cursor(buffered=True)
        try:
            cursor.execute(query, params)
            if fetch == "one":
                row = cursor.fetchone()
                result = dict(zip(cursor.column_names, row)) if row else None
            elif fetch == "all":
                result = [dict(zip(cursor.column_names, r)) for r in cursor.fetchall()]
            elif fetch == "rowcount":
                result = cursor.rowcount
            else:  # "id"
                result = cursor.lastrowid
            self.conn.commit()
            return result
        finally:
            cursor.close()

    def create_table(self):
        cursor = self.get_cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS domanda_questions(
                id INT AUTO_INCREMENT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                author_id BIGINT NOT NULL,
                text VARCHAR(200) NOT NULL,
                status VARCHAR(10) NOT NULL DEFAULT 'pending',
                staff_message_id BIGINT NULL,
                created_at DATETIME NOT NULL,
                INDEX idx_guild_status (guild_id, status),
                INDEX idx_staff_msg (staff_message_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS domanda_weeks(
                id INT AUTO_INCREMENT PRIMARY KEY,
                guild_id BIGINT NOT NULL,
                week_key VARCHAR(32) NOT NULL,
                question_id INT NULL,
                question_text VARCHAR(200) NOT NULL,
                author_id BIGINT NULL,
                channel_id BIGINT NOT NULL,
                message_id BIGINT NULL,
                starts_at DATETIME NOT NULL,
                ends_at DATETIME NOT NULL,
                status VARCHAR(10) NOT NULL DEFAULT 'open',
                UNIQUE KEY uq_guild_week (guild_id, week_key),
                INDEX idx_message (message_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS domanda_votes(
                week_id INT NOT NULL,
                voter_id BIGINT NOT NULL,
                target_id BIGINT NOT NULL,
                PRIMARY KEY(week_id, voter_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS domanda_winners(
                week_id INT NOT NULL,
                user_id BIGINT NOT NULL,
                votes INT NOT NULL,
                PRIMARY KEY(week_id, user_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS domanda_settings(
                guild_id BIGINT PRIMARY KEY,
                winner_role_id BIGINT NULL
            )
        """)
        # Per chi ha già creato la tabella con la vecchia lunghezza (VARCHAR(10))
        cursor.execute("ALTER TABLE domanda_weeks MODIFY week_key VARCHAR(32) NOT NULL")
        self.conn.commit()
        cursor.close()

    # ------------------------------------------------------------------
    # Canali (letti dalla tabella `channels` già usata da ServerSystem)
    # ------------------------------------------------------------------
    def get_channel(self, guild_id, kind):
        row = self._run(
            "SELECT channel_id FROM channels WHERE guild_id = %s AND description = %s",
            (guild_id, kind), fetch="one")
        return int(row["channel_id"]) if row else None

    # ------------------------------------------------------------------
    # Ruolo vincitore
    # ------------------------------------------------------------------
    def set_winner_role(self, guild_id, role_id):
        self._run("""
            INSERT INTO domanda_settings (guild_id, winner_role_id) VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE winner_role_id = VALUES(winner_role_id)
        """, (guild_id, role_id))

    def get_winner_role(self, guild_id):
        row = self._run("SELECT winner_role_id FROM domanda_settings WHERE guild_id = %s",
                        (guild_id,), fetch="one")
        return int(row["winner_role_id"]) if row and row["winner_role_id"] else None

    # ------------------------------------------------------------------
    # Domande proposte
    # ------------------------------------------------------------------
    def add_question(self, guild_id, author_id, text):
        return self._run("""
            INSERT INTO domanda_questions (guild_id, author_id, text, status, created_at)
            VALUES (%s, %s, %s, 'pending', %s)
        """, (guild_id, author_id, text, utcnow()))

    def set_question_staff_message(self, question_id, message_id):
        self._run("UPDATE domanda_questions SET staff_message_id = %s WHERE id = %s",
                  (message_id, question_id))

    def delete_question(self, question_id):
        self._run("DELETE FROM domanda_questions WHERE id = %s", (question_id,))

    def get_question_by_staff_message(self, message_id):
        return self._run("SELECT * FROM domanda_questions WHERE staff_message_id = %s",
                         (message_id,), fetch="one")

    def resolve_pending_question(self, question_id, new_status):
        """Cambia stato solo se è ancora 'pending'. True se ce l'ha fatta (evita doppi click)."""
        return self._run(
            "UPDATE domanda_questions SET status = %s WHERE id = %s AND status = 'pending'",
            (new_status, question_id), fetch="rowcount") > 0

    def mark_question_used(self, question_id):
        self._run("UPDATE domanda_questions SET status = 'used' WHERE id = %s", (question_id,))

    def count_pending_by_author(self, guild_id, author_id):
        row = self._run("""
            SELECT COUNT(*) AS c FROM domanda_questions
            WHERE guild_id = %s AND author_id = %s AND status = 'pending'
        """, (guild_id, author_id), fetch="one")
        return int(row["c"])

    def count_by_status(self, guild_id):
        rows = self._run("""
            SELECT status, COUNT(*) AS c FROM domanda_questions
            WHERE guild_id = %s GROUP BY status
        """, (guild_id,), fetch="all")
        return {r["status"]: int(r["c"]) for r in rows}

    def next_approved_question(self, guild_id):
        """
        La più vecchia domanda approvata e non ancora usata.
        Le domande dei membri hanno la precedenza su quelle di default (author_id = 0).
        """
        return self._run("""
            SELECT * FROM domanda_questions
            WHERE guild_id = %s AND status = 'approved'
            ORDER BY (author_id = 0) ASC, id ASC LIMIT 1
        """, (guild_id,), fetch="one")

    def question_exists(self, guild_id, text):
        row = self._run(
            "SELECT id FROM domanda_questions WHERE guild_id = %s AND text = %s LIMIT 1",
            (guild_id, text), fetch="one")
        return row is not None

    def add_approved_question(self, guild_id, author_id, text):
        """Inserisce direttamente una domanda già approvata (usata per le domande di default)."""
        return self._run("""
            INSERT INTO domanda_questions (guild_id, author_id, text, status, created_at)
            VALUES (%s, %s, %s, 'approved', %s)
        """, (guild_id, author_id, text, utcnow()))

    # ------------------------------------------------------------------
    # Settimane
    # ------------------------------------------------------------------
    def create_week(self, guild_id, week_key, question_id, question_text,
                    author_id, channel_id, starts_at, ends_at):
        """Ritorna l'id della settimana, o None se esiste già una domanda per quella settimana."""
        cursor = self.get_cursor(buffered=True)
        try:
            cursor.execute("""
                INSERT IGNORE INTO domanda_weeks
                    (guild_id, week_key, question_id, question_text, author_id,
                     channel_id, starts_at, ends_at, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'open')
            """, (guild_id, week_key, question_id, question_text, author_id,
                  channel_id, starts_at, ends_at))
            inserted = cursor.rowcount > 0
            week_id = cursor.lastrowid
            self.conn.commit()
            return week_id if inserted else None
        finally:
            cursor.close()

    def week_exists(self, guild_id, key_prefix):
        """True se esiste già una settimana (anche chiusa, anche forzata) con questa chiave ISO."""
        row = self._run(
            "SELECT id FROM domanda_weeks WHERE guild_id = %s AND week_key LIKE %s LIMIT 1",
            (guild_id, key_prefix + "%"), fetch="one")
        return row is not None

    def set_week_message(self, week_id, message_id):
        self._run("UPDATE domanda_weeks SET message_id = %s WHERE id = %s", (message_id, week_id))

    def delete_week(self, week_id):
        self._run("DELETE FROM domanda_weeks WHERE id = %s", (week_id,))

    def close_week(self, week_id):
        self._run("UPDATE domanda_weeks SET status = 'closed' WHERE id = %s", (week_id,))

    def get_open_week(self, guild_id):
        return self._run("""
            SELECT * FROM domanda_weeks
            WHERE guild_id = %s AND status = 'open'
            ORDER BY id DESC LIMIT 1
        """, (guild_id,), fetch="one")

    def get_week_by_message(self, message_id):
        return self._run("SELECT * FROM domanda_weeks WHERE message_id = %s",
                         (message_id,), fetch="one")

    # ------------------------------------------------------------------
    # Voti e vincitori
    # ------------------------------------------------------------------
    def upsert_vote(self, week_id, voter_id, target_id):
        self._run("""
            INSERT INTO domanda_votes (week_id, voter_id, target_id) VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE target_id = VALUES(target_id)
        """, (week_id, voter_id, target_id))

    def get_results(self, week_id):
        """Lista di (target_id, voti) ordinata dal più votato."""
        rows = self._run("""
            SELECT target_id, COUNT(*) AS votes FROM domanda_votes
            WHERE week_id = %s GROUP BY target_id
            ORDER BY votes DESC, target_id ASC
        """, (week_id,), fetch="all")
        return [(int(r["target_id"]), int(r["votes"])) for r in rows]

    def add_winners(self, week_id, winners):
        for user_id, votes in winners:
            self._run("""
                INSERT INTO domanda_winners (week_id, user_id, votes) VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE votes = VALUES(votes)
            """, (week_id, user_id, votes))
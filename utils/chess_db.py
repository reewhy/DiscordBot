from utils.database import BaseDatabase


class ChessSystem(BaseDatabase):
    def __init__(self, host, user, password, database):
        super().__init__(host, user, password, database)
        self.create_table()

    def create_table(self):
        cursor = self.get_cursor()

        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS players
                       (
                           user_id
                           BIGINT,
                           score
                           DOUBLE
                           DEFAULT
                           0,
                           PRIMARY
                           KEY
                       (
                           user_id
                       )
                           )
                       """)

        # Added status (PENDING, STARTED, FINISHED, CANCELLED)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS matches
                       (
                           match_id
                           BIGINT
                           PRIMARY
                           KEY
                           AUTO_INCREMENT,
                           winner
                           BIGINT
                           DEFAULT
                           NULL,
                           status
                           VARCHAR
                       (
                           20
                       ) DEFAULT 'PENDING',
                           FOREIGN KEY
                       (
                           winner
                       ) REFERENCES players
                       (
                           user_id
                       )
                           )
                       """)

        # Changed reported_winner to reported_result (WIN, LOSS, DRAW)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS players_matches
                       (
                           match_id
                           BIGINT,
                           player
                           BIGINT,
                           confirmed
                           BOOLEAN
                           DEFAULT
                           FALSE,
                           reported_result
                           VARCHAR
                       (
                           10
                       ) DEFAULT NULL,
                           PRIMARY KEY
                       (
                           match_id,
                           player
                       ),
                           FOREIGN KEY
                       (
                           match_id
                       ) REFERENCES matches
                       (
                           match_id
                       ) ON DELETE CASCADE,
                           FOREIGN KEY
                       (
                           player
                       ) REFERENCES players
                       (
                           user_id
                       )
                         ON DELETE CASCADE
                           )
                       """)
        self.conn.commit()
        cursor.close()

    def drop_tables(self):
        cursor = self.get_cursor()

        cursor.execute("DROP TABLE IF EXISTS players_matches")
        cursor.execute("DROP TABLE IF EXISTS players")
        cursor.execute("DROP TABLE IF EXISTS matches")

        self.conn.commit()
        cursor.close()

    def get_all_players(self):
        cursor = self.get_cursor()
        cursor.execute("SELECT user_id FROM players")
        results = cursor.fetchall()
        cursor.close()
        return [row[0] for row in results]

    def sign_up(self, user_id):
        cursor = self.get_cursor()
        cursor.execute("INSERT IGNORE INTO players (user_id, score) VALUES (%s, 0)", (user_id,))
        self.conn.commit()
        cursor.close()

    def sign_out(self, user_id):
        cursor = self.get_cursor()
        cursor.execute("DELETE FROM players WHERE user_id = %s", (user_id,))
        self.conn.commit()
        cursor.close()

    def get_score(self, user_id):
        cursor = self.get_cursor()
        cursor.execute("SELECT score FROM players WHERE user_id = %s", (user_id,))
        result = cursor.fetchone()
        cursor.close()
        return result[0] if result else None

    def new_match(self, player1_id, player2_id):
        cursor = self.get_cursor()
        cursor.execute("INSERT INTO matches (status) VALUES ('PENDING')")
        match_id = cursor.lastrowid
        cursor.execute("""
                       INSERT INTO players_matches (match_id, player)
                       VALUES (%s, %s),
                              (%s, %s)
                       """, (match_id, player1_id, match_id, player2_id))
        self.conn.commit()
        cursor.close()
        return match_id

    def confirm_availability(self, match_id, player_id):
        """Marks a player as ready. Returns True if BOTH are now ready."""
        cursor = self.get_cursor()
        cursor.execute("""
                       UPDATE players_matches
                       SET confirmed = TRUE
                       WHERE match_id = %s
                         AND player = %s
                       """, (match_id, player_id))
        self.conn.commit()

        # Check if both are ready
        cursor.execute("SELECT confirmed FROM players_matches WHERE match_id = %s", (match_id,))
        reports = cursor.fetchall()

        both_ready = len(reports) == 2 and all(r[0] for r in reports)

        if both_ready:
            cursor.execute("UPDATE matches SET status = 'STARTED' WHERE match_id = %s", (match_id,))
            self.conn.commit()

        cursor.close()
        return both_ready

    def get_player_matches(self, user_id):
        """Recupera tutte le partite di un giocatore (sia passate che future)."""
        cursor = self.get_cursor()

        # Uniamo pm1 (il giocatore) con pm2 (l'avversario) e matches
        cursor.execute("""
                       SELECT m.match_id, m.status, pm2.player AS opponent_id, m.winner
                       FROM players_matches pm1
                                JOIN matches m ON pm1.match_id = m.match_id
                                JOIN players_matches pm2 ON m.match_id = pm2.match_id AND pm2.player != pm1.player
                       WHERE pm1.player = %s
                       ORDER BY m.match_id DESC
                       """, (user_id,))

        results = cursor.fetchall()
        cursor.close()

        matches = {"active": [], "past": []}

        for row in results:
            match_id, status, opponent_id, winner_id = row
            match_info = {
                "match_id": match_id,
                "opponent_id": opponent_id,
                "status": status,
                "winner_id": winner_id
            }

            # Se la partita è da giocare o in corso
            if status in ['PENDING', 'STARTED']:
                matches["active"].append(match_info)
            # Se la partita è finita o annullata
            else:
                matches["past"].append(match_info)

        return matches

    def report_result(self, match_id, player_id, result):
        """Player reports 'WIN', 'LOSS', or 'DRAW'."""
        cursor = self.get_cursor()
        cursor.execute("""
                       UPDATE players_matches
                       SET reported_result = %s
                       WHERE match_id = %s
                         AND player = %s
                       """, (result, match_id, player_id))
        self.conn.commit()

        cursor.execute("SELECT player, reported_result FROM players_matches WHERE match_id = %s", (match_id,))
        reports = cursor.fetchall()
        cursor.close()

        # If both players haven't reported yet
        if any(r[1] is None for r in reports):
            return "PENDING"

        p1_id, p1_res = reports[0]
        p2_id, p2_res = reports[1]

        # Evaluation Logic
        if p1_res == "WIN" and p2_res == "LOSS":
            self._finalize_match(match_id, winner_id=p1_id)
            return "RESOLVED", p1_id
        elif p1_res == "LOSS" and p2_res == "WIN":
            self._finalize_match(match_id, winner_id=p2_id)
            return "RESOLVED", p2_id
        elif p1_res == "DRAW" and p2_res == "DRAW":
            self._finalize_match(match_id, is_draw=True)
            return "RESOLVED", "DRAW"
        else:
            return "DISPUTE", None

    def _finalize_match(self, match_id, winner_id=None, is_draw=False):
        cursor = self.get_cursor()
        cursor.execute("SELECT status FROM matches WHERE match_id = %s", (match_id,))
        status = cursor.fetchone()[0]

        if status != 'FINISHED':
            cursor.execute("UPDATE matches SET status = 'FINISHED', winner = %s WHERE match_id = %s",
                           (winner_id, match_id))

            # Standard Points: +1 for win. (You can add +1 to both for a draw if you prefer)
            if winner_id and not is_draw:
                # Add 1 point to the winner
                cursor.execute("UPDATE players SET score = score + 1 WHERE user_id = %s", (winner_id,))

            elif is_draw:
                # Add 0.5 points to BOTH players linked to this match
                cursor.execute("""
                               UPDATE players
                                   JOIN players_matches
                               ON players.user_id = players_matches.player
                                   SET players.score = players.score + 0.5
                               WHERE players_matches.match_id = %s
                               """, (match_id,))
            self.conn.commit()
        cursor.close()

    def force_resolve_match(self, match_id, winner_id=None, is_draw=False):
        """Staff method to forcefully resolve a match in case of a dispute."""
        cursor = self.get_cursor()

        # Check if the match exists and its current status
        cursor.execute("SELECT status FROM matches WHERE match_id = %s", (match_id,))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            return False, "Match non trovato."

        status = result[0]
        if status in ['FINISHED', 'CANCELLED']:
            cursor.close()
            return False, f"Impossibile risolvere. Il match è già {status}."

        cursor.close()

        # Call the internal method to finalize the points and update the status
        self._finalize_match(match_id, winner_id, is_draw)

        return True, "Match risolto con successo."

    def process_end_of_day_penalties(self):
        """Applies -1 penalty to players who didn't confirm PENDING matches."""
        cursor = self.get_cursor()

        # Find all matches still stuck in PENDING
        cursor.execute("SELECT match_id FROM matches WHERE status = 'PENDING'")
        pending_matches = cursor.fetchall()

        penalized_players = []

        for (match_id,) in pending_matches:
            # Find players who didn't confirm in this match
            cursor.execute("SELECT player FROM players_matches WHERE match_id = %s AND confirmed = FALSE", (match_id,))
            unconfirmed = cursor.fetchall()

            for (player_id,) in unconfirmed:
                cursor.execute("UPDATE players SET score = score - 1 WHERE user_id = %s", (player_id,))
                penalized_players.append(player_id)

            # Mark the match as cancelled so it doesn't trigger again tomorrow
            cursor.execute("UPDATE matches SET status = 'CANCELLED' WHERE match_id = %s", (match_id,))

        self.conn.commit()
        cursor.close()

        return penalized_players
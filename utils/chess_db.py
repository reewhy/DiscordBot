from utils.database import BaseDatabase


class ChessSystem(BaseDatabase):
    def __init__(self, host, user, password, database):
        super().__init__(host, user, password, database)
        self.create_table()

    def create_table(self):
        cursor = self.get_cursor()

        # Players Table (Championship Points)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS players
                       (
                           user_id
                           BIGINT
                           PRIMARY
                           KEY,
                           score
                           DOUBLE
                           DEFAULT
                           0
                       )
                       """)

        # NEW: Tournament Players Table (Tracks Single-Elimination Status)
        cursor.execute("""
                       CREATE TABLE IF NOT EXISTS tournament_players
                       (
                           user_id
                           BIGINT
                           PRIMARY
                           KEY,
                           status
                           VARCHAR
                       (
                           20
                       ) DEFAULT 'ACTIVE',
                           FOREIGN KEY
                       (
                           user_id
                       ) REFERENCES players
                       (
                           user_id
                       ) ON DELETE CASCADE
                           )
                       """)

        # MODIFIED: Added match_type and round_num
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
                           match_type VARCHAR
                       (
                           20
                       ) DEFAULT 'CHAMPIONSHIP',
                           round_num INT DEFAULT 0,
                           FOREIGN KEY
                       (
                           winner
                       ) REFERENCES players
                       (
                           user_id
                       )
                           )
                       """)

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

        # Helper: Alter existing table if match_type doesn't exist (prevents errors on old databases)
        try:
            cursor.execute("ALTER TABLE matches ADD COLUMN match_type VARCHAR(20) DEFAULT 'CHAMPIONSHIP'")
            cursor.execute("ALTER TABLE matches ADD COLUMN round_num INT DEFAULT 0")
        except:
            pass  # Columns already exist

        self.conn.commit()
        cursor.close()

    def drop_tables(self):
        cursor = self.get_cursor()
        cursor.execute("DROP TABLE IF EXISTS players_matches")
        cursor.execute("DROP TABLE IF EXISTS tournament_players")
        cursor.execute("DROP TABLE IF EXISTS players")
        cursor.execute("DROP TABLE IF EXISTS matches")
        self.conn.commit()
        cursor.close()

    # --- CHAMPIONSHIP METHODS ---
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

    # --- TOURNAMENT METHODS ---
    def tourney_sign_up(self, user_id):
        """Signs a user up for the tournament (and championship if not already in)."""
        self.sign_up(user_id)  # Ensure they exist in the main players table
        cursor = self.get_cursor()
        cursor.execute("INSERT IGNORE INTO tournament_players (user_id, status) VALUES (%s, 'ACTIVE')", (user_id,))
        self.conn.commit()
        cursor.close()

    def get_active_tourney_players(self):
        """Returns a list of all currently ACTIVE players in the tournament."""
        cursor = self.get_cursor()
        cursor.execute("SELECT user_id FROM tournament_players WHERE status = 'ACTIVE'")
        results = cursor.fetchall()
        cursor.close()
        return [row[0] for row in results]

    # --- MATCH METHODS ---
    def new_match(self, player1_id, player2_id, match_type='CHAMPIONSHIP', round_num=0):
        cursor = self.get_cursor()
        cursor.execute("INSERT INTO matches (status, match_type, round_num) VALUES ('PENDING', %s, %s)",
                       (match_type, round_num))
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
        cursor = self.get_cursor()
        cursor.execute("""
                       UPDATE players_matches
                       SET confirmed = TRUE
                       WHERE match_id = %s
                         AND player = %s
                       """, (match_id, player_id))
        self.conn.commit()

        cursor.execute("SELECT confirmed FROM players_matches WHERE match_id = %s", (match_id,))
        reports = cursor.fetchall()
        both_ready = len(reports) == 2 and all(r[0] for r in reports)

        if both_ready:
            cursor.execute("UPDATE matches SET status = 'STARTED' WHERE match_id = %s", (match_id,))
            self.conn.commit()

        cursor.close()
        return both_ready

    def get_player_matches(self, user_id):
        cursor = self.get_cursor()
        cursor.execute("""
                       SELECT m.match_id, m.status, pm2.player AS opponent_id, m.winner, m.match_type
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
            match_id, status, opponent_id, winner_id, match_type = row
            match_info = {
                "match_id": match_id,
                "opponent_id": opponent_id,
                "status": status,
                "winner_id": winner_id,
                "type": match_type
            }
            if status in ['PENDING', 'STARTED']:
                matches["active"].append(match_info)
            else:
                matches["past"].append(match_info)
        return matches

    def report_result(self, match_id, player_id, result):
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

        if any(r[1] is None for r in reports):
            return "PENDING", None

        p1_id, p1_res = reports[0]
        p2_id, p2_res = reports[1]

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
        cursor.execute("SELECT status, match_type FROM matches WHERE match_id = %s", (match_id,))
        match_data = cursor.fetchone()

        if not match_data:
            cursor.close()
            return

        status, match_type = match_data[0], match_data[1]

        if status != 'FINISHED':
            cursor.execute("UPDATE matches SET status = 'FINISHED', winner = %s WHERE match_id = %s",
                           (winner_id, match_id))

            # Logic depends on match type
            if match_type == 'CHAMPIONSHIP':
                if winner_id and not is_draw:
                    cursor.execute("UPDATE players SET score = score + 1 WHERE user_id = %s", (winner_id,))
                elif is_draw:
                    cursor.execute("""
                                   UPDATE players JOIN players_matches
                                   ON players.user_id = players_matches.player
                                       SET players.score = players.score + 0.5
                                   WHERE players_matches.match_id = %s
                                   """, (match_id,))

            elif match_type == 'TOURNAMENT':
                # In a tournament, the loser is eliminated. Draws do nothing (require staff resolution/rematch).
                if winner_id and not is_draw:
                    cursor.execute("SELECT player FROM players_matches WHERE match_id = %s AND player != %s",
                                   (match_id, winner_id))
                    loser_data = cursor.fetchone()
                    if loser_data:
                        loser_id = loser_data[0]
                        cursor.execute("UPDATE tournament_players SET status = 'ELIMINATED' WHERE user_id = %s",
                                       (loser_id,))

            self.conn.commit()
        cursor.close()

    def force_resolve_match(self, match_id, winner_id=None, is_draw=False):
        cursor = self.get_cursor()
        cursor.execute("SELECT status FROM matches WHERE match_id = %s", (match_id,))
        result = cursor.fetchone()

        if not result:
            cursor.close()
            return False, "Match non trovato."

        if result[0] in ['FINISHED', 'CANCELLED']:
            cursor.close()
            return False, f"Impossibile risolvere. Il match è già {result[0]}."

        cursor.close()
        self._finalize_match(match_id, winner_id, is_draw)
        return True, "Match risolto con successo."

    def process_end_of_day_penalties(self):
        cursor = self.get_cursor()
        cursor.execute("SELECT match_id, match_type FROM matches WHERE status = 'PENDING'")
        pending_matches = cursor.fetchall()
        penalized_players = []

        for (match_id, match_type) in pending_matches:
            cursor.execute("SELECT player FROM players_matches WHERE match_id = %s AND confirmed = FALSE", (match_id,))
            unconfirmed = cursor.fetchall()

            for (player_id,) in unconfirmed:
                if match_type == 'CHAMPIONSHIP':
                    cursor.execute("UPDATE players SET score = score - 1 WHERE user_id = %s", (player_id,))
                elif match_type == 'TOURNAMENT':
                    # Eliminate players who don't show up to tournament games
                    cursor.execute("UPDATE tournament_players SET status = 'ELIMINATED' WHERE user_id = %s",
                                   (player_id,))

                penalized_players.append(player_id)

            cursor.execute("UPDATE matches SET status = 'CANCELLED' WHERE match_id = %s", (match_id,))

        self.conn.commit()
        cursor.close()
        return penalized_players
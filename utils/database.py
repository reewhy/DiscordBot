import mysql.connector

class BaseDatabase:
    def __init__(self, host, user, password, database):
        # La connessione viene stabilita qui una volta per tutte
        self.conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )

    def __init__(self, host, user, password, database, charset, use_unicode):
        self.conn = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            charset=charset,
            use_unicode=use_unicode
        )

    def get_cursor(self, buffered=False):
        """
        Controlla se la connessione è viva prima di restituire il cursore.
        Se il DB ha chiuso la connessione, si riconnette in automatico.
        """
        self.conn.ping(reconnect=True, attempts=3, delay=2)
        return self.conn.cursor(buffered=buffered)
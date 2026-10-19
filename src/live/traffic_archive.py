"""DuckDB-backed permanent archive; place database on persistent storage."""
from pathlib import Path
import duckdb
import pandas as pd

DB_PATH = Path(__file__).resolve().parents[2] / 'data/production/canberra_traffic.duckdb'
COLUMNS = ['timestamp', 'originsiteid', 'destsiteid', 'tt', 'mintt', 'relative_delay']


def archive_snapshot(live, db_path=DB_PATH):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    incoming = live[COLUMNS].copy()
    incoming['timestamp'] = pd.to_datetime(incoming['timestamp'], utc=True)
    keys = ['timestamp', 'originsiteid', 'destsiteid']
    if incoming[keys].isna().any().any() or incoming.duplicated(keys).any():
        raise ValueError('Invalid or duplicate observation keys')
    with duckdb.connect(str(db_path)) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS traffic_observations (
            timestamp TIMESTAMPTZ NOT NULL,
            originsiteid BIGINT NOT NULL,
            destsiteid BIGINT NOT NULL,
            tt DOUBLE, mintt DOUBLE, relative_delay DOUBLE,
            PRIMARY KEY (timestamp, originsiteid, destsiteid))''')
        con.register('incoming', incoming)
        con.execute('BEGIN TRANSACTION')
        try:
            con.execute('''INSERT INTO traffic_observations BY NAME
                SELECT timestamp, originsiteid, destsiteid, tt, mintt, relative_delay
                FROM incoming
                ON CONFLICT (timestamp, originsiteid, destsiteid)
                DO UPDATE SET tt = EXCLUDED.tt, mintt = EXCLUDED.mintt,
                              relative_delay = EXCLUDED.relative_delay''')
            con.execute('COMMIT')
        except Exception:
            con.execute('ROLLBACK')
            raise
        history = con.execute('''SELECT * FROM traffic_observations
            WHERE timestamp >= (SELECT MAX(timestamp) - INTERVAL '90 minutes'
                                FROM traffic_observations)
            ORDER BY originsiteid, destsiteid, timestamp''').df()
    history['timestamp'] = pd.to_datetime(history['timestamp'], utc=True)
    return history

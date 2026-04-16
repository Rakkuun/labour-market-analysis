"""Database access: loading and querying the SQLite data store."""
import os
import re
import sqlite3
from datetime import datetime, timezone

import pandas as pd

# ── Database path ─────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data.db')


# ── Admin tables ──────────────────────────────────────────────────────────────

def init_admin_tables():
    """Create admin log tables if they don't exist yet."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS refresh_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            source       TEXT    NOT NULL,
            started_at   TEXT    NOT NULL,
            finished_at  TEXT,
            status       TEXT    NOT NULL DEFAULT 'running',
            rows_updated INTEGER,
            error_msg    TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS api_usage_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            endpoint    TEXT    NOT NULL,
            model       TEXT,
            tokens_in   INTEGER,
            tokens_out  INTEGER,
            duration_ms INTEGER
        )
    ''')
    conn.commit()
    conn.close()


def log_refresh_start(source: str) -> int:
    """Insert a 'running' row into refresh_log; returns the new row id."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO refresh_log (source, started_at, status) VALUES (?, ?, 'running')",
        (source, _now()),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def log_refresh_finish(row_id: int, status: str, rows_updated: int = None, error_msg: str = None):
    """Update an existing refresh_log row with the outcome."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'UPDATE refresh_log SET finished_at=?, status=?, rows_updated=?, error_msg=? WHERE id=?',
        (_now(), status, rows_updated, error_msg, row_id),
    )
    conn.commit()
    conn.close()


def log_api_usage(endpoint: str, model: str, tokens_in: int, tokens_out: int, duration_ms: int):
    """Append a row to api_usage_log."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'INSERT INTO api_usage_log (timestamp, endpoint, model, tokens_in, tokens_out, duration_ms) VALUES (?,?,?,?,?,?)',
        (_now(), endpoint, model, tokens_in, tokens_out, duration_ms),
    )
    conn.commit()
    conn.close()


def get_refresh_log(limit: int = 30) -> list[dict]:
    """Return the last N refresh log entries, newest first."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql(
            f'SELECT * FROM refresh_log ORDER BY id DESC LIMIT {int(limit)}', conn
        )
    except Exception:
        return []
    finally:
        conn.close()
    return df.to_dict(orient='records')


def get_api_usage_stats() -> dict:
    """Return aggregated API usage: per-day totals and an overall summary."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql('SELECT * FROM api_usage_log', conn)
    except Exception:
        return {'daily': [], 'total_calls': 0, 'total_tokens_in': 0, 'total_tokens_out': 0}
    finally:
        conn.close()

    if df.empty:
        return {'daily': [], 'total_calls': 0, 'total_tokens_in': 0, 'total_tokens_out': 0}

    df['date'] = df['timestamp'].str[:10]
    daily = (
        df.groupby('date')
        .agg(calls=('id', 'count'), tokens_in=('tokens_in', 'sum'), tokens_out=('tokens_out', 'sum'))
        .reset_index()
        .sort_values('date', ascending=False)
        .head(30)
        .to_dict(orient='records')
    )
    return {
        'daily': daily,
        'total_calls': int(df['id'].count()),
        'total_tokens_in': int(df['tokens_in'].sum()),
        'total_tokens_out': int(df['tokens_out'].sum()),
    }


def _now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def load_data_from_db():
    """Load absenteeism and prediction data from SQLite.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: (absenteeism_df, predictions_df)
    """
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql('SELECT * FROM cleaned_absenteeism', conn)
    pred_df = pd.read_sql('SELECT * FROM predictions', conn)
    conn.close()
    return df, pred_df


def extract_quarter_number(period_str):
    """Extract quarter number string from a CBS period label.

    Examples:
        "KW01"        -> "1"
        "1e kwartaal" -> "1"
        annual/blank  -> None
    """
    period = str(period_str).strip() if pd.notna(period_str) else ''
    if not period:
        return None

    kw_match = re.search(r'KW0*([1-4])', period, re.IGNORECASE)
    if kw_match:
        return kw_match.group(1)

    norm_match = re.search(r'([1-4])e kwartaal', period, re.IGNORECASE)
    if norm_match:
        return norm_match.group(1)

    return None


def build_sector_data(df):
    """Build a nested data structure of quarterly absenteeism per sector.

    Returns:
        tuple[dict, list]: (sector_data, sectors)
            sector_data: {sector: {quarters: [...], values: [...], years: [...]}}
            sectors: sorted list of sector names
    """
    sectors = sorted(df['Sector'].unique().tolist())
    sector_data = {}

    for sector in sectors:
        rows = df[df['Sector'] == sector].sort_values(['Year', 'Period'])

        quarters, years_list, values = [], [], []
        for _, row in rows.iterrows():
            year = int(row['Year'])
            period = str(row['Period']).strip() if pd.notna(row['Period']) else ''
            quarter = extract_quarter_number(period)

            if quarter is None:
                continue  # skip annual / blank rows

            quarters.append(f"{year}-Q{quarter}")
            years_list.append(year)
            values.append(row['AbsenteeismPercentage'])

        sector_data[sector] = {
            'quarters': quarters,
            'values': values,
            'years': years_list,
        }

    return sector_data, sectors


def load_flu_data():
    """Load quarterly flu positives from the flu_quarterly table.

    Returns:
        list[dict]: each dict has keys 'period', 'year', 'quarter', 'flu_positives'
        Returns empty list if table does not exist.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql(
            'SELECT year, quarter, period, flu_positives FROM flu_quarterly ORDER BY year, quarter',
            conn,
        )
    except Exception:
        return []
    finally:
        conn.close()

    return df.to_dict(orient='records')


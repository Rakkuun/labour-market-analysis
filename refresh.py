"""Data refresh pipeline: fetch → preprocess → predict.

Called by the admin panel (manual) and the nightly APScheduler job.
Every run is logged to refresh_log in data.db.
"""
import sqlite3
import traceback

from db import DB_PATH, log_refresh_start, log_refresh_finish


def run_refresh(source: str) -> dict:
    """Run a full data refresh for *source* ('cbs' or 'flu').

    Returns a dict with keys: status ('ok'/'error'), rows_updated, error_msg.
    """
    row_id = log_refresh_start(source)
    try:
        if source == 'cbs':
            rows = _refresh_cbs()
        elif source == 'flu':
            rows = _refresh_flu()
        else:
            raise ValueError(f"Onbekende databron: {source!r}")

        log_refresh_finish(row_id, status='ok', rows_updated=rows)
        return {'status': 'ok', 'rows_updated': rows, 'error_msg': None}

    except Exception as exc:
        msg = traceback.format_exc()
        log_refresh_finish(row_id, status='error', error_msg=str(exc))
        return {'status': 'error', 'rows_updated': None, 'error_msg': str(exc)}


# ── CBS ───────────────────────────────────────────────────────────────────────

def _refresh_cbs() -> int:
    """Fetch CBS data, preprocess, and regenerate predictions.

    Returns the number of cleaned rows written to cleaned_absenteeism.
    """
    # Step 1: fetch raw data from CBS OData API
    from fetch_data import fetch_absenteeism_data
    fetch_absenteeism_data()

    # Step 2: clean & normalise into cleaned_absenteeism
    from preprocess import preprocess_data
    preprocess_data()

    # Step 3: regenerate linear-regression predictions
    from predict import analyze_trends
    analyze_trends()

    # Return row count of cleaned table
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute('SELECT COUNT(*) FROM cleaned_absenteeism')
    count = cur.fetchone()[0]
    conn.close()
    return count


# ── WHO FluNet ────────────────────────────────────────────────────────────────

def _refresh_flu() -> int:
    """Fetch WHO FluNet data and store quarterly aggregates.

    Returns the number of rows in flu_quarterly after the update.
    """
    from fetch_flu_data import fetch_and_store
    fetch_and_store()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute('SELECT COUNT(*) FROM flu_quarterly')
    count = cur.fetchone()[0]
    conn.close()
    return count

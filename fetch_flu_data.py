"""Download Dutch influenza data from WHO FluNet and store quarterly aggregates in data.db.

Source: WHO FluNet (https://www.who.int/tools/flunet)
Country: Netherlands (NLD)
Metric: INF_ALL — total confirmed influenza positives per ISO week

Run this script once (or to refresh):
    python fetch_flu_data.py
"""

import sqlite3
import urllib.request
import csv
import io
import datetime


FLUNET_URL = (
    'https://xmart-api-public.who.int/FLUMART/VIW_FNT'
    '?%24format=csv&%24filter=COUNTRY_CODE%20eq%20%27NLD%27'
)
DB_PATH = 'data.db'


def _iso_week_to_quarter(year: int, week: int) -> int:
    """Return calendar quarter (1-4) for a given ISO year+week."""
    # Use Jan 4 as anchor (always in week 1) and add (week-1)*7 days
    jan4 = datetime.date(year, 1, 4)
    # Find Monday of week 1
    week1_monday = jan4 - datetime.timedelta(days=jan4.weekday())
    week_start = week1_monday + datetime.timedelta(weeks=week - 1)
    month = week_start.month
    return (month - 1) // 3 + 1


def fetch_and_store():
    print('Downloading WHO FluNet data for Netherlands…')
    with urllib.request.urlopen(FLUNET_URL, timeout=30) as response:
        content = response.read().decode('utf-8')

    rows = list(csv.DictReader(content.splitlines()))
    print(f'  Total rows: {len(rows)}')

    # Aggregate: sum INF_ALL per (year, quarter)
    quarterly: dict[tuple[int, int], dict] = {}
    skipped = 0

    for row in rows:
        inf_all = row.get('INF_ALL', '').strip()
        iso_year = row.get('ISO_YEAR', '').strip()
        iso_week = row.get('ISO_WEEK', '').strip()

        if not inf_all or not iso_year or not iso_week:
            skipped += 1
            continue

        try:
            year = int(iso_year)
            week = int(iso_week)
            flu_val = float(inf_all)
        except ValueError:
            skipped += 1
            continue

        if year < 1996 or year > 2025:
            continue

        quarter = _iso_week_to_quarter(year, week)
        key = (year, quarter)

        if key not in quarterly:
            quarterly[key] = {'flu_positives': 0.0, 'weeks': 0}
        quarterly[key]['flu_positives'] += flu_val
        quarterly[key]['weeks'] += 1

    print(f'  Skipped rows (no data): {skipped}')
    print(f'  Quarterly buckets: {len(quarterly)}')

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute('DROP TABLE IF EXISTS flu_quarterly')
    cur.execute('''
        CREATE TABLE flu_quarterly (
            year INTEGER,
            quarter INTEGER,
            period TEXT,
            flu_positives REAL,
            weeks_with_data INTEGER,
            PRIMARY KEY (year, quarter)
        )
    ''')

    for (year, quarter), data in sorted(quarterly.items()):
        period = f'{year}Q{quarter}'
        cur.execute(
            'INSERT INTO flu_quarterly VALUES (?, ?, ?, ?, ?)',
            (year, quarter, period, data['flu_positives'], data['weeks']),
        )

    conn.commit()
    conn.close()
    print(f'Stored {len(quarterly)} quarterly flu records in data.db (table: flu_quarterly)')


if __name__ == '__main__':
    fetch_and_store()

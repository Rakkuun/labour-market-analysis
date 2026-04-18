"""Clean and normalise raw CBS absenteeism data into cleaned_absenteeism."""
import logging
import sqlite3

import pandas as pd

from db import DB_PATH

logger = logging.getLogger(__name__)

_CBS_PERIOD_COL = 'Perioden'


def preprocess_data():
    """Read raw absenteeism table, normalise columns, and write cleaned_absenteeism."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql('SELECT * FROM absenteeism', conn)
    conn.close()

    # Validate expected columns exist before proceeding
    # Try known column name variants (CBS has changed names over time)
    sector_col = next(
        (c for c in df.columns if 'bedrijfstak' in c.lower() or 'bedrijfskenmerk' in c.lower()),
        None
    )
    absence_col = next(
        (c for c in df.columns if 'ziekteverzuim' in c.lower()),
        None
    )
    if not sector_col or not absence_col:
        raise ValueError(
            f'Verwachte CBS-kolommen niet gevonden. Beschikbare kolommen: {df.columns.tolist()}'
        )

    df = df.drop(columns=['ID'], errors='ignore')
    df = df.rename(columns={sector_col: 'Sector', absence_col: 'AbsenteeismPercentage'})

    df['AbsenteeismPercentage'] = pd.to_numeric(df['AbsenteeismPercentage'], errors='coerce')
    df.dropna(subset=['AbsenteeismPercentage'], inplace=True)

    df['Year'] = df[_CBS_PERIOD_COL].str[:4].astype(int)
    df['Period'] = df[_CBS_PERIOD_COL].str[4:]
    df = df.sort_values(['Year', 'Period'])

    logger.info(
        'Preprocessing klaar: %d rijen, %d sectoren, jaren %d–%d',
        len(df), df['Sector'].nunique(), df['Year'].min(), df['Year'].max()
    )

    conn = sqlite3.connect(DB_PATH)
    df.to_sql('cleaned_absenteeism', conn, if_exists='replace', index=False)
    conn.close()
    logger.info('cleaned_absenteeism opgeslagen.')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    preprocess_data()
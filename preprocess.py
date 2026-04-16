import logging
import pandas as pd
import sqlite3

logger = logging.getLogger(__name__)

# Actual column names returned by the CBS OData API (table 80072ned)
_CBS_SECTOR_COL = 'BedrijfstakkenBedrijfsgrootteSBI2008'
_CBS_ABSENCE_COL = 'Ziekteverzuimpercentage_1'
_CBS_PERIOD_COL = 'Perioden'


def preprocess_data():
    conn = sqlite3.connect('data.db')
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

    conn = sqlite3.connect('data.db')
    df.to_sql('cleaned_absenteeism', conn, if_exists='replace', index=False)
    conn.close()
    logger.info('cleaned_absenteeism opgeslagen.')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    preprocess_data()
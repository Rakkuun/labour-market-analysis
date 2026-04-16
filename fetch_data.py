import logging
import pandas as pd
import sqlite3

from db import DB_PATH

logger = logging.getLogger(__name__)

try:
    import cbsodata
except ImportError:
    logger.warning('cbsodata not installed. Install with: pip install cbsodata')
    cbsodata = None

# Helper functions for date conversion
quarters_map = {
    '1e kwartaal': '01',
    '2e kwartaal': '04',
    '3e kwartaal': '07',
    '4e kwartaal': '10'
}

months_map = {
    'januari': '01', 'februari': '02', 'maart': '03', 'april': '04',
    'mei': '05', 'juni': '06', 'juli': '07', 'augustus': '08',
    'september': '09', 'oktober': '10', 'november': '11', 'december': '12'
}

def convert_cbs_quarter_to_date(period_str):
    """Convert CBS quarter format (e.g., '2020 1e kwartaal') to date."""
    parts = period_str.split(' ', 1) 
    if len(parts) == 2:
        year = parts[0]
        quarter_name = parts[1].lower()
        if quarter_name in quarters_map:
            return pd.to_datetime(f"{year}-{quarters_map[quarter_name]}-01")    
    return pd.NaT

def convert_cbs_month_to_date(period_str):
    """Convert CBS month format (e.g., '2020 januari') to date."""
    parts = period_str.split(' ')
    if len(parts) == 2:
        year = parts[0]
        month_name = parts[1].lower()
        if month_name in months_map:
            return pd.to_datetime(f"{year}-{months_map[month_name]}-01")
    return pd.NaT

_FALLBACK_DATA = {
    'Perioden': [
        '2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02',
        '2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02',
        '2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02',
    ],
    'BedrijfstakkenSBI2008': [
        'A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw',
        'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie',
        'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid',
    ],
    'Ziekteverzuimpercentage': [
        4.5, 4.7, 4.8, 4.6, 4.4, 4.5,
        5.0, 4.8, 4.9, 5.1, 4.7, 4.6,
        3.5, 3.6, 3.4, 3.7, 3.8, 3.5,
    ],
}


def _save_fallback():
    df = pd.DataFrame(_FALLBACK_DATA)
    conn = sqlite3.connect(DB_PATH)
    df.to_sql('absenteeism', conn, if_exists='replace', index=False)
    conn.close()
    logger.warning('Fallback dummy-data opgeslagen in database.')
    return df


def fetch_absenteeism_data():
    """Fetch absenteeism data from CBS using cbsodata library."""
    absenteeism_table_id = '80072ned'  # Ziekteverzuimpercentage; bedrijfstakken

    try:
        if cbsodata is None:
            raise ImportError('cbsodata library not available')

        logger.info('CBS-data ophalen van tabel %s...', absenteeism_table_id)
        df = pd.DataFrame(cbsodata.get_data(absenteeism_table_id))
        logger.info('CBS-data opgehaald: %d rijen, kolommen: %s', len(df), df.columns.tolist())

        # Try to convert period to date (handles both quarters and months)
        df['Date'] = df['Perioden'].apply(
            lambda x: convert_cbs_quarter_to_date(x) if 'kwartaal' in str(x) else convert_cbs_month_to_date(x)
        )

        conn = sqlite3.connect(DB_PATH)
        df.to_sql('absenteeism', conn, if_exists='replace', index=False)
        conn.close()
        logger.info('CBS-data opgeslagen in database.')
        return df

    except ImportError as e:
        logger.error('cbsodata niet beschikbaar: %s — fallback naar dummy-data.', e)
        return _save_fallback()

    except Exception as e:
        logger.exception('Onverwachte fout bij ophalen CBS-data — fallback naar dummy-data.')
        return _save_fallback()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    fetch_absenteeism_data()
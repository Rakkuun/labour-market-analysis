"""Database access: loading and querying the SQLite data store."""
import re
import sqlite3

import pandas as pd


def load_data_from_db():
    """Load absenteeism and prediction data from SQLite.

    Returns:
        tuple[pd.DataFrame, pd.DataFrame]: (absenteeism_df, predictions_df)
    """
    conn = sqlite3.connect('data.db')
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

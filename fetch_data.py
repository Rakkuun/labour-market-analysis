import pandas as pd
import sqlite3
try:
    import cbsodata
except ImportError:
    print("cbsodata not installed. Install with: pip install cbsodata")
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

def fetch_absenteeism_data():
    """Fetch absenteeism data from CBS using cbsodata library."""
    absenteeism_table_id = '80072ned'  # Ziekteverzuimpercentage; bedrijfstakken
    
    try:
        if cbsodata is None:
            raise ImportError("cbsodata library not available")
        
        print(f"Fetching data from CBS table {absenteeism_table_id}...")
        df = pd.DataFrame(cbsodata.get_data(absenteeism_table_id))
        
        print(f"Successfully fetched {len(df)} records")
        print(f"Columns: {df.columns.tolist()}")
        print(f"First few rows:")
        print(df.head())
        
        # Try to convert period to date (handles both quarters and months)
        df['Date'] = df['Perioden'].apply(lambda x: convert_cbs_quarter_to_date(x) if 'kwartaal' in str(x) else convert_cbs_month_to_date(x))
        
        # Save to SQLite database
        conn = sqlite3.connect('data.db')
        df.to_sql('absenteeism', conn, if_exists='replace', index=False)
        conn.close()
        
        print("CBS data fetched and stored successfully.")
        return df
        
    except ImportError as e:
        print(f"Error: {e}")
        print("Falling back to dummy data...")
        # Fallback to dummy data
        data = {
            'Perioden': ['2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02', '2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02', '2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02'],
            'BedrijfstakkenSBI2008': ['A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw', 'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid'],
            'Ziekteverzuimpercentage': [4.5, 4.7, 4.8, 4.6, 4.4, 4.5, 5.0, 4.8, 4.9, 5.1, 4.7, 4.6, 3.5, 3.6, 3.4, 3.7, 3.8, 3.5]
        }
        df = pd.DataFrame(data)
        conn = sqlite3.connect('data.db')
        df.to_sql('absenteeism', conn, if_exists='replace', index=False)
        conn.close()
        print("Dummy data used as fallback.")
        return df
    
    except Exception as e:
        print(f"Unexpected error fetching CBS data: {e}")
        print("Falling back to dummy data...")
        # Fallback to dummy data
        data = {
            'Perioden': ['2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02', '2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02', '2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02'],
            'BedrijfstakkenSBI2008': ['A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw', 'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid'],
            'Ziekteverzuimpercentage': [4.5, 4.7, 4.8, 4.6, 4.4, 4.5, 5.0, 4.8, 4.9, 5.1, 4.7, 4.6, 3.5, 3.6, 3.4, 3.7, 3.8, 3.5]
        }
        df = pd.DataFrame(data)
        conn = sqlite3.connect('data.db')
        df.to_sql('absenteeism', conn, if_exists='replace', index=False)
        conn.close()
        print("Dummy data used as fallback.")
        return df

if __name__ == "__main__":
    fetch_absenteeism_data()
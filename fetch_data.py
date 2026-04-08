import requests
import pandas as pd
import sqlite3

def fetch_absenteeism_data():
    # For demo purposes, using dummy data since CBS API table ID is not found
    # In real use, replace with actual API call
    import pandas as pd
    data = {
        'Perioden': ['2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02', '2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02', '2020KW01', '2020KW02', '2021KW01', '2021KW02', '2022KW01', '2022KW02'],
        'BedrijfstakkenSBI2008': ['A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw', 'A Landbouw', 'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie', 'B Industrie', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid', 'C Bouwnijverheid'],
        'Ziekteverzuimpercentage': [4.5, 4.7, 4.8, 4.6, 4.4, 4.5, 5.0, 4.8, 4.9, 5.1, 4.7, 4.6, 3.5, 3.6, 3.4, 3.7, 3.8, 3.5]
    }
    df = pd.DataFrame(data)
    
    # Save to SQLite database
    conn = sqlite3.connect('data.db')
    df.to_sql('absenteeism', conn, if_exists='replace', index=False)
    conn.close()
    
    print("Dummy data fetched and stored successfully.")

if __name__ == "__main__":
    fetch_absenteeism_data()
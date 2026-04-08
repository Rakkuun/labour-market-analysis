import pandas as pd
import sqlite3

def preprocess_data():
    conn = sqlite3.connect('data.db')
    df = pd.read_sql('SELECT * FROM absenteeism', conn)
    conn.close()
    
    # Assume columns: Perioden (date), BedrijfstakkenSBI2008 (sector), Ziekteverzuimpercentage (percentage)
    # Clean data
    df.dropna(inplace=True)
    # Format Perioden to datetime if needed
    # For simplicity, assume Perioden is string like '2020KW01'
    # Convert to year
    df['Year'] = df['Perioden'].str[:4].astype(int)
    
    # Save cleaned data
    conn = sqlite3.connect('data.db')
    df.to_sql('cleaned_absenteeism', conn, if_exists='replace', index=False)
    conn.close()
    
    print("Data preprocessed and stored.")

if __name__ == "__main__":
    preprocess_data()
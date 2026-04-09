import pandas as pd
import sqlite3

def preprocess_data():
    conn = sqlite3.connect('data.db')
    df = pd.read_sql('SELECT * FROM absenteeism', conn)
    conn.close()
    
    # Drop unnecessary columns for our analysis
    df = df.drop(columns=['ID'], errors='ignore')
    
    # Rename columns for consistency
    df = df.rename(columns={
        'BedrijfskenmerkenSBI2008': 'Sector',
        'Ziekteverzuimpercentage_1': 'AbsenteeismPercentage'
    })
    
    # Clean data
    df.dropna(subset=['AbsenteeismPercentage'], inplace=True)
    
    # Convert percentage to numeric if needed
    df['AbsenteeismPercentage'] = pd.to_numeric(df['AbsenteeismPercentage'], errors='coerce')
    
    # Extract year from Perioden (format: "2020KW01" or "2020 1e kwartaal")
    df['Year'] = df['Perioden'].str[:4].astype(int)
    
    # Extract quarter/period info
    df['Period'] = df['Perioden'].str[4:]
    
    # Sort by year and period
    df = df.sort_values(['Year', 'Period'])
    
    print(f"Cleaned data: {len(df)} rows")
    print(f"Columns: {df.columns.tolist()}")
    print(f"Sectors: {df['Sector'].nunique()}")
    print(f"Year range: {df['Year'].min()} - {df['Year'].max()}")
    
    # Save cleaned data
    conn = sqlite3.connect('data.db')
    df.to_sql('cleaned_absenteeism', conn, if_exists='replace', index=False)
    conn.close()
    
    print("Data preprocessed and stored.")

if __name__ == "__main__":
    preprocess_data()
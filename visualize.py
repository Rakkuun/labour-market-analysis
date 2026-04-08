import pandas as pd
import matplotlib.pyplot as plt
import sqlite3

def create_plots():
    conn = sqlite3.connect('data.db')
    df = pd.read_sql('SELECT * FROM cleaned_absenteeism', conn)
    conn.close()
    
    # Group by sector and year, mean percentage
    grouped = df.groupby(['BedrijfstakkenSBI2008', 'Year'])['Ziekteverzuimpercentage'].mean().reset_index()
    
    # Plot for each sector
    sectors = grouped['BedrijfstakkenSBI2008'].unique()
    for sector in sectors[:5]:  # Limit to first 5 for demo
        sector_data = grouped[grouped['BedrijfstakkenSBI2008'] == sector]
        plt.figure()
        plt.plot(sector_data['Year'], sector_data['Ziekteverzuimpercentage'])
        plt.title(f'Absenteeism Trend for {sector}')
        plt.xlabel('Year')
        plt.ylabel('Percentage')
        plt.savefig(f'static/plot_{sector}.png')
        plt.close()
    
    print("Plots created.")

if __name__ == "__main__":
    create_plots()
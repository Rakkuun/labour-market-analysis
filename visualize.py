import pandas as pd
import matplotlib.pyplot as plt
import sqlite3

def create_plots():
    conn = sqlite3.connect('data.db')
    df = pd.read_sql('SELECT * FROM cleaned_absenteeism', conn)
    conn.close()
    
    if df.empty:
        print("No data to plot")
        return
    
    # Group by sector and year, calculate mean percentage
    grouped = df.groupby(['Sector', 'Year'])['AbsenteeismPercentage'].mean().reset_index()
    
    # Get top sectors by average absenteeism
    top_sectors = df.groupby('Sector')['AbsenteeismPercentage'].mean().nlargest(5).index.tolist()
    
    print(f"Creating plots for sectors: {top_sectors}")
    
    # Plot for each sector
    for sector in top_sectors:
        sector_data = grouped[grouped['Sector'] == sector].sort_values('Year')
        
        if len(sector_data) < 2:
            continue
        
        plt.figure(figsize=(10, 6))
        plt.plot(sector_data['Year'], sector_data['AbsenteeismPercentage'], 
                marker='o', linestyle='-', linewidth=2, markersize=6)
        plt.title(f'Ziekteverzuim Trend: {sector}')
        plt.xlabel('Jaar')
        plt.ylabel('Ziekteverzuim %')
        plt.grid(True, linestyle='--', alpha=0.6)
        plt.tight_layout()
        
        # Save with clean filename
        safe_sector = sector.replace('/', '_').replace(' ', '_')
        plt.savefig(f'static/plot_{safe_sector}.png', dpi=100)
        plt.close()
    
    print("Plots created.")

if __name__ == "__main__":
    create_plots()
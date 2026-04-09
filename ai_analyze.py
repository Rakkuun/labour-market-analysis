import pandas as pd
import sqlite3
from sklearn.linear_model import LinearRegression
import numpy as np

def analyze_trends():
    conn = sqlite3.connect('data.db')
    df = pd.read_sql('SELECT * FROM cleaned_absenteeism', conn)
    conn.close()
    
    if df.empty:
        print("No data to analyze")
        return
    
    # Group by sector and year, calculate mean
    grouped = df.groupby(['Sector', 'Year'])['AbsenteeismPercentage'].mean().reset_index()
    
    # Train model per sector
    sectors = grouped['Sector'].unique()
    predictions = []
    
    print(f"Analyzing trends for {len(sectors)} sectors...")
    
    for sector in sectors[:10]:  # Analyze top 10 sectors
        sector_data = grouped[grouped['Sector'] == sector].sort_values('Year')
        
        if len(sector_data) < 2:
            continue
        
        X = sector_data['Year'].values.reshape(-1, 1)
        y = sector_data['AbsenteeismPercentage'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Predict for next year
        next_year = np.array([[sector_data['Year'].max() + 1]])
        pred = model.predict(next_year)[0]
        
        predictions.append({
            'Sector': sector,
            'Predicted_Absenteeism': round(pred, 2),
            'Trend': 'Increasing' if model.coef_[0] > 0 else 'Decreasing'
        })
    
    # Save predictions
    if predictions:
        pred_df = pd.DataFrame(predictions)
        conn = sqlite3.connect('data.db')
        pred_df.to_sql('predictions', conn, if_exists='replace', index=False)
        conn.close()
        print(f"AI analysis completed. {len(predictions)} sector predictions saved.")
    else:
        print("No predictions generated.")

if __name__ == "__main__":
    analyze_trends()
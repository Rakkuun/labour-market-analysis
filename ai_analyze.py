import pandas as pd
import sqlite3
from sklearn.linear_model import LinearRegression
import numpy as np

def analyze_trends():
    conn = sqlite3.connect('data.db')
    df = pd.read_sql('SELECT * FROM cleaned_absenteeism', conn)
    conn.close()
    
    # Group by sector
    sectors = df['BedrijfstakkenSBI2008'].unique()
    predictions = {}
    
    for sector in sectors[:3]:  # Limit for demo
        sector_data = df[df['BedrijfstakkenSBI2008'] == sector].sort_values('Year')
        X = sector_data['Year'].values.reshape(-1, 1)
        y = sector_data['Ziekteverzuimpercentage'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        # Predict for next year
        next_year = np.array([[sector_data['Year'].max() + 1]])
        pred = model.predict(next_year)[0]
        predictions[sector] = pred
    
    # Save predictions
    pred_df = pd.DataFrame(list(predictions.items()), columns=['Sector', 'Predicted_Absenteeism'])
    conn = sqlite3.connect('data.db')
    pred_df.to_sql('predictions', conn, if_exists='replace', index=False)
    conn.close()
    
    print("AI analysis completed.")

if __name__ == "__main__":
    analyze_trends()
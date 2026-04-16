import logging

import numpy as np
import pandas as pd
import sqlite3
from sklearn.linear_model import LinearRegression

from db import DB_PATH, extract_quarter_number

logger = logging.getLogger(__name__)


def analyze_trends():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql('SELECT * FROM cleaned_absenteeism', conn)
    conn.close()

    if df.empty:
        logger.info('No data to analyze')
        return

    df['QuarterNum'] = pd.to_numeric(df['Period'].apply(extract_quarter_number), errors='coerce')
    df = df.dropna(subset=['QuarterNum'])
    df['QuarterNum'] = df['QuarterNum'].astype(int)
    df['TimeIndex'] = df['Year'] + (df['QuarterNum'] - 1) * 0.25

    grouped = df.groupby(['Sector', 'Year', 'QuarterNum', 'TimeIndex'])['AbsenteeismPercentage'].mean().reset_index()

    sectors = grouped['Sector'].unique()
    predictions = []

    logger.info('Analyzing trends for %d sectors...', len(sectors))

    for sector in sectors:
        sector_data = grouped[grouped['Sector'] == sector].sort_values('TimeIndex')

        if len(sector_data) < 4:
            continue

        time_idx = sector_data['TimeIndex'].values
        q = sector_data['QuarterNum'].values

        # Trend + seasonal dummies (Q1 is baseline, Q2/Q3/Q4 as dummies)
        X = np.column_stack([
            time_idx,
            (q == 2).astype(float),
            (q == 3).astype(float),
            (q == 4).astype(float),
        ])
        y = sector_data['AbsenteeismPercentage'].values

        model = LinearRegression()
        model.fit(X, y)

        trend = 'Increasing' if model.coef_[0] > 0 else 'Decreasing'

        last_time = sector_data['TimeIndex'].max()
        last_row = sector_data[sector_data['TimeIndex'] == last_time].iloc[0]
        last_year = int(last_row['Year'])
        last_q = int(last_row['QuarterNum'])

        # Residual anchoring: correct predictions for the gap between model fit and actual last value
        last_actual = last_row['AbsenteeismPercentage']
        x_last = np.array([[
            last_time,
            1.0 if last_q == 2 else 0.0,
            1.0 if last_q == 3 else 0.0,
            1.0 if last_q == 4 else 0.0,
        ]])
        last_fitted = model.predict(x_last)[0]
        residual = last_actual - last_fitted

        for i in range(1, 5):
            next_q_abs = last_q + i
            next_year = last_year + (next_q_abs - 1) // 4
            next_q_num = ((next_q_abs - 1) % 4) + 1
            next_time = next_year + (next_q_num - 1) * 0.25

            x_pred = np.array([[
                next_time,
                1.0 if next_q_num == 2 else 0.0,
                1.0 if next_q_num == 3 else 0.0,
                1.0 if next_q_num == 4 else 0.0,
            ]])
            pred = model.predict(x_pred)[0] + residual

            predictions.append({
                'Sector': sector,
                'Quarter': f"{next_year}-Q{next_q_num}",
                'Predicted_Absenteeism': round(pred, 2),
                'Trend': trend
            })

    if predictions:
        pred_df = pd.DataFrame(predictions)
        conn = sqlite3.connect(DB_PATH)
        pred_df.to_sql('predictions', conn, if_exists='replace', index=False)
        conn.close()
        logger.info('AI analysis completed. %d quarterly predictions saved for %d sectors.', len(predictions), len(sectors))
    else:
        logger.info('No predictions generated.')


if __name__ == "__main__":
    analyze_trends()

"""Builds the template context dict for the main dashboard page."""
import datetime
import json

from chart import create_plotly_figure
from db import build_sector_data


def build_pred_dict(pred_df):
    """Convert predictions DataFrame to {sector: {quarters, values}} dict."""
    pred_dict = {}
    if pred_df.empty or 'Quarter' not in pred_df.columns:
        return pred_dict

    for _, row in pred_df.iterrows():
        sector = str(row['Sector'])
        pred_dict.setdefault(sector, {'quarters': [], 'values': []})
        pred_dict[sector]['quarters'].append(str(row['Quarter']))
        pred_dict[sector]['values'].append(float(row['Predicted_Absenteeism']))

    return pred_dict


def prepare_context(df, pred_df):
    """Return the full Jinja2 template context for the dashboard.

    Args:
        df: absenteeism DataFrame
        pred_df: predictions DataFrame

    Returns:
        dict: template context
    """
    if df.empty:
        min_year = max_year = datetime.datetime.now().year
        return {
            'plot_html': '<p>No data available for plotting.</p>',
            'sectors': [],
            'sector_data_json': '{}',
            'predictions_json': '{}',
            'years': [],
            'min_year': min_year,
            'max_year': max_year,
            'default_min_year': min_year,
            'default_max_year': max_year,
            'table': '<p>No data available.</p>',
            'pred_table': '<p>No predictions available.</p>',
        }

    sector_data, sectors = build_sector_data(df)
    years = sorted(df['Year'].unique().tolist())
    min_year = int(years[0])
    max_year = int(years[-1])

    current_year = datetime.datetime.now().year
    default_max_year = min(max_year, current_year)
    default_min_year = max(min_year, default_max_year - 4)

    pred_dict = build_pred_dict(pred_df)
    plot_html = create_plotly_figure(sector_data, sectors, pred_dict)

    table = df.head(20).to_html(index=False)
    pred_table = pred_df.to_html(index=False) if not pred_df.empty else '<p>No predictions available.</p>'

    return {
        'plot_html': plot_html,
        'sectors': sectors,
        'sector_data_json': json.dumps(sector_data),
        'predictions_json': json.dumps(pred_dict),
        'years': years,
        'min_year': min_year,
        'max_year': max_year,
        'default_min_year': default_min_year,
        'default_max_year': default_max_year,
        'table': table,
        'pred_table': pred_table,
    }

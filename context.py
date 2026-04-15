"""Builds the template context dict for the main dashboard page."""
import datetime
import json

from chart import create_plotly_figure, create_seasonal_figure, create_flu_comparison_figure
from db import build_sector_data, extract_quarter_number, load_flu_data


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
            'seasonal_chart_html': '',
            'flu_chart_html': '',
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
    seasonal_chart_html = create_seasonal_figure(df)
    flu_data = load_flu_data()
    flu_chart_html = create_flu_comparison_figure(df, flu_data)

    # ── Insight cards ──────────────────────────────────────────────────────────
    _q_names = {'1': 'Q1 (winter)', '2': 'Q2 (lente)', '3': 'Q3 (zomer)', '4': 'Q4 (herfst)'}
    df_q = df.copy()
    df_q['_Q'] = df_q['Period'].apply(extract_quarter_number)
    df_q = df_q[df_q['_Q'].notna()]

    q_avg = df_q.groupby('_Q')['AbsenteeismPercentage'].mean()
    peak_q = _q_names.get(str(q_avg.idxmax()), f"Q{q_avg.idxmax()}")
    low_q  = _q_names.get(str(q_avg.idxmin()), f"Q{q_avg.idxmin()}")

    sector_avg = df.groupby('Sector')['AbsenteeismPercentage'].mean()
    highest_sector     = sector_avg.idxmax()
    highest_sector_val = round(float(sector_avg.max()), 1)
    lowest_sector      = sector_avg.idxmin()
    lowest_sector_val  = round(float(sector_avg.min()), 1)

    nat_avg = round(float(df['AbsenteeismPercentage'].mean()), 1)

    recent_avg = df[df['Year'] >= max_year - 1]['AbsenteeismPercentage'].mean()
    older_avg  = df[df['Year'].between(max_year - 3, max_year - 2)]['AbsenteeismPercentage'].mean()
    trend_up   = recent_avg > older_avg
    trend_diff = round(abs(float(recent_avg - older_avg)), 2)

    insights = {
        'nat_avg': nat_avg,
        'peak_q': peak_q,
        'low_q': low_q,
        'highest_sector': highest_sector,
        'highest_sector_val': highest_sector_val,
        'lowest_sector': lowest_sector,
        'lowest_sector_val': lowest_sector_val,
        'trend_up': trend_up,
        'trend_diff': trend_diff,
        'n_sectors': len(sectors),
        'data_from': min_year,
        'data_to': max_year,
    }

    table = df.head(20).to_html(index=False)
    pred_table = pred_df.to_html(index=False) if not pred_df.empty else '<p>No predictions available.</p>'

    return {
        'plot_html': plot_html,
        'seasonal_chart_html': seasonal_chart_html,
        'flu_chart_html': flu_chart_html,
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
        'insights': insights,
    }

"""
Utility functions for data processing and visualization.
"""
import re
import datetime
import pandas as pd
import sqlite3
import json
import plotly.graph_objects as go


def load_data_from_db():
    """Load absenteeism and prediction data from SQLite database."""
    conn = sqlite3.connect('data.db')
    df = pd.read_sql('SELECT * FROM cleaned_absenteeism', conn)
    pred_df = pd.read_sql('SELECT * FROM predictions', conn)
    conn.close()
    return df, pred_df


def extract_quarter_number(period_str):
    """Extract quarter number from period string.
    
    Examples:
        "KW01" -> "1"
        "1e kwartaal" -> "1"
    Returns None for non-quarter or blank periods.
    """
    period = str(period_str).strip() if pd.notna(period_str) else ''
    if not period:
        return None

    kw_match = re.search(r'KW0*([1-4])', period, re.IGNORECASE)
    if kw_match:
        return kw_match.group(1)

    norm_match = re.search(r'([1-4])e kwartaal', period, re.IGNORECASE)
    if norm_match:
        return norm_match.group(1)

    return None


def build_sector_data(df):
    """Build sector data structure with quarters, values, and years.
    
    Returns:
        dict: {sector: {quarters: [...], values: [...], years: [...]}}
    """
    sectors = sorted(df['Sector'].unique().tolist())
    sector_data = {}
    
    for sector in sectors:
        data = df[df['Sector'] == sector].sort_values(['Year', 'Period']).copy()
        
        quarters = []
        years_list = []
        values = []
        
        for _, row in data.iterrows():
            year = int(row['Year'])
            period = str(row['Period']).strip() if pd.notna(row['Period']) else ''
            quarter = extract_quarter_number(period)
            
            # Only include valid quarterly rows; skip annual or blank period rows
            if quarter is None:
                continue
            
            quarter_label = f"{year}-Q{quarter}"
            quarters.append(quarter_label)
            years_list.append(year)
            values.append(row['AbsenteeismPercentage'])
        
        sector_data[sector] = {
            'quarters': quarters,
            'values': values,
            'years': years_list
        }
    
    return sector_data, sectors


def create_plotly_figure(sector_data, sectors):
    """Create Plotly figure for all sectors.
    
    Args:
        sector_data: dict with sector information
        sectors: list of sector names
        
    Returns:
        str: HTML representation of the Plotly figure
    """
    fig = go.Figure()
    
    for sector in sectors:
        quarters = sector_data[sector]['quarters']
        values = sector_data[sector]['values']
        
        fig.add_trace(go.Scatter(
            x=quarters,
            y=values,
            mode='lines+markers',
            name=sector,
            visible=True,
            hovertemplate='<b>%{text}</b><br>Kwartaal: %{x}<br>Verzuim: %{y:.2f}%<extra></extra>',
            text=[sector] * len(values)
        ))
    
    fig.update_layout(
        title='Ziekteverzuimpercentage per sector over tijd',
        xaxis_title='Kwartaal',
        yaxis_title='Ziekteverzuim %',
        legend_title='Sector',
        hovermode='closest',
        margin=dict(l=40, r=40, t=70, b=40),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn', div_id='plotly-chart')


def prepare_context(df, pred_df):
    """Prepare template context with all necessary data.
    
    Args:
        df: absenteeism DataFrame
        pred_df: predictions DataFrame
        
    Returns:
        dict: context for template rendering
    """
    if df.empty:
        min_year = 2024
        max_year = 2024
        return {
            'plot_html': '<p>No data available for plotting.</p>',
            'sectors': [],
            'sector_data_json': '{}',
            'years': [],
            'min_year': min_year,
            'max_year': max_year,
            'default_min_year': min_year,
            'default_max_year': max_year,
            'table': '<p>No data available.</p>',
            'pred_table': '<p>No predictions available.</p>'
        }
    
    # Process sector and time data
    sector_data, sectors = build_sector_data(df)
    years = sorted(df['Year'].unique().tolist())
    min_year = int(years[0])
    max_year = int(years[-1])

    current_year = datetime.datetime.now().year
    default_max_year = min(max_year, current_year)
    default_min_year = max(min_year, default_max_year - 4)
    
    # Create visualizations and tables
    plot_html = create_plotly_figure(sector_data, sectors)
    table = df.head(20).to_html(index=False)
    pred_table = pred_df.to_html(index=False) if not pred_df.empty else '<p>No predictions available.</p>'
    
    return {
        'plot_html': plot_html,
        'sectors': sectors,
        'sector_data_json': json.dumps(sector_data),
        'years': years,
        'min_year': min_year,
        'max_year': max_year,
        'default_min_year': default_min_year,
        'default_max_year': default_max_year,
        'table': table,
        'pred_table': pred_table
    }

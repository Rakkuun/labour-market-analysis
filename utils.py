"""
Utility functions for data processing and visualization.
"""
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
        "" -> "1" (default)
    """
    period = str(period_str).strip() if pd.notna(period_str) else ''
    
    if 'KW' in period:
        q_num = period.replace('KW', '').lstrip('0') or '0'
    elif period and period[0].isdigit():
        q_num = period[0]
    else:
        q_num = '1'
    
    return q_num


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
        
        for _, row in data.iterrows():
            year = int(row['Year'])
            q_num = extract_quarter_number(row['Period'])
            quarter_label = f"{year}-Q{q_num}"
            
            quarters.append(quarter_label)
            years_list.append(year)
        
        sector_data[sector] = {
            'quarters': quarters,
            'values': data['AbsenteeismPercentage'].tolist(),
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
        return {
            'plot_html': '<p>No data available for plotting.</p>',
            'sectors': [],
            'sector_data_json': '{}',
            'years': [],
            'min_year': 2024,
            'max_year': 2024,
            'table': '<p>No data available.</p>',
            'pred_table': '<p>No predictions available.</p>'
        }
    
    # Process sector and time data
    sector_data, sectors = build_sector_data(df)
    years = sorted(df['Year'].unique().tolist())
    min_year = int(years[0])
    max_year = int(years[-1])
    
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
        'table': table,
        'pred_table': pred_table
    }

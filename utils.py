"""
Utility functions for data processing and visualization.
"""
import re
import datetime
import pandas as pd
import sqlite3
import json
import plotly.graph_objects as go
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()


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


def create_plotly_figure(sector_data, sectors, pred_dict=None):
    """Create Plotly figure for all sectors.
    
    Args:
        sector_data: dict with sector information
        sectors: list of sector names
        pred_dict: optional dict {sector: predicted_value} for dashed forecast lines
        
    Returns:
        str: HTML representation of the Plotly figure
    """
    fig = go.Figure()

    COLORS = [
        '#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
        '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52',
        '#1F77B4', '#FF7F0E', '#2CA02C', '#D62728', '#9467BD',
        '#8C564B', '#E377C2', '#7F7F7F', '#BCBD22', '#17BECF',
        '#AEC7E8', '#FFBB78', '#98DF8A', '#FF9896', '#C5B0D5',
        '#C49C94', '#F7B6D2', '#C7C7C7', '#DBDB8D', '#9EDAE5',
        '#393B79', '#637939', '#8C6D31', '#843C39', '#7B4173',
        '#5254A3', '#B5CF6B', '#E7CB94', '#AD494A', '#A55194'
    ]

    for i, sector in enumerate(sectors):
        color = COLORS[i % len(COLORS)]
        quarters = sector_data[sector]['quarters']
        values = sector_data[sector]['values']
        years = sector_data[sector]['years']
        
        fig.add_trace(go.Scatter(
            x=quarters,
            y=values,
            mode='lines+markers',
            name=sector,
            legendgroup=sector,
            visible=True,
            line=dict(color=color),
            marker=dict(color=color),
            hovertemplate='<b>%{text}</b><br>Kwartaal: %{x}<br>Verzuim: %{y:.2f}%<extra></extra>',
            text=[sector] * len(values)
        ))

        if pred_dict and sector in pred_dict and quarters:
            pred_quarters = pred_dict[sector]['quarters']
            pred_values = pred_dict[sector]['values']
            fig.add_trace(go.Scatter(
                x=[quarters[-1]] + pred_quarters,
                y=[values[-1]] + pred_values,
                mode='lines+markers',
                name=f"{sector} (prognose)",
                legendgroup=sector,
                showlegend=False,
                line=dict(dash='dot', color=color),
                marker=dict(color=color),
                hovertemplate='<b>%{text}</b><br>%{x}<br>Prognose: %{y:.2f}%<extra></extra>',
                text=[sector] * (1 + len(pred_quarters))
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
    
    # Build predictions dict {sector: {quarters: [...], values: [...]}} for chart
    pred_dict = {}
    if not pred_df.empty and 'Quarter' in pred_df.columns:
        for _, row in pred_df.iterrows():
            sector = str(row['Sector'])
            if sector not in pred_dict:
                pred_dict[sector] = {'quarters': [], 'values': []}
            pred_dict[sector]['quarters'].append(str(row['Quarter']))
            pred_dict[sector]['values'].append(float(row['Predicted_Absenteeism']))

    # Create visualizations and tables
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
        'pred_table': pred_table
    }


def analyze_with_ai(sector_data, selected_sectors, year_min, year_max):
    """Analyze sector trends using DeepSeek AI.
    
    Args:
        sector_data: dict with sector information
        selected_sectors: list of selected sector names
        year_min: minimum year for analysis
        year_max: maximum year for analysis
        
    Returns:
        str: AI-generated analysis text
    """
    # Build data summary for AI
    stats = []
    for sector in selected_sectors:
        quarters = sector_data[sector]['quarters']
        values = sector_data[sector]['values']
        years = sector_data[sector]['years']
        filtered_values = []
        for i in range(len(years)):
            if year_min <= years[i] <= year_max:
                filtered_values.append(values[i])
        if filtered_values:
            start = filtered_values[0]
            end = filtered_values[-1]
            avg = sum(filtered_values) / len(filtered_values)
            min_val = min(filtered_values)
            max_val = max(filtered_values)
            stats.append({
                'sector': sector,
                'start': round(start, 2),
                'end': round(end, 2),
                'avg': round(avg, 2),
                'min': round(min_val, 2),
                'max': round(max_val, 2),
                'quarters': len(filtered_values)
            })
    if not stats:
        return 'Geen data beschikbaar voor de geselecteerde periode.'
    data_str = json.dumps(stats, indent=2)
    prompt = f"""Je bent een arbeidsmarktanalist die grafieken met ziekteverzuimpercentages analyseert.\n\nAnalyseer deze data voor sectoren in Nederland van {year_min} tot {year_max}:\n{data_str}\n\nGeef een korte, professionele trendanalyse in Nederlands (2-3 zinnen max). Focus op:\n1. Trends (op/neerwaartse beweging)\n2. Vergelijking tussen sectoren (als meer dan 1)\n3. Opvallende patronen of anomalieën\n\nWees beknopt en specifiek."""

    api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
    base_url = 'https://api.deepseek.com'
    model = 'deepseek-chat'
    if not api_key:
        raise Exception('DeepSeek API-key niet geconfigureerd. Voeg DEEPSEEK_API_KEY toe aan .env')
    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'user', 'content': prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f'Fout bij AI-analyse: {str(e)}'

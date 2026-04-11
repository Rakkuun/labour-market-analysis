"""Re-export shim for backwards compatibility.

All logic has been split into focused modules:
  db.py      - database access and sector data building
  chart.py   - Plotly figure creation
  ai.py      - DeepSeek AI analysis and company lookup
  context.py - Flask template context preparation
"""
from db import load_data_from_db, build_sector_data          # noqa: F401
from chart import create_plotly_figure                        # noqa: F401
from ai import analyze_with_ai, lookup_company_info           # noqa: F401
from context import prepare_context                           # noqa: F401



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


def _hover_text_color(hex_color):
    """Return '#000000' or '#ffffff' based on WCAG relative luminance."""
    h = hex_color.lstrip('#')
    r, g, b = int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255
    def lin(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    lum = 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)
    return '#000000' if lum > 0.179 else '#ffffff'


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
            hoverlabel=dict(font=dict(color=_hover_text_color(color))),
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
                hoverlabel=dict(font=dict(color=_hover_text_color(color))),
                hovertemplate='<b>%{text}</b><br>%{x}<br>Prognose: %{y:.2f}%<extra></extra>',
                text=[sector] * (1 + len(pred_quarters))
            ))
    
    fig.update_layout(
        title='Ziekteverzuimpercentage per sector over tijd',
        xaxis=dict(title=dict(text='Kwartaal', standoff=20), tickangle=-45),
        yaxis=dict(title=dict(text='Ziekteverzuim %', standoff=10)),
        legend_title='Sector',
        hovermode='closest',
        margin=dict(l=70, r=40, t=70, b=80),
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


def analyze_with_ai(sector_data, selected_sectors, year_min, year_max, pred_dict=None):
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
        return 'Geen data beschikbaar voor de geselecteerde periode.', ''
    data_str = json.dumps(stats, indent=2)

    # Build forecast summary for selected sectors
    forecast_stats = []
    if pred_dict:
        for sector in selected_sectors:
            if sector in pred_dict:
                forecast_stats.append({
                    'sector': sector,
                    'prognoses': [
                        {'kwartaal': q, 'waarde': v}
                        for q, v in zip(pred_dict[sector]['quarters'], pred_dict[sector]['values'])
                    ]
                })
    forecast_str = json.dumps(forecast_stats, indent=2) if forecast_stats else 'Geen prognosedata beschikbaar.'

    prompt = f"""Je bent een arbeidsmarktanalist die ziekteverzuimpercentages analyseert.

HISTORISCHE DATA ({year_min}-{year_max}):
{data_str}

KWARTAALPROGNOSES (seizoensgecorrigeerde lineaire regressie):
{forecast_str}

Geef je antwoord in exact dit formaat, twee secties gescheiden door "###":

Eerste sectie: 2-3 zinnen historische trendanalyse van de data.
###
Tweede sectie: 2-3 zinnen over de verwachting voor de komende 4 kwartalen op basis van de prognosedata, inclusief seizoenspatroon en trendrichting als onderbouwing.

Begin elke sectie direct met de inhoud, zonder labels of koppen. Schrijf in professioneel Nederlands. Wees beknopt en specifiek."""

    api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
    base_url = 'https://api.deepseek.com'
    model = 'deepseek-chat'
    if not api_key:
        raise Exception('DeepSeek API-key niet geconfigureerd. Voeg DEEPSEEK_API_KEY toe aan .env')
    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=500,
            temperature=0.7
        )
        full_text = response.choices[0].message.content
        parts = full_text.split('###', 1)
        analysis = parts[0].strip()
        forecast = parts[1].strip() if len(parts) > 1 else ''
        return analysis, forecast
    except Exception as e:
        return f'Fout bij AI-analyse: {str(e)}', ''


def lookup_company_info(company_name):
    """Use DeepSeek AI to determine CBS SBI 2008 classification for a Dutch company.

    Returns a dict with keys: bedrijfssector, bedrijfstak, bedrijfsklasse, bedrijfsgrootte.
    All values are exact matches with the Sector column in the CBS absenteeism dataset.
    Returns null (None -> JSON null) for bedrijfstak/bedrijfsklasse when no match exists in the data.
    """
    # These are the EXACT values present in the Sector column of our CBS dataset.
    # The AI must pick from these lists only.
    prompt = f"""Je bent een expert in de Nederlandse CBS-bedrijfsclassificatie (SBI 2008).

Gegeven bedrijfsnaam: "{company_name}"

Kies voor dit bedrijf de meest passende waarden uit de onderstaande lijsten.
Je MOET exact de vermelde waarden gebruiken — geen variaties, geen omschrijvingen.

BEDRIJFSSECTOR (kies precies één waarde):
A Landbouw, bosbouw en visserij
B Delfstoffenwinning
C Industrie
D Energievoorziening
E Waterbedrijven en afvalbeheer
F Bouwnijverheid
G Handel
H Vervoer en opslag
I Horeca
J Informatie en communicatie
K Financiële dienstverlening
L Verhuur en handel van onroerend goed
M Specialistische zakelijke diensten
N Verhuur en overige zakelijke diensten
O Openbaar bestuur en overheidsdiensten
P Onderwijs
Q Gezondheids- en welzijnszorg
R Cultuur, sport en recreatie
S Overige dienstverlening

BEDRIJFSTAK (kies de meest passende waarde, of null als geen past):
10-12 Voedings-, genotmiddelenindustrie
17-18 Papier- en grafische industrie
19-22 Raffinaderijen en chemie
24-30, 33 Metaal-elektro industrie
45 Autohandel en -reparatie
46 Groothandel en handelsbemiddeling
47 Detailhandel (niet in auto's)
49 Vervoer over land
86 Gezondheidszorg
87 Verpleging en zorg met overnachting
88 Welzijnszorg zonder overnachting
812 Schoonmaakbedrijven

BEDRIJFSKLASSE (kies de meest passende waarde, of null als geen past):
861 Ziekenhuizen

BEDRIJFSGROOTTE (kies precies één waarde):
1 tot 10 werkzame personen
10 tot 100 werkzame personen
100 of meer werkzame personen

Antwoord uitsluitend in JSON-formaat zonder extra tekst of markdown. Gebruik null (geen aanhalingstekens) als er geen passende waarde is voor bedrijfstak of bedrijfsklasse:
{{"bedrijfssector": "...", "bedrijfstak": "..." or null, "bedrijfsklasse": "..." or null, "bedrijfsgrootte": "..."}}"""

    api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
    if not api_key:
        raise Exception('DeepSeek API-key niet geconfigureerd.')
    client = OpenAI(api_key=api_key, base_url='https://api.deepseek.com')
    response = client.chat.completions.create(
        model='deepseek-chat',
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=200,
        temperature=0.0
    )
    content = response.choices[0].message.content.strip()
    # Strip markdown code fences if the model adds them
    if content.startswith('```'):
        content = re.sub(r'^```[a-z]*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)
    data = json.loads(content.strip())
    # Normalise: replace empty strings with None for optional fields
    for field in ('bedrijfstak', 'bedrijfsklasse'):
        if not data.get(field):
            data[field] = None
    return data

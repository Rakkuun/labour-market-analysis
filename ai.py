"""AI-powered analysis and company classification via DeepSeek."""
import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

_DEEPSEEK_BASE_URL = 'https://api.deepseek.com'
_DEEPSEEK_MODEL = 'deepseek-chat'


def _get_client():
    api_key = os.getenv('DEEPSEEK_API_KEY', '').strip()
    if not api_key:
        raise Exception('DeepSeek API-key niet geconfigureerd. Voeg DEEPSEEK_API_KEY toe aan .env')
    return OpenAI(api_key=api_key, base_url=_DEEPSEEK_BASE_URL)


# ── Trend analysis ────────────────────────────────────────────────────────────

def _build_stats(sector_data, selected_sectors, year_min, year_max):
    stats = []
    for sector in selected_sectors:
        quarters = sector_data[sector]['quarters']
        values = sector_data[sector]['values']
        years = sector_data[sector]['years']
        filtered = [v for v, y in zip(values, years) if year_min <= y <= year_max]
        if filtered:
            stats.append({
                'sector': sector,
                'start': round(filtered[0], 2),
                'end': round(filtered[-1], 2),
                'avg': round(sum(filtered) / len(filtered), 2),
                'min': round(min(filtered), 2),
                'max': round(max(filtered), 2),
                'quarters': len(filtered),
            })
    return stats


def _build_forecast_stats(selected_sectors, pred_dict):
    if not pred_dict:
        return []
    return [
        {
            'sector': sector,
            'prognoses': [
                {'kwartaal': q, 'waarde': v}
                for q, v in zip(pred_dict[sector]['quarters'], pred_dict[sector]['values'])
            ],
        }
        for sector in selected_sectors
        if sector in pred_dict
    ]


def analyze_with_ai(sector_data, selected_sectors, year_min, year_max, pred_dict=None):
    """Generate a Dutch trend analysis and forecast via DeepSeek.

    Returns:
        tuple[str, str]: (historical_analysis, forecast_text)
    """
    stats = _build_stats(sector_data, selected_sectors, year_min, year_max)
    if not stats:
        return 'Geen data beschikbaar voor de geselecteerde periode.', ''

    forecast_stats = _build_forecast_stats(selected_sectors, pred_dict)
    forecast_str = json.dumps(forecast_stats, indent=2) if forecast_stats else 'Geen prognosedata beschikbaar.'

    prompt = f"""Je bent een arbeidsmarktanalist die ziekteverzuimpercentages analyseert.

HISTORISCHE DATA ({year_min}-{year_max}):
{json.dumps(stats, indent=2)}

KWARTAALPROGNOSES (seizoensgecorrigeerde lineaire regressie):
{forecast_str}

Geef je antwoord in exact dit formaat, twee secties gescheiden door "###":

Eerste sectie: 2-3 zinnen historische trendanalyse van de data.
###
Tweede sectie: 2-3 zinnen over de verwachting voor de komende 4 kwartalen op basis van de prognosedata, inclusief seizoenspatroon en trendrichting als onderbouwing.

Begin elke sectie direct met de inhoud, zonder labels of koppen. Schrijf in professioneel Nederlands. Wees beknopt en specifiek."""

    try:
        response = _get_client().chat.completions.create(
            model=_DEEPSEEK_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=500,
            temperature=0.7,
        )
        parts = response.choices[0].message.content.split('###', 1)
        return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ''
    except Exception as e:
        return f'Fout bij AI-analyse: {e}', ''


# ── Company CBS classification ────────────────────────────────────────────────

_LOOKUP_PROMPT = """Je bent een expert in de Nederlandse CBS-bedrijfsclassificatie (SBI 2008).

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


def lookup_company_info(company_name):
    """Classify a Dutch company according to CBS SBI 2008 using DeepSeek.

    Returns:
        dict with keys: bedrijfssector, bedrijfstak, bedrijfsklasse, bedrijfsgrootte.
        bedrijfstak and bedrijfsklasse are None when no match exists in the dataset.
    """
    prompt = _LOOKUP_PROMPT.format(company_name=company_name)

    response = _get_client().chat.completions.create(
        model=_DEEPSEEK_MODEL,
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=200,
        temperature=0.0,
    )
    content = response.choices[0].message.content.strip()

    # Strip markdown code fences if the model adds them
    if content.startswith('```'):
        content = re.sub(r'^```[a-z]*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)

    data = json.loads(content.strip())

    # Allowed exact values per field — AI must return one of these or null
    _ALLOWED = {
        'bedrijfstak': {
            '10-12 Voedings-, genotmiddelenindustrie',
            '17-18 Papier- en grafische industrie',
            '19-22 Raffinaderijen en chemie',
            '24-30, 33 Metaal-elektro industrie',
            '45 Autohandel en -reparatie',
            '46 Groothandel en handelsbemiddeling',
            "47 Detailhandel (niet in auto's)",
            '49 Vervoer over land',
            '86 Gezondheidszorg',
            '87 Verpleging en zorg met overnachting',
            '88 Welzijnszorg zonder overnachting',
            '812 Schoonmaakbedrijven',
        },
        'bedrijfsklasse': {'861 Ziekenhuizen'},
    }

    # Normalise: replace empty strings or non-whitelisted values with None
    for field in ('bedrijfstak', 'bedrijfsklasse'):
        val = data.get(field)
        if not val or val not in _ALLOWED[field]:
            data[field] = None

    return data


# ── Conversational analytics agent ───────────────────────────────────────────

_CHAT_TOOLS = [
    {
        'type': 'function',
        'function': {
            'name': 'list_sectors',
            'description': 'Geeft een lijst van alle beschikbare sectoren in de dataset.',
            'parameters': {'type': 'object', 'properties': {}, 'required': []},
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_sector_stats',
            'description': 'Geeft statistieken over ziekteverzuim (gemiddelde, min, max, meest recente waarde) voor een sector, optioneel gefilterd op jaar.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'sector': {'type': 'string', 'description': 'Exacte sectornaam zoals in de dataset'},
                    'year_min': {'type': 'integer', 'description': 'Beginjaar (optioneel)'},
                    'year_max': {'type': 'integer', 'description': 'Eindjaar (optioneel)'},
                },
                'required': ['sector'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'compare_sectors',
            'description': 'Vergelijkt ziekteverzuimstatistieken tussen twee sectoren naast elkaar.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'sector_a': {'type': 'string', 'description': 'Eerste sector'},
                    'sector_b': {'type': 'string', 'description': 'Tweede sector'},
                    'year_min': {'type': 'integer', 'description': 'Beginjaar (optioneel)'},
                    'year_max': {'type': 'integer', 'description': 'Eindjaar (optioneel)'},
                },
                'required': ['sector_a', 'sector_b'],
            },
        },
    },
    {
        'type': 'function',
        'function': {
            'name': 'get_forecast',
            'description': 'Geeft de kwartaalprognoses voor de komende vier kwartalen voor een sector.',
            'parameters': {
                'type': 'object',
                'properties': {
                    'sector': {'type': 'string', 'description': 'Exacte sectornaam'},
                },
                'required': ['sector'],
            },
        },
    },
]


def _tool_list_sectors(df):
    sectors = sorted(df['Sector'].unique().tolist())
    return {'sectoren': sectors, 'aantal': len(sectors)}


def _tool_get_sector_stats(df, sector, year_min=None, year_max=None):
    s = df[df['Sector'] == sector].copy()
    if year_min is not None:
        s = s[s['Year'] >= year_min]
    if year_max is not None:
        s = s[s['Year'] <= year_max]
    if s.empty:
        return {'fout': f'Geen data gevonden voor sector: {sector}'}
    vals = s['AbsenteeismPercentage'].dropna()
    recent = s.sort_values(['Year', 'Period']).iloc[-1]
    return {
        'sector': sector,
        'periode': f"{int(s['Year'].min())}–{int(s['Year'].max())}",
        'gemiddelde_pct': round(float(vals.mean()), 2),
        'minimum_pct': round(float(vals.min()), 2),
        'maximum_pct': round(float(vals.max()), 2),
        'meest_recent_pct': round(float(recent['AbsenteeismPercentage']), 2),
        'meest_recent_periode': f"{int(recent['Year'])} {recent['Period']}",
        'n_kwartalen': int(len(vals)),
    }


def _tool_compare_sectors(df, sector_a, sector_b, year_min=None, year_max=None):
    return {
        sector_a: _tool_get_sector_stats(df, sector_a, year_min, year_max),
        sector_b: _tool_get_sector_stats(df, sector_b, year_min, year_max),
    }


def _tool_get_forecast(pred_df, sector):
    rows = pred_df[pred_df['Sector'] == sector].sort_values('Quarter')
    if rows.empty:
        return {'fout': f'Geen prognose gevonden voor sector: {sector}'}
    return {
        'sector': sector,
        'prognoses': [
            {'kwartaal': row['Quarter'], 'verzuim_pct': round(float(row['Predicted_Absenteeism']), 2)}
            for _, row in rows.iterrows()
        ],
    }


def _execute_tool(name, args, df, pred_df):
    if name == 'list_sectors':
        return _tool_list_sectors(df)
    if name == 'get_sector_stats':
        return _tool_get_sector_stats(df, **args)
    if name == 'compare_sectors':
        return _tool_compare_sectors(df, **args)
    if name == 'get_forecast':
        return _tool_get_forecast(pred_df, **args)
    return {'fout': f'Onbekend tool: {name}'}


def chat_with_agent(message, history, df, pred_df, active_sector=None):
    """Conversational agent that answers questions about absenteeism data using tools.

    Args:
        message: the user's latest message
        history: list of {role, content} dicts (prior turns)
        df: cleaned_absenteeism DataFrame
        pred_df: predictions DataFrame
        active_sector: sector currently selected in the dashboard (optional)

    Returns:
        str: the agent's reply in Dutch
    """
    system = (
        'Je bent een arbeidsmarktanalist die helpt bij het interpreteren van Nederlandse '
        'CBS-ziekteverzuimdata (1996–2025, 39 sectoren) en kwartaalprognoses. '
        'Gebruik de beschikbare tools om vragen te beantwoorden met echte data. '
        'Antwoord altijd in het Nederlands. Wees beknopt maar informatief (2–4 zinnen). '
        'Noem concrete percentages uit de data wanneer dat relevant is.'
    )
    if active_sector:
        system += f" De gebruiker heeft momenteel sector '{active_sector}' geselecteerd."

    messages = [{'role': 'system', 'content': system}]
    for h in (history or [])[-8:]:
        if h.get('role') in ('user', 'assistant') and h.get('content'):
            messages.append({'role': h['role'], 'content': h['content']})
    messages.append({'role': 'user', 'content': message})

    client = _get_client()
    for _ in range(5):
        response = client.chat.completions.create(
            model=_DEEPSEEK_MODEL,
            messages=messages,
            tools=_CHAT_TOOLS,
            tool_choice='auto',
            max_tokens=600,
            temperature=0.5,
        )
        msg = response.choices[0].message
        # Append as dict so it serialises cleanly for subsequent rounds
        messages.append(msg)

        if not msg.tool_calls:
            return (msg.content or '').strip()

        for tc in msg.tool_calls:
            result = _execute_tool(
                tc.function.name,
                json.loads(tc.function.arguments),
                df,
                pred_df,
            )
            messages.append({
                'role': 'tool',
                'tool_call_id': tc.id,
                'content': json.dumps(result, ensure_ascii=False),
            })

    return 'Sorry, ik kon deze vraag niet volledig beantwoorden. Probeer het opnieuw.'

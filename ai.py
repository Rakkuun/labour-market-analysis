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

    # Normalise: replace empty strings with None for optional fields
    for field in ('bedrijfstak', 'bedrijfsklasse'):
        if not data.get(field):
            data[field] = None

    return data

"""
Labour Market Analysis Flask Application

A web application for analyzing Dutch labour market data,
specifically absenteeism rates across different sectors.
"""
from flask import Flask, render_template, request, jsonify
from utils import load_data_from_db, prepare_context, build_sector_data, analyze_with_ai, lookup_company_info

app = Flask(__name__)


@app.route('/')
def index():
    """Render the main dashboard page."""
    df, pred_df = load_data_from_db()
    context = prepare_context(df, pred_df)
    return render_template('index.html', **context)


@app.route('/api/analyze', methods=['POST'])
def api_analyze():
    """Generate AI analysis for selected sectors and year range."""
    try:
        data = request.json
        selected_sectors = data.get('sectors', [])
        year_min = data.get('year_min', 2021)
        year_max = data.get('year_max', 2025)
        pred_dict = data.get('pred_dict', None)

        # Load and prepare data
        df, _ = load_data_from_db()
        sector_data, _ = build_sector_data(df)

        # Get AI analysis
        analysis, forecast = analyze_with_ai(sector_data, selected_sectors, year_min, year_max, pred_dict)

        return jsonify({'analysis': analysis, 'forecast': forecast})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/lookup-company', methods=['POST'])
def api_lookup_company():
    """Look up CBS classification for a given company name using AI."""
    try:
        data = request.json
        company_name = (data.get('company_name') or '').strip()
        if not company_name:
            return jsonify({'error': 'Geen bedrijfsnaam opgegeven'}), 400
        result = lookup_company_info(company_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)

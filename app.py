"""
Labour Market Analysis Flask Application

A web application for analyzing Dutch labour market data,
specifically absenteeism rates across different sectors.
"""
from flask import Flask, render_template, request, jsonify
from db import load_data_from_db, build_sector_data
from ai import analyze_with_ai, lookup_company_info
from context import prepare_context

app = Flask(__name__)


@app.route('/')
def home():
    """Render the homepage."""
    df, _ = load_data_from_db()
    n_sectors = df['Sector'].nunique() if not df.empty else 0
    min_year = int(df['Year'].min()) if not df.empty else 1996
    max_year = int(df['Year'].max()) if not df.empty else 2025
    return render_template('home.html', active_page='home',
                           n_sectors=n_sectors, min_year=min_year, max_year=max_year)


@app.route('/tools')
def tools():
    """Render the tools overview page."""
    return render_template('tools.html', active_page='tools')


@app.route('/tools/ziekteverzuim')
def ziekteverzuim():
    """Render the ziekteverzuim dashboard."""
    df, pred_df = load_data_from_db()
    context = prepare_context(df, pred_df)
    context['active_page'] = 'ziekteverzuim'
    return render_template('ziekteverzuim.html', **context)


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

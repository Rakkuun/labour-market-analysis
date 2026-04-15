"""
Labour Market Analysis Flask Application

A web application for analyzing Dutch labour market data,
specifically absenteeism rates across different sectors.
"""
import os
from functools import wraps

from flask import Flask, render_template, request, jsonify, Response
from apscheduler.schedulers.background import BackgroundScheduler

from db import load_data_from_db, build_sector_data, init_admin_tables, get_refresh_log, get_api_usage_stats
from ai import analyze_with_ai, lookup_company_info, chat_with_agent
from context import prepare_context
from chart import create_hero_preview_figure
from refresh import run_refresh

app = Flask(__name__)

# Initialise admin log tables on startup
init_admin_tables()

# ── Nightly scheduler ─────────────────────────────────────────────────────────
_scheduler = BackgroundScheduler(daemon=True)
_scheduler.add_job(lambda: run_refresh('cbs'), 'cron', hour=3, minute=0,
                   id='nightly_cbs', misfire_grace_time=3600)
_scheduler.add_job(lambda: run_refresh('flu'), 'cron', hour=3, minute=30,
                   id='nightly_flu', misfire_grace_time=3600)
_scheduler.start()

# ── Admin Basic Auth ──────────────────────────────────────────────────────────
def _require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        password = os.getenv('ADMIN_PASSWORD', '').strip()
        auth = request.authorization
        if not password or not auth or auth.password != password:
            return Response(
                'Toegang geweigerd', 401,
                {'WWW-Authenticate': 'Basic realm="Admin"'}
            )
        return f(*args, **kwargs)
    return decorated


@app.route('/')
def home():
    """Render the homepage."""
    df, _ = load_data_from_db()
    n_sectors = df['Sector'].nunique() if not df.empty else 0
    min_year = int(df['Year'].min()) if not df.empty else 1996
    max_year = int(df['Year'].max()) if not df.empty else 2025
    hero_chart_html = create_hero_preview_figure(df) if not df.empty else ''
    return render_template('home.html', active_page='home',
                           n_sectors=n_sectors, min_year=min_year, max_year=max_year,
                           hero_chart_html=hero_chart_html)


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


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """Conversational analytics: answer questions about absenteeism data using an AI agent."""
    try:
        data = request.json
        message = (data.get('message') or '').strip()
        if not message:
            return jsonify({'error': 'Geen bericht opgegeven'}), 400
        history = data.get('history') or []
        active_sector = (data.get('active_sector') or '').strip() or None

        df, pred_df = load_data_from_db()
        reply = chat_with_agent(message, history, df, pred_df, active_sector)
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Admin ─────────────────────────────────────────────────────────────────────

@app.route('/admin')
@_require_admin
def admin():
    """Admin dashboard: refresh log + API usage stats."""
    refresh_log = get_refresh_log(limit=30)
    usage = get_api_usage_stats()
    jobs = [
        {'id': j.id, 'next_run': str(j.next_run_time)[:19] if j.next_run_time else '—'}
        for j in _scheduler.get_jobs()
    ]
    return render_template('admin.html', refresh_log=refresh_log, usage=usage, jobs=jobs)


@app.route('/admin/refresh', methods=['POST'])
@_require_admin
def admin_refresh():
    """Trigger a manual data refresh."""
    source = (request.json or {}).get('source', '').strip()
    if source not in ('cbs', 'flu'):
        return jsonify({'error': 'Ongeldige bron. Gebruik "cbs" of "flu".'}), 400
    result = run_refresh(source)
    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True)

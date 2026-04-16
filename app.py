"""
Labour Market Analysis Flask Application

A web application for analyzing Dutch labour market data,
specifically absenteeism rates across different sectors.
"""
import hmac
import logging
import os
from functools import wraps

from flask import Flask, render_template, request, jsonify, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from apscheduler.schedulers.background import BackgroundScheduler

from db import load_data_from_db, build_sector_data, init_admin_tables, get_refresh_log, get_api_usage_stats
from ai import analyze_with_ai, lookup_company_info, chat_with_agent
from context import prepare_context
from chart import create_hero_preview_figure
from refresh import run_refresh

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Rate limiting ─────────────────────────────────────────────────────────────
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],          # No global limit; set per-route below
    storage_uri='memory://',
)

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
        if not password or not auth or not hmac.compare_digest(auth.password, password):
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
@limiter.limit('20 per minute; 100 per hour')
def api_analyze():
    """Generate AI analysis for selected sectors and year range."""
    try:
        data = request.json or {}
        selected_sectors = data.get('sectors', [])
        year_min = data.get('year_min', 2021)
        year_max = data.get('year_max', 2025)
        pred_dict = data.get('pred_dict', None)

        # Load and prepare data
        df, _ = load_data_from_db()
        sector_data, valid_sectors = build_sector_data(df)

        # Validate sector input against known sectors
        valid_set = set(valid_sectors)
        selected_sectors = [s for s in selected_sectors if isinstance(s, str) and s in valid_set]

        # Get AI analysis
        analysis, forecast = analyze_with_ai(sector_data, selected_sectors, year_min, year_max, pred_dict)

        return jsonify({'analysis': analysis, 'forecast': forecast})

    except Exception:
        logger.exception('Fout in /api/analyze')
        return jsonify({'error': 'Er is een interne fout opgetreden.'}), 500


@app.route('/api/lookup-company', methods=['POST'])
@limiter.limit('10 per minute; 50 per hour')
def api_lookup_company():
    """Look up CBS classification for a given company name using AI."""
    try:
        data = request.json
        company_name = (data.get('company_name') or '').strip()
        if not company_name:
            return jsonify({'error': 'Geen bedrijfsnaam opgegeven'}), 400
        result = lookup_company_info(company_name)
        return jsonify(result)
    except Exception:
        logger.exception('Fout in /api/lookup-company')
        return jsonify({'error': 'Er is een interne fout opgetreden.'}), 500


@app.route('/api/chat', methods=['POST'])
@limiter.limit('30 per minute; 200 per hour')
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
    except Exception:
        logger.exception('Fout in /api/chat')
        return jsonify({'error': 'Er is een interne fout opgetreden.'}), 500


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


# ── Health check ─────────────────────────────────────────────────────────────
@app.route('/health')
def health():
    """Health check for Railway / uptime monitors."""
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')

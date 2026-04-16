"""Flask application for Dutch labour market absenteeism analysis."""
import hmac
import logging
import os
from functools import wraps

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response, jsonify, render_template, request
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from ai import analyze_with_ai, chat_with_agent, lookup_company_info
from chart import create_hero_preview_figure
from context import prepare_context
from db import (build_sector_data, get_api_usage_stats, get_refresh_log,
                init_admin_tables, load_data_from_db)
from refresh import run_refresh

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = Flask(__name__)

cache = Cache(app, config={
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 3600,   # 1 hour; invalidated earlier on refresh
})

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri='memory://',
)

# ── Startup ───────────────────────────────────────────────────────────────────
init_admin_tables()

_scheduler = BackgroundScheduler(daemon=True)
_scheduler.add_job(lambda: run_refresh('cbs'), 'cron', hour=3, minute=0,
                   id='nightly_cbs', misfire_grace_time=3600)
_scheduler.add_job(lambda: run_refresh('flu'), 'cron', hour=3, minute=30,
                   id='nightly_flu', misfire_grace_time=3600)
_scheduler.start()


# ── Auth ──────────────────────────────────────────────────────────────────────
def _require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        password = os.getenv('ADMIN_PASSWORD', '').strip()
        auth = request.authorization
        if not password or not auth or not hmac.compare_digest(auth.password, password):
            return Response('Toegang geweigerd', 401,
                            {'WWW-Authenticate': 'Basic realm="Admin"'})
        return f(*args, **kwargs)
    return decorated


# ── Pages ─────────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    df, _ = load_data_from_db()
    return render_template(
        'home.html',
        active_page='home',
        n_sectors=df['Sector'].nunique() if not df.empty else 0,
        min_year=int(df['Year'].min()) if not df.empty else 1996,
        max_year=int(df['Year'].max()) if not df.empty else 2025,
        hero_chart_html=create_hero_preview_figure(df) if not df.empty else '',
    )


@app.route('/tools')
def tools():
    return render_template('tools.html', active_page='tools')


@app.route('/tools/ziekteverzuim')
@cache.cached(key_prefix='ziekteverzuim_context')
def ziekteverzuim():
    df, pred_df = load_data_from_db()
    context = prepare_context(df, pred_df)
    context['active_page'] = 'ziekteverzuim'
    return render_template('ziekteverzuim.html', **context)


# ── API ───────────────────────────────────────────────────────────────────────
@app.route('/api/analyze', methods=['POST'])
@limiter.limit('20 per minute; 100 per hour')
def api_analyze():
    try:
        data = request.json or {}
        df, _ = load_data_from_db()
        sector_data, valid_sectors = build_sector_data(df)
        selected_sectors = [s for s in data.get('sectors', [])
                            if isinstance(s, str) and s in set(valid_sectors)]
        analysis, forecast = analyze_with_ai(
            sector_data, selected_sectors,
            data.get('year_min', 2021), data.get('year_max', 2025),
            data.get('pred_dict'),
        )
        return jsonify({'analysis': analysis, 'forecast': forecast})
    except Exception:
        logger.exception('Fout in /api/analyze')
        return jsonify({'error': 'Er is een interne fout opgetreden.'}), 500


@app.route('/api/lookup-company', methods=['POST'])
@limiter.limit('10 per minute; 50 per hour')
def api_lookup_company():
    try:
        data = request.json or {}
        company_name = (data.get('company_name') or '').strip()
        if not company_name:
            return jsonify({'error': 'Geen bedrijfsnaam opgegeven'}), 400
        return jsonify(lookup_company_info(company_name))
    except Exception:
        logger.exception('Fout in /api/lookup-company')
        return jsonify({'error': 'Er is een interne fout opgetreden.'}), 500


@app.route('/api/chat', methods=['POST'])
@limiter.limit('30 per minute; 200 per hour')
def api_chat():
    try:
        data = request.json or {}
        message = (data.get('message') or '').strip()
        if not message:
            return jsonify({'error': 'Geen bericht opgegeven'}), 400
        df, pred_df = load_data_from_db()
        reply = chat_with_agent(
            message,
            data.get('history') or [],
            df, pred_df,
            (data.get('active_sector') or '').strip() or None,
        )
        return jsonify({'reply': reply})
    except Exception:
        logger.exception('Fout in /api/chat')
        return jsonify({'error': 'Er is een interne fout opgetreden.'}), 500


# ── Admin ─────────────────────────────────────────────────────────────────────
@app.route('/admin')
@_require_admin
def admin():
    return render_template(
        'admin.html',
        refresh_log=get_refresh_log(limit=30),
        usage=get_api_usage_stats(),
        jobs=[{'id': j.id,
               'next_run': str(j.next_run_time)[:19] if j.next_run_time else '—'}
              for j in _scheduler.get_jobs()],
    )


@app.route('/admin/refresh', methods=['POST'])
@_require_admin
def admin_refresh():
    source = (request.json or {}).get('source', '').strip()
    if source not in ('cbs', 'flu'):
        return jsonify({'error': 'Ongeldige bron. Gebruik "cbs" of "flu".'}), 400
    return jsonify(run_refresh(source))


# ── Health ────────────────────────────────────────────────────────────────────
@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')

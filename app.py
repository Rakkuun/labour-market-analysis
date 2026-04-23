"""Flask application for Dutch labour market absenteeism analysis."""
import hmac
import logging
import os
from collections import defaultdict
from functools import wraps

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, Response, jsonify, render_template, request
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from ai import analyze_with_ai, chat_with_agent, compare_with_ai, lookup_company_info
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

_debug = os.getenv('FLASK_DEBUG', '0') == '1'
cache = Cache(app, config={
    'CACHE_TYPE': 'NullCache' if _debug else 'SimpleCache',
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


@app.route('/api/compare', methods=['POST'])
@limiter.limit('10 per minute; 50 per hour')
def api_compare():
    try:
        data = request.json or {}
        sector_levels = data.get('sector_levels') or {}
        own_quarters = data.get('own_quarters') or []

        df, pred_df = load_data_from_db()
        sector_data, valid_sectors = build_sector_data(df)
        valid_set = set(valid_sectors)

        # Find best matching sector: lowest granularity first (same logic as applyCompanyFilter JS)
        matched_sector = None
        for level in ['bedrijfsklasse', 'bedrijfstak', 'bedrijfssector']:
            val = (sector_levels.get(level) or '').strip()
            if val and val in valid_set:
                matched_sector = val
                break

        if not matched_sector:
            return jsonify({'error': f'Geen CBS-sectormatch gevonden in de dataset. Gevonden niveaus: {sector_levels}'}), 400

        from context import build_pred_dict
        pred_dict = build_pred_dict(pred_df)

        sector_quarters = sector_data[matched_sector]['quarters']
        sector_values   = sector_data[matched_sector]['values']
        last4_values    = sector_values[-4:]   if len(sector_values)   >= 4 else sector_values
        last4_quarters  = sector_quarters[-4:] if len(sector_quarters) >= 4 else sector_quarters
        sector_recent_avg = round(sum(last4_values) / len(last4_values), 2)

        # Actual national average per quarter (mean across all sectors)
        national_by_quarter = defaultdict(list)
        for s in valid_sectors:
            for q, v in zip(sector_data[s]['quarters'], sector_data[s]['values']):
                national_by_quarter[q].append(v)
        all_values = [v for vals in national_by_quarter.values() for v in vals]
        national_avg = round(sum(all_values) / len(all_values), 2) if all_values else None

        # Forecast national average per quarter (mean of all sector predictions)
        national_pred_by_quarter = defaultdict(list)
        for s, pd_entry in pred_dict.items():
            for q, v in zip(pd_entry['quarters'], pd_entry['values']):
                national_pred_by_quarter[q].append(v)

        # Sector actual and forecast lookups
        sector_by_quarter = dict(zip(sector_quarters, sector_values))
        sector_pred_by_quarter = {}
        if matched_sector in pred_dict:
            sector_pred_by_quarter = dict(zip(
                pred_dict[matched_sector]['quarters'],
                pred_dict[matched_sector]['values'],
            ))

        # Build per-quarter rows aligned to the user's own_quarters labels
        own_avg = None
        per_quarter = []
        for oq in own_quarters:
            if not isinstance(oq, dict):
                continue
            label   = str(oq.get('label') or '').strip()
            own_val = oq.get('value')
            if own_val is not None and not isinstance(own_val, (int, float)):
                own_val = None
            normalized = label.replace(' ', '-')  # "2026 Q1" → "2026-Q1"

            sv = sector_by_quarter.get(normalized)
            sv_forecast = False
            if sv is None and normalized in sector_pred_by_quarter:
                sv = round(float(sector_pred_by_quarter[normalized]), 2)
                sv_forecast = True
            elif sv is not None:
                sv = round(float(sv), 2)

            nat_vals = national_by_quarter.get(normalized, [])
            nv = round(sum(nat_vals) / len(nat_vals), 2) if nat_vals else None
            nv_forecast = False
            if nv is None:
                nat_pred_vals = national_pred_by_quarter.get(normalized, [])
                if nat_pred_vals:
                    nv = round(sum(nat_pred_vals) / len(nat_pred_vals), 2)
                    nv_forecast = True

            per_quarter.append({
                'label':               label,
                'own_value':           round(float(own_val), 2) if own_val is not None else None,
                'sector_value':        sv,
                'sector_is_forecast':  sv_forecast,
                'national_value':      nv,
                'national_is_forecast': nv_forecast,
            })

        # If no own_quarters provided, fall back to last 4 sector quarters
        if not per_quarter:
            for q, v in zip(last4_quarters, last4_values):
                nat_vals = national_by_quarter.get(q, [])
                nv = round(sum(nat_vals) / len(nat_vals), 2) if nat_vals else None
                per_quarter.append({
                    'label': q, 'own_value': None,
                    'sector_value': round(float(v), 2), 'sector_is_forecast': False,
                    'national_value': nv, 'national_is_forecast': False,
                })

        if own_quarters:
            vals = [q['value'] for q in own_quarters if isinstance(q.get('value'), (int, float))]
            if vals:
                own_avg = round(sum(vals) / len(vals), 2)

        analysis, forecast = compare_with_ai(
            sector=matched_sector,
            sector_data=sector_data,
            pred_dict=pred_dict,
            own_quarters=own_quarters,
            own_avg=own_avg,
            sector_recent_avg=sector_recent_avg,
            national_avg=national_avg,
        )

        return jsonify({
            'matched_sector':   matched_sector,
            'per_quarter':      per_quarter,
            'sector_recent_avg': sector_recent_avg,
            'national_avg':     national_avg,
            'own_avg':          own_avg,
            'analysis':         analysis,
            'forecast':         forecast,
        })
    except Exception:
        logger.exception('Fout in /api/compare')
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

"""
WattWise Backend — ALL values sourced directly from uploaded datasets.
15min_TOD.csv  : per-interval per-appliance kWh (70176 rows, 2024-01-01 to 2025-12-31)
Monthly.csv    : daily rows with monthly aggregates, bills, tariff info
"""

from flask import Flask, jsonify, render_template, send_from_directory, send_file
import pandas as pd
import numpy as np
import pickle
import os
import json

BASE = os.path.dirname(os.path.abspath(__file__))
print(f"[WattWise] Root: {BASE}")
print(f"[WattWise] Contents: {os.listdir(BASE)}")

# Flexible path detection for Render (handles flattened structure)
tpl_path = os.path.join(BASE, 'templates')
if not os.path.exists(tpl_path):
    print("[WattWise] 'templates' folder NOT FOUND, using root.")
    tpl_path = BASE
else:
    print(f"[WattWise] Templates found in folder: {os.listdir(tpl_path)}")

static_path = os.path.join(BASE, 'static')
if not os.path.exists(static_path):
    print("[WattWise] 'static' folder NOT FOUND, using root.")
    static_path = BASE

app = Flask(__name__, 
            static_folder=static_path, 
            template_folder=tpl_path)

# ─── Load & Pre-compute once at startup ───────────────────────────────────────
print("[WattWise] Loading datasets...")

# --- APPLIANCE_COLS must be defined BEFORE use in tod_dtypes / tod_cols ---
APPLIANCE_COLS = [
    'ac_kwh','fan_1_kwh','fan_2_kwh','fan_3_kwh','fan_4_kwh',
    'fridge_kwh','hrs_kwh','induction-stove_kwh','iron-box_kwh',
    'light_1_kwh','light_2_kwh','light_3_kwh','light_4_kwh','light_5_kwh',
    'mixi_kwh','tv_kwh','washing-machine_kwh','water-pump_kwh'
]

# --- TOD ---
# Optimization: Explicit dtypes reduce memory overhead and speed up parsing
tod_dtypes = {
    'timestamp': 'int64',
    'total_kwh': 'float64',
}
# Appliances are all float64
for c in APPLIANCE_COLS:
    tod_dtypes[c] = 'float64'

# Optimization: Load only required columns from TOD
tod_cols = ['timestamp', 'total_kwh'] + APPLIANCE_COLS
tod = pd.read_csv(
    os.path.join(BASE, '15min_TOD.csv'),
    dtype={k: v for k, v in tod_dtypes.items() if k in tod_cols},
    usecols=tod_cols
)
tod['ts']         = pd.to_datetime(tod['timestamp'], unit='s')
tod['hour']       = tod['ts'].dt.hour
tod['dow']        = tod['ts'].dt.dayofweek
tod['is_weekend'] = tod['dow'] >= 5
TOD_VALUES   = tod['total_kwh'].values.tolist()        # Use .values for faster conversion
# Memory Optimization: Generate TOD_TS only if needed, but keeping for now as it's used in dashboard
TOD_TS       = tod['ts'].dt.strftime('%Y-%m-%d %H:%M').tolist()
TOD_N        = len(tod)
print(f"[TOD] {TOD_N} rows | {tod['ts'].min()} → {tod['ts'].max()}")

APPLIANCE_DISPLAY = {
    'ac_kwh':               ('Air Conditioner',    '❄️'),
    'fan_1_kwh':            ('Fan 1',              '🌀'),
    'fan_2_kwh':            ('Fan 2',              '🌀'),
    'fan_3_kwh':            ('Fan 3',              '🌀'),
    'fan_4_kwh':            ('Fan 4',              '🌀'),
    'fridge_kwh':           ('Refrigerator',       '🧊'),
    'hrs_kwh':              ('Water Heater (HRS)',  '🚿'),
    'induction-stove_kwh':  ('Induction Stove',    '🍳'),
    'iron-box_kwh':         ('Iron Box',           '👔'),
    'light_1_kwh':          ('Light 1',            '💡'),
    'light_2_kwh':          ('Light 2',            '💡'),
    'light_3_kwh':          ('Light 3',            '💡'),
    'light_4_kwh':          ('Light 4',            '💡'),
    'light_5_kwh':          ('Light 5',            '💡'),
    'mixi_kwh':             ('Mixer/Grinder',       '🥣'),
    'tv_kwh':               ('Television',         '📺'),
    'washing-machine_kwh':  ('Washing Machine',    '🫧'),
    'water-pump_kwh':       ('Water Pump',         '💧'),
}

# Pre-compute dataset aggregates
HOURLY_AVG    = {int(h): round(float(v), 4) for h, v in tod.groupby('hour')['total_kwh'].mean().items()}
WDAY_HOURLY   = {int(h): round(float(v), 4) for h, v in tod[~tod['is_weekend']].groupby('hour')['total_kwh'].mean().items()}
WEND_HOURLY   = {int(h): round(float(v), 4) for h, v in tod[tod['is_weekend']].groupby('hour')['total_kwh'].mean().items()}

night_avg     = float(tod[tod['hour'].isin(range(0,6))]['total_kwh'].mean())
morning_avg   = float(tod[tod['hour'].isin(range(6,12))]['total_kwh'].mean())
afternoon_avg = float(tod[tod['hour'].isin(range(12,18))]['total_kwh'].mean())
evening_avg   = float(tod[tod['hour'].isin(range(18,24))]['total_kwh'].mean())
_tod_sum      = night_avg + morning_avg + afternoon_avg + evening_avg
NIGHT_PCT     = round(night_avg / _tod_sum * 100, 1)
MORNING_PCT   = round(morning_avg / _tod_sum * 100, 1)
AFTERNOON_PCT = round(afternoon_avg / _tod_sum * 100, 1)
EVENING_PCT   = round(evening_avg / _tod_sum * 100, 1)

WDAY_AVG = float(tod[~tod['is_weekend']]['total_kwh'].mean())
WEND_AVG = float(tod[tod['is_weekend']]['total_kwh'].mean())
OVERALL_AVG  = float(tod['total_kwh'].mean())
OVERALL_PEAK = float(tod['total_kwh'].max())
OVERALL_BASE = float(tod['total_kwh'].quantile(0.05))
OVERALL_STD  = float(tod['total_kwh'].std())

cv = OVERALL_STD / OVERALL_AVG if OVERALL_AVG > 0 else 0.5
CONSISTENCY   = round(max(0, min(100, 100 - cv * 60)), 1)

op_mask = tod['hour'].isin(list(range(22,24)) + list(range(0,6)))
op_avg  = float(tod[op_mask]['total_kwh'].mean())
on_avg  = float(tod[~op_mask]['total_kwh'].mean())
ENERGY_INDEP  = round(op_avg / (op_avg + on_avg) * 100, 1) if (op_avg + on_avg) > 0 else 0

# Appliance daily avgs from dataset (96 intervals * mean per interval)
APPLIANCE_DAILY = {}
for col in APPLIANCE_COLS:
    APPLIANCE_DAILY[col] = round(float(tod[col].mean()) * 96, 4)   # kWh/day

# Peak hours
sorted_h  = sorted(HOURLY_AVG.items(), key=lambda x: x[1], reverse=True)
PEAK_HOURS = [int(h) for h, _ in sorted_h[:3]]

print(f"[TOD] Hourly profile computed. Peak hour: {PEAK_HOURS[0]}:00")

# --- Monthly ---
monthly = pd.read_csv(os.path.join(BASE, 'Monthly.csv'))
monthly['date_parsed'] = pd.to_datetime(monthly['date'], dayfirst=True)
monthly['month_yr']    = monthly['date_parsed'].dt.to_period('M')

m_agg = monthly.groupby('month_yr').agg(
    kwh      = ('monthly_unit_kwh(Aggregate)', 'last'),
    bill     = ('monthly_bill(Aggregate)',      'last'),
    op_kwh   = ('OP_unit_kwh',  'sum'),
    pk_kwh   = ('PK_unit_kwh',  'sum'),
    nl_kwh   = ('NL_unit_kwh',  'sum'),
    temp     = ('temperature',  'mean'),
    residents= ('residents',    'mean'),
).reset_index().sort_values('month_yr').reset_index(drop=True)

m_agg['tariff'] = m_agg['bill'] / m_agg['kwh']

MONTHLY_TREND = [
    {'month': str(r['month_yr']), 'bill': round(float(r['bill']),2), 'kwh': round(float(r['kwh']),2)}
    for _, r in m_agg.tail(12).iterrows()
]
LAST_BILL  = float(m_agg['bill'].iloc[-1])
PREV_BILL  = float(m_agg['bill'].iloc[-2]) if len(m_agg) > 1 else LAST_BILL
LAST_KWH   = float(m_agg['kwh'].iloc[-1])
TARIFF     = round(float(m_agg['tariff'].iloc[-1]), 4)
RESIDENTS  = int(monthly['residents'].iloc[-1])
TOTAL_EQUIP= int(monthly['total_equipments'].iloc[-1])

pct_change = round((LAST_BILL - PREV_BILL) / PREV_BILL * 100, 2) if PREV_BILL > 0 else 0.0
trend_dir  = 'improving' if LAST_BILL < PREV_BILL else 'worsening'
trend_pct  = round(abs(LAST_BILL - PREV_BILL) / PREV_BILL * 100, 1) if PREV_BILL > 0 else 0.0

# 3-month projection (weighted moving avg from actual monthly bills)
proj_base = float(m_agg['bill'].tail(3).mean())
THREE_MONTH_PROJ = [round(proj_base * (1 + 0.015*i), 2) for i in range(1,4)]

print(f"[Monthly] {len(m_agg)} months | Last: ₹{LAST_BILL} | Tariff: ₹{TARIFF}/kWh")
print(f"[Monthly] Residents: {RESIDENTS} | Equipments: {TOTAL_EQUIP}")
# --- Seasonal Monthly Dataset ---
# ─── Seasonal Trend Processing ─────────────────────────────

seasonal_path = os.path.join(BASE, 'monthly1.csv')
seasonal = pd.read_csv(seasonal_path)

print("[Seasonal] Columns:", seasonal.columns.tolist())

# Normalize column names
seasonal.columns = seasonal.columns.str.strip()

# Create month labels
seasonal['label'] = seasonal['month'].astype(str) + '-' + seasonal['year'].astype(str)

# Build frontend payload
SEASONAL_TREND = []

try:
    seasonal = pd.read_csv(seasonal_path)
    seasonal.columns = seasonal.columns.str.strip()
    print("[WattWise] Successfully parsed monthly1.csv for UI Trend Graph.")
    
    for _, row in seasonal.iterrows():
        # Standardize single-digit months to standard two-digit strings (e.g., 1 -> "01")
        month_int = int(row['month'])
        month_str = f"{month_int:02d}"
        year_str = str(int(row['year']))
        
        # Format label to match standard "YYYY-MM" (e.g., "2020-01")
        frontend_label = f"{year_str}-{month_str}"
        
        SEASONAL_TREND.append({
            'month': frontend_label,
            'kwh': float(row['monthly_energy_kwh']),
            'bill': float(row['monthly_bill_rs'])
        })
except Exception as e:
    print(f"⚠️ [Graph Warning] Could not parse monthly1.csv for UI: {e}")
    # Fallback directly to m_agg data if the new file fails to read
    SEASONAL_TREND = [
        {'month': str(r['month_yr']), 'bill': round(float(r['bill']),2), 'kwh': round(float(r['kwh']),2)}
        for _, r in m_agg.iterrows()
    ]
# --- Model ---
model_path = os.path.join(BASE, 'electricity_model.pkl')
try:
    if os.path.exists(model_path):
        with open(model_path, 'rb') as f:
            MODEL = pickle.load(f)
        feat = np.array([[LAST_KWH, float(m_agg['op_kwh'].iloc[-1]),
                          float(m_agg['pk_kwh'].iloc[-1]), float(m_agg['temp'].iloc[-1])]])
        PREDICTED_BILL = round(float(MODEL.predict(feat)[0]), 2)
        print(f"[Model] Loaded. Predicted next bill: ₹{PREDICTED_BILL}")
    else:
        print("[Model] WARNING: electricity_model.pkl NOT found. Using trend estimate.")
        PREDICTED_BILL = round(proj_base * 1.03, 2)
except Exception as e:
    print(f"[Model] Error loading model: {e} — using trend estimate")
    PREDICTED_BILL = round(proj_base * 1.03, 2)

# Carbon footprint (0.82 kg CO₂/kWh — Indian grid factor)
CARBON_KG = round(LAST_KWH * 0.82, 1)

# Peer diff (simulated — no real neighbor data exists)
np.random.seed(99)
PEER_AVG = round(OVERALL_AVG * np.random.uniform(0.85, 1.15), 4)
PEER_DIFF = round((OVERALL_AVG - PEER_AVG) / PEER_AVG * 100, 1)

# Goals from real data
GOALS = [
    {'label': 'Monthly bill target',   'target': round(LAST_BILL * 0.9, 2),  'current': round(LAST_BILL, 2),    'unit': '₹'},
    {'label': 'Peak hour reduction',   'target': 25,                          'current': AFTERNOON_PCT,          'unit': '%'},
    {'label': 'Off-peak usage share',  'target': 30,                          'current': ENERGY_INDEP,           'unit': '%'},
    {'label': 'Consistency score',     'target': 80,                          'current': CONSISTENCY,            'unit': '/100'},
]

# Streaks derived from actual data
LOW_EVE_COUNT = int(tod[tod['hour'].isin(range(18,23))].groupby(tod['ts'].dt.date)['total_kwh'].mean().lt(OVERALL_AVG * 0.85).sum())
OP_MORN_COUNT = int(tod[tod['hour'].isin(range(5,8))].groupby(tod['ts'].dt.date)['total_kwh'].mean().lt(OVERALL_AVG).sum())
TOD_DAYS = int(tod['ts'].dt.date.nunique())

print("[WattWise] All pre-computations complete. Starting server...")

# ─── Routes ──────────────────────────────────────────────────────────────────
@app.route('/')
def home():
    return render_template(
        'index.html',
        last_bill=LAST_BILL,
        predicted_bill=round(PREDICTED_BILL, 2),
        goals=GOALS,
        tod_rows=TOD_N
    )
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/profile')
def profile():
    return render_template('profile.html')

@app.route('/api/status')
def status():
    return jsonify({'status': 'WattWise Running 🚀', 'tod_rows': TOD_N})

@app.route('/health')
def health():
    return "OK", 200

# ─── PWA Support (Serving from root for scope) ───────────────────────────────
@app.route('/sw.js')
def serve_sw():
    # Attempt to find sw.js in absolute locations for maximum reliability
    locs = [os.path.join(BASE, 'static', 'sw.js'), os.path.join(BASE, 'sw.js')]
    for loc in locs:
        if os.path.exists(loc):
            return send_file(loc, mimetype='application/javascript')
    return "[WattWise] Service Worker file not found", 404

@app.route('/manifest.json')
def serve_manifest():
    locs = [os.path.join(BASE, 'static', 'manifest.json'), os.path.join(BASE, 'manifest.json')]
    for loc in locs:
        if os.path.exists(loc):
            return send_file(loc, mimetype='application/json')
    return "[WattWise] Manifest file not found", 404

@app.route('/debug/ls')
def debug_ls():
    files = []
    for root, dirs, filenames in os.walk(BASE):
        for f in filenames:
            files.append(os.path.relpath(os.path.join(root, f), BASE))
    return jsonify({'base': BASE, 'files': files})

# ─── TOD series for looping graph ────────────────────────────────────────────
# Returns a WINDOW of real data starting from requested index
@app.route('/api/tod_window/<int:start_idx>')
def tod_window(start_idx):
    """Returns 96 consecutive points (24h) from the TOD dataset starting at start_idx.
    Loops around when end of dataset is reached."""
    window = 96   # 24h window shown on chart
    indices = [(start_idx + i) % TOD_N for i in range(window)]
    return jsonify({
        'start_idx': start_idx,
        'next_idx':  (start_idx + 1) % TOD_N,      # advance 1 interval (15 min)
        'total':     TOD_N,
        'values':    [round(TOD_VALUES[i], 4) for i in indices],
        'timestamps': [TOD_TS[i] for i in indices],
        'current_value': round(TOD_VALUES[start_idx], 4),
        'current_ts':    TOD_TS[start_idx],
    })

# ─── Dashboard ───────────────────────────────────────────────────────────────
@app.route('/api/dashboard')
def dashboard():
    try:
        # Latest value from dataset (last row of TOD)
        latest = round(TOD_VALUES[-1], 4)
        cost_per_hr = round(latest * 4 * TARIFF, 4)   # 15-min kWh * 4 = hourly kWh, * tariff = cost

        alerts = []
        if latest > OVERALL_AVG * 1.2:
            alerts.append({'type':'warning', 'msg': f'⚡ High Usage — Current {latest:.4f} kWh is {round((latest/OVERALL_AVG-1)*100,1)}% above dataset average'})
        if PREDICTED_BILL > LAST_BILL:
            pct = round((PREDICTED_BILL-LAST_BILL)/LAST_BILL*100,1)
            alerts.append({'type':'budget', 'msg': f'💸 Budget Warning — Predicted ₹{round(PREDICTED_BILL-LAST_BILL,0):.0f} higher (+{pct}%) than last month'})
        if latest > OVERALL_PEAK * 0.88:
            alerts.append({'type':'peak', 'msg': '🔴 Near Peak Load — Approaching dataset maximum reading'})
        if not alerts:
            alerts.append({'type':'ok', 'msg': '✅ All Systems Normal — Usage within expected dataset range'})

        # Appliance list from dataset
        equip = []
        for col in APPLIANCE_COLS:
            name, icon = APPLIANCE_DISPLAY[col]
            daily_kwh = APPLIANCE_DAILY[col]
            cost_day  = round(daily_kwh * TARIFF, 2)
            equip.append({
                'col': col, 'name': name, 'icon': icon,
                'daily_kwh':    round(daily_kwh, 4),
                'cost_per_day': cost_day,
                'monthly_kwh':  round(daily_kwh * 30, 3),
                'pct_of_total': round(daily_kwh / (OVERALL_AVG * 96) * 100, 1),
            })
        equip.sort(key=lambda x: x['daily_kwh'], reverse=True)
        next_month_val = round(THREE_MONTH_PROJ[0], 2) if THREE_MONTH_PROJ else round(PREDICTED_BILL, 2)
        return jsonify({
            # ── FROM DATASET ──
            'latest_kwh':           latest,
            'average_kwh':          round(OVERALL_AVG, 4),
            'peak_kwh':             round(OVERALL_PEAK, 4),
            'base_kwh':             round(OVERALL_BASE, 4),
            'load_std':             round(OVERALL_STD, 4),
            'last_month_bill':      LAST_BILL,
            'prev_month_bill':      PREV_BILL,
            'last_month_kwh':       LAST_KWH,
            'tariff_rate':          TARIFF,
            'residents':            RESIDENTS,
            'total_equipments':     TOTAL_EQUIP,
            'monthly_trend':        SEASONAL_TREND,
            'seasonal_trend':        SEASONAL_TREND,
            'hourly_avg':           HOURLY_AVG,
            'peak_hours':           PEAK_HOURS,
            # ── CALCULATED FROM DATASET ──
            'cost_per_hour':        cost_per_hr,
            'pct_change':           pct_change,
            'efficiency_score':     round(OVERALL_AVG / OVERALL_PEAK * 100, 1) if OVERALL_PEAK > 0 else 0,
            'carbon_footprint_kg':  CARBON_KG,
            'three_month_projection': THREE_MONTH_PROJ,
            'equipment':            equip,
            'alerts':               alerts,
            # ── MODEL PREDICTION ──
            'predicted_bill':       PREDICTED_BILL,
            'next_month_predicted': next_month_val,
            # ── TOD graph: start from index 0, client loops itself ──
            'tod_total':            TOD_N,
        })
    except Exception as e:
        print(f"[API ERROR] /api/dashboard: {e}")
        return jsonify({'error': str(e), 'msg': 'Failed to process dashboard data'}), 500

# ─── Profile ─────────────────────────────────────────────────────────────────
@app.route('/api/profile/<user_id>')
def user_profile(user_id):
    # Profile type from dataset percentages
    if NIGHT_PCT > 28:
        ptype = 'night_owl'; plabel = 'Night Owl 🦉'; pcolor = '#9b59b6'
        pdesc = f'Your dataset shows {NIGHT_PCT}% of usage happens midnight–6 AM. Classic night owl pattern — heavy overnight appliance usage.'
    elif MORNING_PCT > 28:
        ptype = 'early_bird'; plabel = 'Early Birdie 🐦'; pcolor = '#f39c12'
        pdesc = f'Your dataset shows {MORNING_PCT}% of usage in early morning hours. Iron box, induction stove and water heater dominate your mornings.'
    else:
        ptype = 'peak_scoobie'; plabel = 'Peak Scoobie 🕵️'; pcolor = '#e74c3c'
        pdesc = f'Your dataset shows peak usage ({AFTERNOON_PCT}%) in afternoon hours (12–18). AC, induction stove and fridge drive afternoon consumption.'

    # Suggestions from dataset patterns
    top3 = [APPLIANCE_DISPLAY[c][0] for c in sorted(APPLIANCE_DAILY, key=APPLIANCE_DAILY.get, reverse=True)[:3]]
    sug = []
    if APPLIANCE_DAILY['fridge_kwh'] > 2.0:
        sug.append(f"🧊 Fridge uses {APPLIANCE_DAILY['fridge_kwh']:.2f} kWh/day — highest single appliance. Check door seal and set to 4°C.")
    if APPLIANCE_DAILY['induction-stove_kwh'] > 1.0:
        sug.append(f"🍳 Induction Stove: {APPLIANCE_DAILY['induction-stove_kwh']:.2f} kWh/day. Batch-cook meals to reduce usage by ~20%.")
    if APPLIANCE_DAILY['ac_kwh'] > 0.5:
        sug.append(f"❄️ AC: {APPLIANCE_DAILY['ac_kwh']:.2f} kWh/day from your dataset. Set to 26°C — saves ~6% per degree increase.")
    if APPLIANCE_DAILY['water-pump_kwh'] > 0.5:
        sug.append(f"💧 Water Pump: {APPLIANCE_DAILY['water-pump_kwh']:.2f} kWh/day. Run only twice daily at off-peak hours (23:00 or 05:00).")
    if APPLIANCE_DAILY['iron-box_kwh'] > 0.5:
        sug.append(f"👔 Iron Box: {APPLIANCE_DAILY['iron-box_kwh']:.2f} kWh/day — batch iron weekly, not daily. Saves ~0.6 kWh/day.")
    ww_diff = abs(WEND_AVG - WDAY_AVG) / WDAY_AVG * 100 if WDAY_AVG > 0 else 0
    sug.append(f"📅 Weekend usage is {ww_diff:.1f}% {'higher' if WEND_AVG > WDAY_AVG else 'lower'} than weekdays (from dataset). {RESIDENTS} residents active.")
    if ptype == 'night_owl':
        sug.append(f"🌙 Night Owl tip: {NIGHT_PCT}% usage at night — schedule fan timers to turn off at 2 AM while sleeping.")
    elif ptype == 'early_bird':
        sug.append(f"🌅 Early Bird tip: Spread morning appliances — stagger induction stove and iron to avoid simultaneous peak.")
    else:
        sug.append(f"☀️ Afternoon Peak tip: {AFTERNOON_PCT}% load in 12–18 hrs. Pre-cool rooms before 12 PM to reduce AC run time.")

    # Streaks derived from actual data (pre-computed at startup)
    under_budget  = max(0, int((PREV_BILL - LAST_BILL) / (PREV_BILL * 0.05 + 1)))

    streaks = [
        {'label': f'Low-usage evenings (from {TOD_DAYS} days)',  'count': min(30, LOW_EVE_COUNT),  'icon': '🌙'},
        {'label': 'Off-peak mornings in dataset',                                        'count': min(30, OP_MORN_COUNT),  'icon': '☀️'},
        {'label': 'Under-budget months (recent)',                                        'count': min(6, under_budget),    'icon': '💰'},
    ]

    # Appliance list for profile (daily kWh from dataset)
    appliance_list = []
    for col in APPLIANCE_COLS:
        name, icon = APPLIANCE_DISPLAY[col]
        daily = APPLIANCE_DAILY[col]
        appliance_list.append({
            'col': col, 'name': name, 'icon': icon,
            'daily_kwh': round(daily, 4),
            'monthly_kwh': round(daily * 30, 3),
            'pct_of_total': round(daily / (OVERALL_AVG * 96) * 100, 1),
        })
    appliance_list.sort(key=lambda x: x['daily_kwh'], reverse=True)

    return jsonify({
        # ── ALL FROM DATASET ──
        'user_id':          user_id,
        'residents':        RESIDENTS,
        'total_equipments': TOTAL_EQUIP,
        'profile_type':     ptype,
        'profile_label':    plabel,
        'profile_color':    pcolor,
        'profile_desc':     pdesc,
        'night_pct':        NIGHT_PCT,
        'morning_pct':      MORNING_PCT,
        'afternoon_pct':    AFTERNOON_PCT,
        'evening_pct':      EVENING_PCT,
        'night_avg':        round(night_avg, 4),
        'morning_avg':      round(morning_avg, 4),
        'afternoon_avg':    round(afternoon_avg, 4),
        'evening_avg':      round(evening_avg, 4),
        'weekday_avg':      round(WDAY_AVG, 4),
        'weekend_avg':      round(WEND_AVG, 4),
        'wday_hourly':      [round(WDAY_HOURLY.get(h, WDAY_AVG), 4) for h in range(24)],
        'wend_hourly':      [round(WEND_HOURLY.get(h, WEND_AVG), 4) for h in range(24)],
        'hourly_profile':   HOURLY_AVG,
        'consistency_score': CONSISTENCY,
        'energy_independence': ENERGY_INDEP,
        'trend_direction':  trend_dir,
        'trend_pct':        trend_pct,
        'your_avg_kwh':     round(OVERALL_AVG, 4),
        'seasonal_trend':    SEASONAL_TREND,
        'monthly_trend':    SEASONAL_TREND,
        'last_month_kwh':   LAST_KWH,
        'last_month_bill':  LAST_BILL,
        'appliance_list':   appliance_list,
        'suggestions':      sug,
        'streaks':          streaks,
        'goals':            GOALS,
        # ── SIMULATED (no real peer data in dataset) ──
        'peer_avg_kwh':     PEER_AVG,
        'peer_diff':        PEER_DIFF,
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

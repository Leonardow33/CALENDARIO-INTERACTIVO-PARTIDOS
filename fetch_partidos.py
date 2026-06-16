"""
fetch_partidos.py
Jala partidos de fútbol desde football-data.org, convierte UTC → hora Perú,
y actualiza partidos.json preservando los partidos de tenis existentes.

Uso:
    pip install requests
    python fetch_partidos.py
"""

import requests
import json
import os
from datetime import datetime, timedelta, timezone

# ── CONFIGURACIÓN ──────────────────────────────────────────────────────────
FOOTBALL_DATA_KEY = '68eeda917e7d419ba6c3d1c871aaed4e'
PERU_OFFSET_HOURS = -5  # UTC-5

# Competencias a incluir: código football-data.org → nombre en el widget
COMPETITIONS = {
    'WC':  'Mundial 2026',
    'CLI': 'Copa Libertadores',
    'CSA': 'Copa Sudamericana',
    'PD':  'La Liga',
    'PL':  'Premier League',
    'BL1': 'Bundesliga',
    'SA':  'Serie A',
    'FL1': 'Ligue 1',
}

# Equipos que marcan un partido como "importante" (estrella ⭐)
IMPORTANT_TEAMS = {
    # Sudamérica
    'Argentina', 'Brazil', 'Colombia', 'Uruguay', 'Peru', 'Chile', 'Ecuador',
    'Bolivia', 'Paraguay', 'Venezuela',
    # Europa top
    'Spain', 'France', 'Germany', 'England', 'Portugal', 'Italy',
    'Netherlands', 'Belgium', 'Croatia',
}

MONTHS_ES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
MONTHS_NUM = {m: i+1 for i, m in enumerate(MONTHS_ES)}

# ── HELPERS ────────────────────────────────────────────────────────────────
def utc_to_peru(utc_str):
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    return dt + timedelta(hours=PERU_OFFSET_HOURS)

def format_day(dt):
    return f"{dt.day} {MONTHS_ES[dt.month - 1]}"

def format_time(dt):
    h, m = dt.hour, dt.minute
    ampm = 'AM' if h < 12 else 'PM'
    h12  = h % 12 or 12
    return f"{h12}:{m:02d} {ampm}"

def sort_key(match):
    """Clave de ordenamiento: (mes, día, hora24, minuto)"""
    parts   = match['day'].split()
    day_num = int(parts[0])
    mon_num = MONTHS_NUM.get(parts[1], 0)
    tp      = match['time'].split()
    hh, mm  = map(int, tp[0].split(':'))
    ampm    = tp[1]
    if ampm == 'PM' and hh != 12: hh += 12
    if ampm == 'AM' and hh == 12: hh  =  0
    return (mon_num, day_num, hh, mm)

def get_week_range():
    today  = datetime.now(timezone.utc).date()
    monday = today - timedelta(days=today.weekday())  # 0=lunes
    sunday = monday + timedelta(days=6)
    return monday, sunday

# ── FETCH ──────────────────────────────────────────────────────────────────
def fetch_matches():
    monday, sunday = get_week_range()
    headers = {'X-Auth-Token': FOOTBALL_DATA_KEY}
    params  = {
        'dateFrom': monday.isoformat(),
        'dateTo':   sunday.isoformat(),
    }
    resp = requests.get(
        'https://api.football-data.org/v4/matches',
        headers=headers,
        params=params,
        timeout=15
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get('matches', [])

# ── CONSTRUIR ENTRADAS ─────────────────────────────────────────────────────
def build_football_entries(raw_matches):
    entries = []
    for m in raw_matches:
        comp_code = m.get('competition', {}).get('code', '')
        liga      = COMPETITIONS.get(comp_code)
        if not liga:
            continue

        utc_date = m.get('utcDate', '')
        if not utc_date:
            continue

        dt_peru = utc_to_peru(utc_date)
        home    = (m.get('homeTeam') or {}).get('shortName') or (m.get('homeTeam') or {}).get('name', '')
        away    = (m.get('awayTeam') or {}).get('shortName') or (m.get('awayTeam') or {}).get('name', '')
        venue   = m.get('venue') or ''

        entry = {
            'day':   format_day(dt_peru),
            'liga':  liga,
            'home':  home,
            'away':  away,
            'time':  format_time(dt_peru),
            'venue': venue,
            'sport': 'futbol',
        }

        if home in IMPORTANT_TEAMS or away in IMPORTANT_TEAMS:
            entry['importante'] = True

        entries.append(entry)

    return entries

# ── MAIN ───────────────────────────────────────────────────────────────────
def main():
    json_path = os.path.join(os.path.dirname(__file__), 'partidos.json')

    print('Fetching football-data.org...')
    try:
        raw = fetch_matches()
    except requests.HTTPError as e:
        print(f'Error HTTP {e.response.status_code}: {e.response.text}')
        return
    except Exception as e:
        print(f'Error de conexión: {e}')
        return

    print(f'  {len(raw)} partidos en la API esta semana')

    football_entries = build_football_entries(raw)
    print(f'  {len(football_entries)} en competencias seleccionadas')

    # Preservar tenis existentes
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        tenis_entries = [m for m in existing.get('matches', []) if m.get('sport') == 'tenis']
        print(f'  {len(tenis_entries)} partidos de tenis preservados')
    except Exception:
        tenis_entries = []
        print('  partidos.json no encontrado — se crea desde cero')

    all_matches = sorted(football_entries + tenis_entries, key=sort_key)

    today  = datetime.now().strftime('%Y-%m-%d')
    monday, sunday = get_week_range()
    output = {
        '_actualizado': today,
        '_semana':      f"{monday.isoformat()} / {sunday.isoformat()}",
        '_nota':        'Fútbol: football-data.org UTC→Perú (auto). Tenis: manual.',
        'matches':      all_matches,
    }

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    futbol_imp = sum(1 for m in football_entries if m.get('importante'))
    print(f'\npartidos.json actualizado:')
    print(f'  {len(football_entries)} fútbol ({futbol_imp} importantes) + {len(tenis_entries)} tenis')
    print(f'  Total: {len(all_matches)} partidos')

if __name__ == '__main__':
    main()

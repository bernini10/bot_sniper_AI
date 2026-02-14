from flask import Flask, render_template, jsonify, send_from_directory
import json
import os
import ccxt
import time
import sqlite3
from datetime import datetime, timedelta
from lib_utils import JsonManager

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configs
WATCHLIST_FILE = os.path.join(BASE_DIR, 'watchlist.json')
HISTORY_FILE = os.path.join(BASE_DIR, 'trades_history.json')
CLOSED_PNL_CACHE = os.path.join(BASE_DIR, 'closed_pnl_cache.json')
CACHE_MAX_AGE = 24 * 3600  # 24 horas
watchlist_mgr = JsonManager(WATCHLIST_FILE)


def fetch_closed_pnl_from_bybit():
    """Busca todos os trades fechados dos últimos 30 dias via Bybit API"""
    secrets = get_secrets()
    if not secrets.get('BYBIT_API_KEY'):
        return None
    
    try:
        exchange = ccxt.bybit({
            'apiKey': secrets['BYBIT_API_KEY'],
            'secret': secrets['BYBIT_SECRET'],
            'options': {'defaultType': 'linear'}
        })
        
        all_trades = []
        cursor = ''
        
        for _ in range(50):  # max 50 pages (5000 trades)
            params = {'category': 'linear', 'limit': 100}
            if cursor:
                params['cursor'] = cursor
            
            result = exchange.private_get_v5_position_closed_pnl(params)
            trades = result['result']['list']
            if not trades:
                break
            
            # Filtrar últimos 30 dias
            cutoff_ms = (time.time() - 30 * 86400) * 1000
            for t in trades:
                if int(t['updatedTime']) >= cutoff_ms:
                    all_trades.append({
                        'symbol': t['symbol'],
                        'side': t['side'],
                        'pnl': float(t['closedPnl']),
                        'qty': float(t.get('qty', 0)),
                        'entry_price': float(t.get('avgEntryPrice', 0)),
                        'exit_price': float(t.get('avgExitPrice', 0)),
                        'leverage': t.get('leverage', '1'),
                        'closed_at': int(t['updatedTime']),
                        'order_type': t.get('orderType', ''),
                    })
                else:
                    # Trades mais antigos que 30 dias, parar
                    cursor = ''
                    break
            
            cursor = result['result'].get('nextPageCursor', '')
            if not cursor:
                break
            time.sleep(0.15)
        
        # Ordenar por data (mais recente primeiro)
        all_trades.sort(key=lambda x: x['closed_at'], reverse=True)
        
        # Salvar cache
        cache = {
            'updated_at': time.time(),
            'trades': all_trades
        }
        with open(CLOSED_PNL_CACHE, 'w') as f:
            json.dump(cache, f)
        
        print(f"[CACHE] Bybit closed PnL atualizado: {len(all_trades)} trades (30d)")
        return all_trades
        
    except Exception as e:
        print(f"Erro fetch closed PnL: {e}")
        return None


def get_closed_trades():
    """Retorna trades fechados do cache (atualiza se > 24h)"""
    # Tentar ler cache
    if os.path.exists(CLOSED_PNL_CACHE):
        try:
            with open(CLOSED_PNL_CACHE, 'r') as f:
                cache = json.load(f)
            age = time.time() - cache.get('updated_at', 0)
            if age < CACHE_MAX_AGE:
                return cache.get('trades', [])
            print(f"[CACHE] Expirado ({age/3600:.1f}h). Atualizando...")
        except Exception as e:
            print(f"Erro lendo cache: {e}")
    
    # Cache inexistente ou expirado — buscar da Bybit
    trades = fetch_closed_pnl_from_bybit()
    return trades if trades is not None else []

def get_secrets():
    secrets = {}
    try:
        path_env = os.path.join(BASE_DIR, '.env')
        if os.path.exists(path_env):
            with open(path_env, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, val = line.strip().split('=', 1)
                        secrets[key] = val
    except: pass
    return secrets

# LANDING PAGE (rota principal)
@app.route('/')
def index():
    return render_template('index.html')

# DASHBOARD (aba secundária)
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/stats')
def stats():
    secrets = get_secrets()
    data = {
        'equity': 0, 
        'available': 0, 
        'pnl_today': 0,
        'pnl_unrealized': 0,
        'open_positions': [],
        'active_count': 0
    }
    
    if secrets.get('BYBIT_API_KEY'):
        try:
            exchange = ccxt.bybit({
                'apiKey': secrets['BYBIT_API_KEY'],
                'secret': secrets['BYBIT_SECRET'],
                'options': {'defaultType': 'linear'}
            })
            
            # Balance
            bal = exchange.fetch_balance()
            data['equity'] = bal['USDT']['total']
            data['available'] = bal['USDT']['free']
            
            # Posições Abertas + PnL Unrealized
            positions = exchange.fetch_positions()
            pnl_total = 0
            
            for p in positions:
                contracts = float(p.get('contracts') or 0)
                if contracts > 0:
                    pnl_unreal = float(p.get('unrealizedPnl') or 0)
                    pnl_total += pnl_unreal
                    
                    data['open_positions'].append({
                        'symbol': p['symbol'],
                        'side': p['side'],
                        'size': contracts,
                        'entry': float(p.get('entryPrice') or 0),
                        'pnl': pnl_unreal,
                        'pnl_pct': float(p.get('percentage') or 0),
                        'leverage': p.get('leverage', 1)
                    })
            
            data['pnl_unrealized'] = pnl_total
            data['active_count'] = len(data['open_positions'])
            data['pnl_today'] = pnl_total  # Simplificação: PnL Today = Unrealized
                
        except Exception as e:
            print(f"Erro API Bybit: {e}")
            
    return jsonify(data)

@app.route('/api/watchlist')
def get_watchlist():
    wl = watchlist_mgr.read()
    if not wl: return jsonify([])
    
    # Adicionar preço atual para calcular distancia
    secrets = get_secrets()
    if secrets.get('BYBIT_API_KEY'):
        try:
            exchange = ccxt.bybit({
                'apiKey': secrets['BYBIT_API_KEY'], 
                'secret': secrets['BYBIT_SECRET']
            })
            
            if wl.get('pares'):
                symbols = [p['symbol'] for p in wl['pares']]
                try:
                    tickers = exchange.fetch_tickers(symbols)
                    for p in wl['pares']:
                        sym = p['symbol']
                        if sym in tickers:
                            p['current_price'] = tickers[sym]['last']
                            # Calc % distance
                            neckline = float(p.get('neckline', 0))
                            if neckline > 0:
                                dist = abs(p['current_price'] - neckline) / p['current_price'] * 100
                                p['dist_pct'] = round(dist, 2)
                except Exception as e:
                    print(f"Erro fetch tickers: {e}")
        except: pass
            
    return jsonify(wl.get('pares', []))

@app.route('/api/history')
def get_history():
    """
    Retorna trades fechados dos últimos 30 dias (Bybit closed PnL, cache 24h).
    """
    trades = get_closed_trades()
    
    if trades:
        # Calcular cumulative_pnl para o gráfico (do mais antigo pro mais recente)
        sorted_trades = sorted(trades, key=lambda x: x['closed_at'])
        cumulative = 0
        for t in sorted_trades:
            cumulative += t['pnl']
            t['cumulative_pnl'] = round(cumulative, 4)
            # Formatar data
            t['closed_at_str'] = datetime.fromtimestamp(t['closed_at'] / 1000).strftime('%d/%m %H:%M')
            t['status'] = 'WIN' if t['pnl'] > 0 else 'LOSS'
        
        # Retornar na ordem cronológica (mais antigo primeiro) para o gráfico
        return jsonify(sorted_trades)
    
    return jsonify([])

@app.route('/api/winrate')
def get_winrate():
    """Calcula win rate a partir dos trades fechados na Bybit (últimos 30 dias)"""
    try:
        trades = get_closed_trades()
        
        if not trades:
            return jsonify({'winrate': 0, 'wins': 0, 'losses': 0, 'total': 0, 'total_pnl': 0})
        
        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        total = len(trades)
        losses = total - wins
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        winrate = (wins / total * 100) if total > 0 else 0
        
        return jsonify({
            'winrate': round(winrate, 1),
            'wins': wins,
            'losses': losses,
            'total': total,
            'total_pnl': round(total_pnl, 4)
        })
    except Exception as e:
        print(f"Erro calc winrate: {e}")
        return jsonify({'winrate': 0, 'wins': 0, 'losses': 0, 'total': 0, 'total_pnl': 0})

@app.route('/api/logs')
def get_logs():
    log_data = []
    files = ['scanner_bybit.log', 'monitor_bybit.log', 'executor_bybit.log', 'vision_alerts.log']
    
    for log_file in files:
        path = os.path.join(BASE_DIR, log_file)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[-20:]
                    for line in lines:
                        log_data.append(f"[{log_file.split('_')[0].upper()}] {line.strip()}")
            except: pass
    
    return jsonify(log_data[-50:])

@app.route('/api/market')
def get_market():
    """
    Retorna análise de mercado (BTC.D + Cenário)
    Dados vêm do webhook do TradingView
    """
    BTCD_FILE = os.path.join(BASE_DIR, 'btcd_data.json')
    
    try:
        # Ler dados do BTC.D (webhook)
        if os.path.exists(BTCD_FILE):
            with open(BTCD_FILE, 'r') as f:
                btcd_data = json.load(f)
            
            # Calcular idade dos dados
            age_seconds = time.time() - btcd_data.get('timestamp', 0)
            age_minutes = age_seconds / 60
            
            # Determinar cenário (simplificado, sem BTC trend aqui)
            # Idealmente usaria get_market_analysis da lib_utils, mas evitando dependência de exchange
            btcd_direction = btcd_data.get('direction', 'NEUTRAL')
            btcd_value = btcd_data.get('btc_d_value', 0)
            change_pct = btcd_data.get('change_pct', 0)
            
            # Cenário simplificado (só baseado em BTC.D)
            if btcd_direction == 'LONG':
                scenario_text = "BTC.D Subindo"
                scenario_color = "text-red-400"
                longs_status = "❌ Desfavorável"
                shorts_status = "✅ Favorável"
                scenario_advice = "Dinheiro indo para BTC. Evite LONGs em alts."
            elif btcd_direction == 'SHORT':
                scenario_text = "BTC.D Caindo"
                scenario_color = "text-green-400"
                longs_status = "✅ Favorável"
                shorts_status = "⚠️ Neutro"
                scenario_advice = "Dinheiro saindo do BTC. LONGs em alts favorecidos."
            else:
                scenario_text = "BTC.D Lateral"
                scenario_color = "text-yellow-400"
                longs_status = "⚠️ Neutro"
                shorts_status = "⚠️ Neutro"
                scenario_advice = "Mercado lateral. Alts seguem BTC."
            
            return jsonify({
                'btcd_value': btcd_value,
                'btcd_direction': btcd_direction,
                'change_pct': change_pct,
                'age_minutes': round(age_minutes, 1),
                'scenario_text': scenario_text,
                'scenario_color': scenario_color,
                'longs_status': longs_status,
                'shorts_status': shorts_status,
                'scenario_advice': scenario_advice,
                'source': 'TradingView Premium',
                'last_update': btcd_data.get('datetime', 'N/A')
            })
        else:
            # Arquivo não existe ainda
            return jsonify({
                'btcd_value': 0,
                'btcd_direction': 'WAITING',
                'change_pct': 0,
                'age_minutes': 0,
                'scenario_text': 'Aguardando dados...',
                'scenario_color': 'text-gray-400',
                'longs_status': '⏳ Aguardando',
                'shorts_status': '⏳ Aguardando',
                'scenario_advice': 'Configurando webhook do TradingView...',
                'source': 'TradingView Premium',
                'last_update': 'N/A'
            })
    except Exception as e:
        print(f"Erro ao ler market data: {e}")
        return jsonify({
            'btcd_value': 0,
            'btcd_direction': 'ERROR',
            'change_pct': 0,
            'age_minutes': 0,
            'scenario_text': 'Erro ao carregar',
            'scenario_color': 'text-red-400',
            'longs_status': '❌ Erro',
            'shorts_status': '❌ Erro',
            'scenario_advice': str(e),
            'source': 'Error',
            'last_update': 'N/A'
        })


@app.route('/api/vision/logs')
def get_vision_logs():
    try:
        log_path = os.path.join(BASE_DIR, 'vision.log')
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                lines = f.readlines()[-20:]  # Last 20 lines
            return jsonify({'logs': [l.strip() for l in lines]})
        return jsonify({'logs': ['Waiting for vision logs...']})
    except Exception as e:
        return jsonify({'logs': [f'Error reading logs: {str(e)}']})

@app.route('/api/vision/stats')
def get_vision_stats():
    from datetime import datetime
    try:
        import sqlite3
        db_path = os.path.join(BASE_DIR, 'sniper_brain.db')
        if not os.path.exists(db_path):
            return jsonify({'recent': [], 'stats': {'total': 0, 'valid': 0, 'invalid': 0}})
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Recent Validations
        c.execute("SELECT symbol, pattern_detected, ai_verdict, ai_confidence, timestamp_detection FROM raw_samples WHERE status='PROCESSED' ORDER BY id DESC LIMIT 5")
        recent = []
        for row in c.fetchall():
            r = dict(row)
            # Validação e formatação segura
            try:
                if r.get('timestamp_detection'):
                    dt = datetime.fromtimestamp(r['timestamp_detection'])
                    r['timestamp_formatted'] = dt.strftime('%d/%m/%Y %H:%M:%S')
                else:
                    r['timestamp_formatted'] = 'N/A'
            except:
                r['timestamp_formatted'] = 'N/A'
            
            # Garantir que campos críticos existem
            r.setdefault('symbol', 'UNKNOWN')
            r.setdefault('pattern_detected', 'N/A')
            r.setdefault('ai_verdict', 'PENDING')
            r.setdefault('ai_confidence', 0.0)
            
            recent.append(r)
        
        # Stats
        c.execute("SELECT COUNT(*) as total FROM raw_samples")
        total = c.fetchone()['total']
        c.execute("SELECT COUNT(*) as valid FROM raw_samples WHERE ai_verdict='VALID'")
        valid = c.fetchone()['valid']
        c.execute("SELECT COUNT(*) as invalid FROM raw_samples WHERE ai_verdict='INVALID'")
        invalid = c.fetchone()['invalid']
        
        conn.close()
        return jsonify({
            'recent': recent,
            'stats': {'total': total, 'valid': valid, 'invalid': invalid}
        })
    except Exception as e:
        print(f"Vision DB Error: {e}")
        return jsonify({'error': str(e), 'recent': [], 'stats': {}})



@app.route('/api/vision/alerts')
def get_vision_alerts():
    """Retorna alertas e validações pós-entrada do Vision AI"""
    try:
        alert_file = os.path.join(BASE_DIR, 'vision_alerts.log')
        if not os.path.exists(alert_file):
            return jsonify({'alerts': []})
        with open(alert_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-30:]  # Últimas 30 linhas
        return jsonify({'alerts': [l.strip() for l in lines if l.strip()]})
    except Exception as e:
        return jsonify({'alerts': [], 'error': str(e)})

@app.route('/brain_images/<path:filename>')
def serve_brain_image(filename):
    """Serve imagens geradas pelo Vision Validator"""
    return send_from_directory(os.path.join(BASE_DIR, 'brain_images'), filename)

@app.route('/api/vision/analysis')
def get_vision_analysis():
    """Retorna análises completas da IA com imagens, reasoning e confidence"""
    try:
        db_path = os.path.join(BASE_DIR, 'sniper_brain.db')
        if not os.path.exists(db_path):
            return jsonify({'analyses': []})
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("""
            SELECT id, symbol, timeframe, pattern_detected, direction,
                   ai_verdict, ai_confidence, ai_reasoning, image_path, status
            FROM raw_samples 
            WHERE status = 'PROCESSED'
            ORDER BY id DESC 
            LIMIT 20
        """)
        
        analyses = []
        for row in c.fetchall():
            r = dict(row)
            # Converter image_path para URL servível
            if r.get('image_path'):
                img_file = os.path.basename(r['image_path'])
                r['image_url'] = f"/brain_images/{img_file}"
            else:
                r['image_url'] = None
            del r['image_path']
            analyses.append(r)
        
        conn.close()
        return jsonify({'analyses': analyses})
    except Exception as e:
        print(f"Vision analysis error: {e}")
        return jsonify({'analyses': [], 'error': str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)

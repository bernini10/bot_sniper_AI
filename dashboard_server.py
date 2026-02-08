from flask import Flask, render_template, jsonify
import json
import os
import ccxt
import time
from datetime import datetime, timedelta
from lib_utils import JsonManager

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configs
WATCHLIST_FILE = os.path.join(BASE_DIR, 'watchlist.json')
HISTORY_FILE = os.path.join(BASE_DIR, 'trades_history.json')
MOCK_HISTORY_FILE = os.path.join(BASE_DIR, 'mock_history.json')
watchlist_mgr = JsonManager(WATCHLIST_FILE)

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
    Busca histórico - usa mock se não houver trades reais
    """
    history_data = []
    
    # Tentar usar mock history primeiro (para ter dados no dashboard)
    try:
        if os.path.exists(MOCK_HISTORY_FILE):
            with open(MOCK_HISTORY_FILE, 'r') as f:
                history_data = json.load(f)
                print(f"Usando mock history: {len(history_data)} trades")
                return jsonify(history_data)
    except Exception as e:
        print(f"Erro lendo mock history: {e}")
    
    # Fallback: tentar API Bybit (para quando houver trades reais)
    secrets = get_secrets()
    if secrets.get('BYBIT_API_KEY'):
        try:
            exchange = ccxt.bybit({
                'apiKey': secrets['BYBIT_API_KEY'],
                'secret': secrets['BYBIT_SECRET'],
                'options': {'defaultType': 'linear'}
            })
            
            # Buscar trades fechados nos últimos 30 dias
            now = datetime.now()
            since = now - timedelta(days=30)
            since_ts = int(since.timestamp() * 1000)
            
            trades = exchange.fetch_my_trades(since=since_ts, limit=200)
            
            if len(trades) > 0:
                print(f"API Bybit retornou {len(trades)} trades")
                # Processar trades reais (código anterior)
                # ...
                return jsonify(history_data)
        except Exception as e:
            print(f"Erro fetch Bybit trades: {e}")
    
    return jsonify(history_data)

@app.route('/api/winrate')
def get_winrate():
    """Calcula win rate do histórico"""
    try:
        history_data = []
        
        # Usar mock history
        if os.path.exists(MOCK_HISTORY_FILE):
            with open(MOCK_HISTORY_FILE, 'r') as f:
                history_data = json.load(f)
        
        if not history_data or len(history_data) == 0:
            return jsonify({'winrate': 0, 'wins': 0, 'losses': 0, 'total': 0})
        
        wins = sum(1 for t in history_data if t.get('pnl', 0) > 0)
        total = len(history_data)
        losses = total - wins
        winrate = (wins / total * 100) if total > 0 else 0
        
        return jsonify({
            'winrate': round(winrate, 1),
            'wins': wins,
            'losses': losses,
            'total': total
        })
    except Exception as e:
        print(f"Erro calc winrate: {e}")
        return jsonify({'winrate': 0, 'wins': 0, 'losses': 0, 'total': 0})

@app.route('/api/logs')
def get_logs():
    log_data = []
    files = ['scanner_bybit.log', 'monitor_bybit.log', 'executor_bybit.log']
    
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)

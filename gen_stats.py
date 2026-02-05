import json
import os
import time
import ccxt
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST = os.path.join(BASE_DIR, 'watchlist.json')
STATS_FILE = '/var/www/liquidation-bot/stats.json'
TRADES_HISTORY = os.path.join(BASE_DIR, 'trades_history.json')

def carregar_segredos():
    segredos = {}
    try:
        env_path = os.path.join(BASE_DIR, '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, val = line.strip().split('=', 1)
                        segredos[key] = val
    except: pass
    return segredos

def get_exchange():
    secrets = carregar_segredos()
    return ccxt.bybit({
        'apiKey': secrets.get('BYBIT_API_KEY'),
        'secret': secrets.get('BYBIT_SECRET'),
        'options': {'defaultType': 'linear'}
    })

def get_balance(exchange):
    try:
        bal = exchange.fetch_balance()
        return {"free": round(bal['USDT']['free'], 2), "total": round(bal['USDT']['total'], 2)}
    except Exception as e:
        return {"free": 0, "total": 0, "error": str(e)}

def get_active_trades(exchange):
    try:
        positions = exchange.fetch_positions()
        active = []
        for p in positions:
            if float(p['contracts']) > 0:
                entry = float(p['entryPrice']) if p['entryPrice'] else 0
                pnl = float(p['unrealizedPnl']) if p['unrealizedPnl'] else 0
                notional = float(p['notional']) if p['notional'] else 0
                roi = (pnl / notional * 100) if notional > 0 else 0
                active.append({
                    "symbol": p['symbol'],
                    "side": p['side'].upper(),
                    "size": float(p['contracts']),
                    "entry_price": entry,
                    "current_pnl": round(pnl, 4),
                    "roi_percent": round(roi, 2),
                    "leverage": p.get('leverage', 10)
                })
        return active
    except Exception as e:
        print(f"Erro ao buscar posicoes: {e}")
        return []

def load_trades_history():
    try:
        if os.path.exists(TRADES_HISTORY):
            with open(TRADES_HISTORY, 'r') as f:
                return json.load(f)
    except: pass
    return []

def get_mode():
    try:
        mode_file = os.path.join(BASE_DIR, 'config_mode.json')
        if os.path.exists(mode_file):
            with open(mode_file, 'r') as f:
                return json.load(f).get('mode', 'MANUAL')
    except: pass
    return 'MANUAL'

def loop():
    exchange = None
    last_positions = {}
    
    print(">>> Dashboard Stats Iniciado <<<")
    
    while True:
        try:
            # Reconecta exchange se necessario
            if exchange is None:
                try:
                    exchange = get_exchange()
                    exchange.load_markets()
                except Exception as e:
                    print(f"Erro ao conectar exchange: {e}")
                    exchange = None
            
            data = {
                "status": "ONLINE",
                "updated_at": str(datetime.now()),
                "mode": get_mode(),
                "balance": {"free": 0, "total": 0},
                "signals": [],
                "active_trades": [],
                "closed_trades": load_trades_history()[-10:]  # Ultimos 10
            }
            
            # Processos
            scan_on = os.system("pgrep -f bot_scanner.py > /dev/null 2>&1") == 0
            data["scanner"] = "RUNNING" if scan_on else "STOPPED"
            
            # Saldo e Trades Ativos
            if exchange:
                data["balance"] = get_balance(exchange)
                data["active_trades"] = get_active_trades(exchange)
                
                # Detectar trades fechados (comparando com estado anterior)
                current_symbols = {t['symbol'] for t in data["active_trades"]}
                for sym, old_trade in list(last_positions.items()):
                    if sym not in current_symbols:
                        # Trade foi fechado! Registrar no historico
                        closed_trade = {
                            "symbol": sym,
                            "side": old_trade.get('side', 'UNKNOWN'),
                            "entry_price": old_trade.get('entry_price', 0),
                            "final_pnl": old_trade.get('current_pnl', 0),
                            "roi_percent": old_trade.get('roi_percent', 0),
                            "result": "WIN" if old_trade.get('current_pnl', 0) > 0 else "LOSS",
                            "closed_at": str(datetime.now())
                        }
                        # Salvar no historico
                        history = load_trades_history()
                        history.append(closed_trade)
                        with open(TRADES_HISTORY, 'w') as f:
                            json.dump(history[-50:], f, indent=2)  # Manter ultimos 50
                        print(f"Trade fechado registrado: {sym} | PnL: {closed_trade['final_pnl']}")
                
                # Atualizar estado
                last_positions = {t['symbol']: t for t in data["active_trades"]}
            
            # Sinais da Watchlist
            if os.path.exists(WATCHLIST):
                with open(WATCHLIST, 'r') as f:
                    wl = json.load(f)
                    data["signals"] = wl.get('pares', [])
            
            # Salva para o Nginx servir
            with open(STATS_FILE, 'w') as f:
                json.dump(data, f)
                
        except Exception as e:
            print(f"Erro no loop: {e}")
            exchange = None  # Forca reconexao
        
        time.sleep(5)

if __name__ == "__main__":
    loop()

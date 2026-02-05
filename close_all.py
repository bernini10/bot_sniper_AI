import ccxt
import json
import os

# Carrega chaves
try:
    env_path = '/root/bot_sniper_bybit/.env'
    secrets = {}
    with open(env_path, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                secrets[key] = val
    
    exchange = ccxt.bybit({
        'apiKey': secrets.get('BYBIT_API_KEY'),
        'secret': secrets.get('BYBIT_SECRET'),
        'options': {'defaultType': 'linear'} 
    })
    
    # Fecha SOL/USDT
    symbol = 'SOL/USDT:USDT' # Simbolo unificado CCXT para Bybit Linear
    
    # Verifica posicao
    positions = exchange.fetch_positions([symbol])
    for p in positions:
        size = float(p['contracts'])
        if size > 0:
            side = 'buy' if p['side'] == 'short' else 'sell'
            print(f"Fechando {size} contratos de {symbol} ({p['side']})...")
            exchange.create_order(symbol, 'market', side, size, params={'reduceOnly': True})
            print("Fechado com sucesso.")
        else:
            print("Nenhuma posicao aberta encontrada.")

except Exception as e:
    print(f"Erro: {e}")

#!/usr/bin/env python3
"""
Gera histórico mock baseado nas posições abertas no trades_history.json
Para popular o dashboard enquanto não há trades fechados reais
"""
import json
import random
from datetime import datetime, timedelta

# Ler posições abertas
with open('/root/bot_sniper_bybit/trades_history.json', 'r') as f:
    open_trades = json.load(f)

# Gerar 50 trades mock fechados
mock_history = []
cumulative_pnl = 0

# Base: usar os símbolos das posições abertas
symbols = list(set([t['symbol'] for t in open_trades if t.get('symbol')]))
if not symbols:
    symbols = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT']

# Gerar 50 trades nos últimos 30 dias
now = datetime.now()

for i in range(50):
    # 60% win rate
    is_win = random.random() < 0.6
    
    # PnL aleatório realista
    if is_win:
        pnl = random.uniform(0.5, 8.0)  # Ganhos $0.5-$8
    else:
        pnl = random.uniform(-5.0, -0.3)  # Perdas $-5 a $-0.3
    
    cumulative_pnl += pnl
    
    # Timestamp nos últimos 30 dias
    days_ago = random.randint(0, 30)
    hours_ago = random.randint(0, 23)
    timestamp = (now - timedelta(days=days_ago, hours=hours_ago)).timestamp() * 1000
    
    mock_history.append({
        'order_id': f'mock_{i}',
        'symbol': random.choice(symbols),
        'side': random.choice(['LONG', 'SHORT']),
        'entry_price': random.uniform(100, 70000),
        'amount': random.uniform(0.001, 1.0),
        'pnl': round(pnl, 2),
        'cumulative_pnl': round(cumulative_pnl, 2),
        'timestamp': int(timestamp),
        'status': 'WIN' if pnl > 0 else 'LOSS'
    })

# Ordenar por timestamp
mock_history.sort(key=lambda x: x['timestamp'])

# Recalcular cumulative
cumulative = 0
for trade in mock_history:
    cumulative += trade['pnl']
    trade['cumulative_pnl'] = round(cumulative, 2)

# Salvar
with open('/root/bot_sniper_bybit/mock_history.json', 'w') as f:
    json.dump(mock_history, f, indent=2)

print(f"✅ Gerado histórico mock com {len(mock_history)} trades")
print(f"   Win rate: {sum(1 for t in mock_history if t['pnl'] > 0) / len(mock_history) * 100:.1f}%")
print(f"   PnL acumulado: ${mock_history[-1]['cumulative_pnl']}")

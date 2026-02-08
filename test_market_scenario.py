#!/usr/bin/env python3
"""
Teste da Análise de Correlação BTC/BTC.D
Severino - 2026-02-08
"""

import sys
import os
import ccxt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lib_utils import get_market_analysis, should_trade_in_scenario

def test_market_scenario():
    """Testa análise de mercado em tempo real"""
    print("🔍 TESTE: Análise de Correlação BTC/BTC.D/ALTS")
    print("=" * 60)
    
    try:
        # Criar exchange
        secrets = {}
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, val = line.strip().split('=', 1)
                        secrets[key] = val
        
        exchange = ccxt.bybit({
            'apiKey': secrets.get('BYBIT_API_KEY'),
            'secret': secrets.get('BYBIT_SECRET'),
            'enableRateLimit': True,
            'options': {'defaultType': 'linear'}
        })
        
        # Análise completa
        analysis = get_market_analysis(exchange, timeframe='4h')
        
        print(f"\n📊 ANÁLISE ATUAL:")
        print(f"   BTC Trend:    {analysis['btc_trend']}")
        print(f"   BTC.D Trend:  {analysis['btcd_trend']}")
        print(f"   Cenário:      #{analysis['scenario_number']} - {analysis['scenario_name']}")
        print(f"   Descrição:    {analysis['scenario_description']}")
        
        # Testes de decisão
        print(f"\n🎯 DECISÕES DE TRADE:")
        
        scenario = analysis['scenario_number']
        
        for direction in ['LONG', 'SHORT']:
            should_trade, reason = should_trade_in_scenario(scenario, direction)
            status = "✅ PERMITIDO" if should_trade else "❌ BLOQUEADO"
            
            print(f"   {direction:5} → {status}")
            if reason:
                print(f"            Motivo: {reason}")
        
        print(f"\n✅ Teste concluído com sucesso!")
        return 0
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(test_market_scenario())

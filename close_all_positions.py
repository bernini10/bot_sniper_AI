#!/usr/bin/env python3
"""
Fechar todas as posições abertas - Cenário mudou
"""

import ccxt
import json
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def carregar_segredos():
    """Carrega as chaves API do arquivo secreto"""
    try:
        # Verificar arquivos possíveis
        possiveis = [
            os.path.join(BASE_DIR, 'secrets.json'),
            os.path.join(BASE_DIR, 'api_keys.json'),
            os.path.join(BASE_DIR, 'config', 'secrets.json'),
            os.path.join(os.path.expanduser('~'), '.bybit_keys.json')
        ]
        
        for arquivo in possiveis:
            if os.path.exists(arquivo):
                with open(arquivo, 'r') as f:
                    return json.load(f)
        
        # Tentar variáveis de ambiente
        api_key = os.getenv('BYBIT_API_KEY')
        api_secret = os.getenv('BYBIT_SECRET')
        
        if api_key and api_secret:
            return {'BYBIT_API_KEY': api_key, 'BYBIT_SECRET': api_secret}
        
        return {}
        
    except Exception as e:
        print(f"❌ Erro ao carregar segredos: {e}")
        return {}

def fechar_todas_posicoes():
    """Fecha todas as posições abertas"""
    print("="*60)
    print("🚪 FECHANDO TODAS AS POSIÇÕES ABERTAS")
    print("Motivo: Cenário de mercado mudou (BTC.D bearish para alts)")
    print("="*60)
    
    segredos = carregar_segredos()
    
    if not segredos.get('BYBIT_API_KEY') or not segredos.get('BYBIT_SECRET'):
        print("❌ Chaves API não encontradas!")
        print("   Verifique secrets.json ou variáveis de ambiente")
        return False
    
    try:
        # Conectar ao Bybit
        exchange = ccxt.bybit({
            'apiKey': segredos['BYBIT_API_KEY'],
            'secret': segredos['BYBIT_SECRET'],
            'enableRateLimit': True,
            'options': {'defaultType': 'linear'}
        })
        
        print("🔍 Buscando posições abertas...")
        
        # Buscar posições
        positions = exchange.fetch_positions()
        open_positions = [p for p in positions if float(p.get('contracts', 0)) > 0]
        
        if not open_positions:
            print("✅ Nenhuma posição aberta encontrada")
            return True
        
        print(f"📊 {len(open_positions)} posição(ões) aberta(s):")
        
        total_pnl = 0
        fechadas_com_sucesso = 0
        
        for pos in open_positions:
            symbol = pos['symbol']
            side = pos['side']
            contracts = float(pos['contracts'])
            entry_price = float(pos['entryPrice'])
            mark_price = float(pos['markPrice'])
            
            # Calcular PnL
            if side == 'long':
                pnl = (mark_price - entry_price) * contracts
            else:
                pnl = (entry_price - mark_price) * contracts
            
            pnl_pct = (pnl / (entry_price * contracts)) * 100 if entry_price * contracts > 0 else 0
            total_pnl += pnl
            
            print(f"\n📈 {symbol}:")
            print(f"   Direção: {side.upper()}")
            print(f"   Contratos: {contracts}")
            print(f"   Entrada: ${entry_price:.4f}")
            print(f"   Preço atual: ${mark_price:.4f}")
            print(f"   PnL: ${pnl:.4f} ({pnl_pct:.2f}%)")
            
            # Fechar posição
            print(f"   🚪 Fechando...")
            try:
                if side == 'long':
                    order = exchange.create_market_sell_order(symbol, contracts)
                else:
                    order = exchange.create_market_buy_order(symbol, contracts)
                
                print(f"   ✅ Fechado! Order ID: {order['id']}")
                fechadas_com_sucesso += 1
                
            except Exception as e:
                print(f"   ❌ Erro ao fechar: {e}")
        
        # Resumo
        print("\n" + "="*60)
        print("📊 RESUMO DO FECHAMENTO:")
        print(f"   Posições encontradas: {len(open_positions)}")
        print(f"   Fechadas com sucesso: {fechadas_com_sucesso}")
        print(f"   PnL total: ${total_pnl:.4f}")
        
        if fechadas_com_sucesso == len(open_positions):
            print("✅ Todas as posições foram fechadas!")
        else:
            print(f"⚠️ {len(open_positions) - fechadas_com_sucesso} posição(ões) não puderam ser fechadas")
        
        return fechadas_com_sucesso == len(open_positions)
        
    except Exception as e:
        print(f"❌ Erro geral: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧠 SISTEMA DE FECHAMENTO DE EMERGÊNCIA")
    print("Motivo: Cenário BTC.D mudou - risco de maiores perdas")
    print(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Confirmar
    confirm = input("⚠️  Tem certeza que deseja fechar TODAS as posições? (s/N): ")
    
    if confirm.lower() != 's':
        print("Operação cancelada pelo usuário")
        sys.exit(0)
    
    sucesso = fechar_todas_posicoes()
    
    if sucesso:
        print("\n🎯 PRÓXIMOS PASSOS:")
        print("1. Sistema será atualizado com validação BTC.D")
        print("2. Bug de direção será corrigido")
        print("3. Novas operações só entrarão em cenário favorável")
        print("\n✅ Pronto para reiniciar operações com segurança!")
    else:
        print("\n❌ Algumas posições não puderam ser fechadas")
        print("   Verifique manualmente na plataforma Bybit")
    
    sys.exit(0 if sucesso else 1)
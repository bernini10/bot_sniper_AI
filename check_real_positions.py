import ccxt
import os
import sys
import json
import logging
import psutil
from dotenv import load_dotenv

# Configuração de Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CheckRealPositions")

# Carregar Segredos (.env)
load_dotenv('/root/bot_sniper_bybit/.env')

def listar_processos_executores():
    executores = {}
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and 'python' in cmdline[0] and 'bot_executor.py' in ' '.join(cmdline):
                # Extrair Símbolo (ex: --symbol DOT/USDT)
                symbol_arg = None
                for i, arg in enumerate(cmdline):
                    if arg == '--symbol' and i + 1 < len(cmdline):
                        symbol_arg = cmdline[i+1]
                        break
                if symbol_arg:
                    executores[symbol_arg] = proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return executores

def main():
    api_key = os.getenv('BYBIT_API_KEY')
    api_secret = os.getenv('BYBIT_SECRET')
    
    if not api_key or not api_secret:
        logger.error("❌ API Key/Secret não encontradas no .env")
        return

    try:
        # Conectar na Bybit
        exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'linear'} 
        })

        logger.info("🔍 Consultando API Bybit (Positions)...")
        
        # Buscar posições ABERTAS (size != 0)
        positions = exchange.fetch_positions(params={'settleCoin': 'USDT'})
        open_positions = []
        for p in positions:
            size = float(p['contracts']) if 'contracts' in p else float(p['info']['size'])
            if size > 0:
                open_positions.append(p)
        
        logger.info(f"✅ Encontradas {len(open_positions)} posições abertas na corretora.")
        
        # Listar Processos Locais
        executores_ativos = listar_processos_executores()
        logger.info(f"✅ Encontrados {len(executores_ativos)} executores rodando localmente.")
        
        print("\n" + "="*80)
        print(f"{'PAR':<15} | {'TAMANHO':<10} | {'PNL (USDT)':<12} | {'SIDE':<6} | {'STATUS PROCESSO'}")
        print("="*80)
        
        orphans = []
        
        for pos in open_positions:
            symbol = pos['symbol']
            size = float(pos['contracts'])
            pnl = float(pos['unrealizedPnl'] or 0)
            side = pos['side'].upper()
            
            # Normalizar símbolo para comparação (DOT/USDT:USDT -> DOT/USDT)
            symbol_simple = symbol.split(':')[0]
            
            status_proc = "🔴 ÓRFÃO (SEM PROCESSO)"
            pid_str = ""
            
            # Verificar se existe processo para este símbolo
            found_proc = False
            for exec_sym, pid in executores_ativos.items():
                if exec_sym == symbol or exec_sym == symbol_simple:
                    status_proc = f"🟢 RODANDO (PID {pid})"
                    found_proc = True
                    break
            
            if not found_proc:
                orphans.append(symbol_simple)
            
            print(f"{symbol:<15} | {size:<10} | {pnl:<12.2f} | {side:<6} | {status_proc}")
            
        print("="*80)
        
        if orphans:
            print(f"\n⚠️ ALERTA: {len(orphans)} POSIÇÕES ÓRFÃS DETECTADAS!")
            print(f"Lista para resgate: {', '.join(orphans)}")
            
            # Salvar lista de órfãos
            with open('/root/bot_sniper_bybit/orphans_list.json', 'w') as f:
                json.dump(orphans, f)
            print("✅ Lista de órfãos salva em 'orphans_list.json'")
        else:
            print("\n✅ TUDO SINCRONIZADO. Nenhuma posição órfã.")
            if os.path.exists('/root/bot_sniper_bybit/orphans_list.json'):
                os.remove('/root/bot_sniper_bybit/orphans_list.json')

    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

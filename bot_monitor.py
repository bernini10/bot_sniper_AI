import json
import time
import os
import sys
import logging
import ccxt
from datetime import datetime
from lib_utils import JsonManager

# --- CONFIGURAÇÃO ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_FILE = os.path.join(BASE_DIR, 'watchlist.json')

sys.path.insert(0, BASE_DIR)
try:
    from bot_telegram import lancar_executor, CHAT_ID, TOKEN, bot
except Exception as e:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "monitor_bybit.log")),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MonitorBybit")

watchlist_mgr = JsonManager(WATCHLIST_FILE)

def get_bybit_public():
    return ccxt.bybit({
        'enableRateLimit': True,
        'options': {'defaultType': 'linear'}
    })

def esta_no_fechamento_candle(timeframe):
    now = datetime.now()
    minute = now.minute
    fechamentos = {
        '1m': list(range(60)),
        '3m': [0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45, 48, 51, 54, 57],
        '5m': [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
        '15m': [0, 15, 30, 45],
        '30m': [0, 30],
        '1h': [0],
        '4h': [0]
    }
    if timeframe not in fechamentos: return True
    return minute in fechamentos[timeframe]

def analisar_padrao(symbol, timeframe):
    try:
        exchange = get_bybit_public()
        candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=200)
        from lib_padroes import AnalistaTecnico
        analista = AnalistaTecnico()
        padrao = analista.analisar_par(symbol, candles)
        return padrao
    except Exception as e:
        logger.error(f"Erro ao analisar padrão para {symbol}: {e}")
        return None

def adicionar_smart_blacklist(symbol, padrao, timeframe, motivo):
    """Bloqueia combinação (Par + Padrão + TF) por 6 horas"""
    BLACKLIST_FILE = os.path.join(BASE_DIR, 'smart_blacklist.json')
    try:
        bl = {}
        if os.path.exists(BLACKLIST_FILE):
            with open(BLACKLIST_FILE, 'r') as f: bl = json.load(f)
        
        key = f"{symbol}_{padrao}_{timeframe}"
        expire_at = time.time() + (6 * 3600) # 6 horas
        
        bl[key] = {
            'expire': expire_at,
            'reason': motivo
        }
        
        # Limpar expirados
        now = time.time()
        bl = {k:v for k,v in bl.items() if v['expire'] > now}
        
        with open(BLACKLIST_FILE, 'w') as f: json.dump(bl, f, indent=2)
        logger.info(f"🚫 {key} adicionado à Smart Blacklist por 6h ({motivo})")
    except Exception as e:
        logger.error(f"Erro ao atualizar blacklist: {e}")

def invalidar_par(wl, idx, motivo):
    try:
        par = wl['pares'][idx]
        symbol = par['symbol']
        padrao = par['padrao']
        timeframe = par['timeframe']
        
        del wl['pares'][idx]
        wl['slots_ocupados'] = len(wl['pares'])
        watchlist_mgr.write(wl)
        logger.info(f"Par {symbol} removido: {motivo}")
        
        # Adicionar à Blacklist Inteligente
        adicionar_smart_blacklist(symbol, padrao, timeframe, motivo)
        
        try:
            bot.send_message(CHAT_ID, f"❌ PADRÃO INVALIDADO: {symbol}. Motivo: {motivo}", parse_mode='Markdown')
        except: pass
    except Exception as e:
        logger.error(f"Erro ao invalidar par: {e}")

def disparar_trade(wl, idx, preco_atual):
    """Dispara executor para entrada IMEDIATA"""
    symbol = wl['pares'][idx]['symbol']
    direcao = wl['pares'][idx]['direcao']
    
    if wl['pares'][idx].get('status') == 'EXECUTANDO':
        return

    logger.info(f"🔥 GATILHO ACIONADO para {symbol} em {preco_atual}! Disparando Executor...")
    
    wl['pares'][idx]['status'] = 'EXECUTANDO'
    watchlist_mgr.write(wl)
    
    try:
        lancar_executor(symbol)
        try:
            bot.send_message(CHAT_ID, f"🚀 GATILHO ROMPIDO: {symbol} @ {preco_atual}. Entrando {direcao}...", parse_mode='Markdown')
        except: pass
    except Exception as e:
        logger.error(f"Erro ao disparar executor para {symbol}: {e}")
        # Rollback status
        wl = watchlist_mgr.read()
        if idx < len(wl.get('pares', [])):
             wl['pares'][idx]['status'] = 'EM_FORMACAO'
             watchlist_mgr.write(wl)

def monitorar_watchlist():
    logger.info(">>> Monitor de Watchlist Iniciado (Vigia de Preço Ativo) <<<")
    exchange = get_bybit_public()
    
    while True:
        try:
            wl = watchlist_mgr.read()
            if not wl or 'pares' not in wl or len(wl['pares']) == 0:
                time.sleep(10)
                continue

            pares_para_processar = wl['pares'][:]
            restart_loop = False

            for idx, par in enumerate(pares_para_processar):
                symbol = par['symbol']
                timeframe = par['timeframe']
                neckline = par['neckline']
                direcao = par['direcao']
                stop_loss = par['stop_loss']
                status = par.get('status', 'EM_FORMACAO')

                if status == 'EXECUTANDO':
                    continue

                # 1. VERIFICAÇÃO RÁPIDA DE PREÇO (GATILHO)
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    preco = ticker['last']
                    
                    acionar = False
                    invalidar_trade = False
                    
                    if direcao == 'SHORT':
                        if preco <= neckline: acionar = True
                        elif preco >= stop_loss: invalidar_trade = True
                    elif direcao == 'LONG':
                        if preco >= neckline: acionar = True
                        elif preco <= stop_loss: invalidar_trade = True
                        
                    if invalidar_trade:
                        wl_atual = watchlist_mgr.read()
                        invalidar_par(wl_atual, idx, f"Stop atingido antes da entrada ({preco})")
                        restart_loop = True
                        break

                    if acionar:
                        disparar_trade(wl, idx, preco)
                        continue # Vai pro proximo, esse ja foi

                except Exception as e:
                    logger.error(f"Erro ao checar preço {symbol}: {e}")

                # 2. VALIDAÇÃO LENTA (CANDLE CLOSE)
                # Só verifica se o padrão ainda existe quando o candle fecha
                if esta_no_fechamento_candle(timeframe):
                    logger.info(f"Validando padrão {symbol} [{timeframe}]...")
                    padrao = analisar_padrao(symbol, timeframe)
                    
                    if not padrao:
                        wl_atual = watchlist_mgr.read()
                        invalidar_par(wl_atual, idx, "Padrão desfeito no fechamento")
                        restart_loop = True
                        break
                    elif padrao.nome != par['padrao'] or padrao.direcao != par['direcao']:
                        wl_atual = watchlist_mgr.read()
                        invalidar_par(wl_atual, idx, "Padrão mudou a configuração")
                        restart_loop = True
                        break
                    else:
                        # Atualiza niveis se mudaram levemente
                        if padrao.neckline_price != neckline:
                            wl_atual = watchlist_mgr.read()
                            if idx < len(wl_atual.get('pares', [])):
                                wl_atual['pares'][idx]['neckline'] = padrao.neckline_price
                                wl_atual['pares'][idx]['target'] = padrao.target_price
                                wl_atual['pares'][idx]['stop_loss'] = padrao.stop_loss_price
                                watchlist_mgr.write(wl_atual)
                                logger.info(f"Níveis atualizados para {symbol}")

            if restart_loop:
                continue

            time.sleep(20) # Verifica preços a cada 10s (High Frequency Check)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Erro fatal monitor: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitorar_watchlist()

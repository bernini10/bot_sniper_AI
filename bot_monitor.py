import json
import time
import os
import sys
import logging
import ccxt
from datetime import datetime
from lib_utils import JsonManager
from vision_validator_watchlist import VisionValidatorWatchlist # SEVERINO: Import IA

# --- CONFIGURAÇÃO ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_FILE = os.path.join(BASE_DIR, 'watchlist.json')
BLACKLIST_FILE = os.path.join(BASE_DIR, 'smart_blacklist.json')

sys.path.insert(0, BASE_DIR)
# Tenta importar bot telegram (pode falhar se nao configurado)
try:
    from bot_telegram import lancar_executor
    CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    TOKEN = os.getenv('TELEGRAM_TOKEN')
    import telebot
    bot = telebot.TeleBot(TOKEN) if TOKEN else None
except Exception:
    bot = None
    pass

# Tenta importar Brain Integration (NOVO)
try:
    from brain_integration import BrainIntegration
    BRAIN_AVAILABLE = True
    brain = BrainIntegration()
    brain_initialized = brain.initialize()
    if brain_initialized:
        logging.info("🧠 Brain Integration inicializado com sucesso")
    else:
        logging.warning("⚠️ Brain Integration em modo fallback")
except Exception as e:
    BRAIN_AVAILABLE = False
    logging.warning(f"⚠️ Brain Integration não disponível: {e}")

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

# Instancia IA Globalmente
try:
    exchange_ai = get_bybit_public()
    vision_validator = VisionValidatorWatchlist(exchange_ai)
except Exception as e:
    logger.error(f"Falha ao iniciar Vision AI: {e}")
    vision_validator = None

def get_fechamento_candle(timeframe):
    """Retorna True se estivermos no minuto de fechamento do candle"""
    now = datetime.now()
    minute = now.minute
    
    # Minutos que fecham candles
    fechamentos = {
        '15m': [0, 15, 30, 45], # Ex: 10:00, 10:15...
        '30m': [0, 30],
        '1h': [0],
        '4h': [0]
    }
    
    if timeframe not in fechamentos: return True # Default (sempre checa)
    
    # Checa se estamos NO MINUTO EXATO ou LOGO APÓS (margem de 2 min)
    # Ex: 10:00, 10:01, 10:15, 10:16
    for m in fechamentos[timeframe]:
        if minute == m or minute == (m + 1):
            return True
            
    return False

def analisar_padrao_tecnico(symbol, timeframe):
    """Validação Matemática (Lib Padrões)"""
    try:
        exchange = get_bybit_public()
        candles = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=200)
        from lib_padroes import AnalistaTecnico
        analista = AnalistaTecnico()
        padrao = analista.analisar_par(symbol, candles)
        return padrao
    except Exception as e:
        logger.error(f"Erro ao analisar padrão técnico {symbol}: {e}")
        return None

def adicionar_smart_blacklist(symbol, padrao, timeframe, motivo):
    """Bloqueia combinação (Par + Padrão + TF) por 6 horas"""
    try:
        bl = {}
        if os.path.exists(BLACKLIST_FILE):
            with open(BLACKLIST_FILE, 'r') as f: bl = json.load(f)
        
        key = f"{symbol}_{padrao}_{timeframe}"
        expire_at = time.time() + (6 * 3600) # 6 horas
        
        bl[key] = {
            'expire': expire_at,
            'reason': motivo,
            'timestamp': str(datetime.now())
        }
        
        # Limpar expirados
        now = time.time()
        bl = {k:v for k,v in bl.items() if v['expire'] > now}
        
        with open(BLACKLIST_FILE, 'w') as f: json.dump(bl, f, indent=2)
        logger.info(f"🚫 {key} adicionado à Smart Blacklist por 6h ({motivo})")
    except Exception as e:
        logger.error(f"Erro ao atualizar blacklist: {e}")

def remove_par_watchlist(wl_data, index, motivo, symbol, padrao, timeframe):
    try:
        if index < len(wl_data['pares']):
            del wl_data['pares'][index]
            wl_data['slots_ocupados'] = len(wl_data['pares'])
            watchlist_mgr.write(wl_data)
            
            logger.info(f"❌ Par {symbol} removido: {motivo}")
            adicionar_smart_blacklist(symbol, padrao, timeframe, motivo)
            
            try:
                if bot and CHAT_ID:
                    bot.send_message(CHAT_ID, f"❌ PADRÃO INVALIDADO: {symbol}\nMotivo: {motivo}", parse_mode='Markdown')
            except: pass
            return True
    except Exception as e:
        logger.error(f"Erro ao remover par: {e}")
    return False

def disparar_trade(wl_data, index, preco_atual):
    """Dispara executor para entrada IMEDIATA"""
    try:
        par = wl_data['pares'][index]
        symbol = par['symbol']
        direcao = par['direcao']
        
        if par.get('status') == 'EXECUTANDO':
            return

        logger.info(f"🔥 GATILHO ACIONADO para {symbol} em {preco_atual}! Disparando Executor...")
        
        # Atualiza status para não disparar 2x
        wl_data['pares'][index]['status'] = 'EXECUTANDO'
        watchlist_mgr.write(wl_data)
        
        # Lança processo filho
        lancar_executor(symbol)
        
        try:
            if bot and CHAT_ID:
                bot.send_message(CHAT_ID, f"🚀 GATILHO ROMPIDO: {symbol} @ {preco_atual}. Entrando {direcao}...", parse_mode='Markdown')
        except: pass
        
    except Exception as e:
        logger.error(f"Erro ao disparar executor para {symbol}: {e}")

def consultar_brain_para_decisao(par, preco_atual):
    """
    NOVO: Consulta o cérebro para decisão de entrada
    Retorna: (deve_entrar: bool, motivo: str, brain_data: dict)
    """
    if not BRAIN_AVAILABLE or not brain_initialized:
        # Fallback: sempre entra se gatilho acionado
        return True, "Brain não disponível - usando fallback", {}
    
    try:
        # Preparar dados para o brain
        pattern_data = {
            'symbol': par['symbol'],
            'timeframe': par['timeframe'],
            'pattern': par['padrao'],
            'direction': par['direcao'],
            'ai_confidence': par.get('ai_confidence', 0.5),
            'neckline': par['neckline'],
            'stop_loss': par['stop_loss'],
            'target': par['target'],
            'current_price': preco_atual
        }
        
        # Consultar brain
        brain_decision = brain.should_enter_trade(pattern_data)
        
        # Registrar decisão no par
        par['brain_decision'] = brain_decision
        
        # Decidir baseado no brain
        if brain_decision['decision'] == 'ENTER':
            return True, f"Brain APROVOU: {brain_decision['reason']}", brain_decision
        else:
            return False, f"Brain REJEITOU: {brain_decision['reason']}", brain_decision
            
    except Exception as e:
        logger.error(f"❌ Erro ao consultar brain: {e}")
        # Fallback seguro: não entra se brain falhar
        return False, f"Erro no brain: {str(e)}", {}

def monitorar_watchlist():
    logger.info(">>> Monitor de Watchlist Iniciado v2.4.0 (IA + BRAIN) <<<")
    exchange = get_bybit_public()
    
    # Controle de validação IA para não chamar toda hora
    last_ai_check = {} 
    
    while True:
        try:
            wl = watchlist_mgr.read()
            if not wl or 'pares' not in wl or len(wl['pares']) == 0:
                time.sleep(10)
                continue

            pares = wl['pares']
            restart_loop = False

            # Itera sobre cópia para poder modificar a lista original
            # Copiamos a lista para evitar erro de índice ao deletar
            for i, par in enumerate(list(pares)):
                # Indice real na lista original pode mudar se deletarmos itens
                # Precisamos re-buscar o índice real pelo símbolo
                real_idx = -1
                for idx_orig, p_orig in enumerate(wl['pares']):
                    if p_orig['symbol'] == par['symbol']:
                        real_idx = idx_orig
                        break
                
                if real_idx == -1: continue # Ja foi removido

                symbol = par['symbol']
                timeframe = par['timeframe']
                neckline = par['neckline']
                direcao = par['direcao']
                stop_loss = par['stop_loss']
                padrao_nome = par['padrao']
                status = par.get('status', 'EM_FORMACAO')

                if status == 'EXECUTANDO':
                    continue

                # ==========================================================
                # 1. VERIFICAÇÃO RÁPIDA DE PREÇO (GATILHO - EXECUÇÃO)
                # ==========================================================
                try:
                    ticker = exchange.fetch_ticker(symbol)
                    preco_atual = ticker['last']
                    
                    acionar_gatilho = False
                    stop_atingido = False
                    
                    if direcao == 'SHORT':
                        # Short: Rompe suporte (neckline) para baixo
                        if preco_atual <= neckline: acionar_gatilho = True
                        # Stop antes da entrada (preço subiu demais e invalidou a tese)
                        elif preco_atual >= stop_loss: stop_atingido = True
                            
                    elif direcao == 'LONG':
                        # Long: Rompe resistência (neckline) para cima
                        if preco_atual >= neckline: acionar_gatilho = True
                        # Stop antes da entrada (preço caiu demais)
                        elif preco_atual <= stop_loss: stop_atingido = True
                        
                    if stop_atingido:
                        remove_par_watchlist(wl, real_idx, f"Stop atingido antes da entrada ({preco_atual})", symbol, padrao_nome, timeframe)
                        restart_loop = True
                        break # Reinicia loop pois lista mudou

                    if acionar_gatilho:
                        # NOVO: CONSULTAR BRAIN ANTES DE ENTRAR
                        deve_entrar, motivo, brain_data = consultar_brain_para_decisao(par, preco_atual)
                        
                        if deve_entrar:
                            disparar_trade(wl, real_idx, preco_atual)
                            logger.info(f"🧠 {motivo}")
                            
                            # Atualizar par com decisão do brain
                            wl['pares'][real_idx]['brain_decision'] = brain_data
                            watchlist_mgr.write(wl)
                        else:
                            logger.info(f"🧠 {motivo}")
                            # Opcional: remover do watchlist se brain rejeitar
                            # remove_par_watchlist(wl, real_idx, motivo, symbol, padrao_nome, timeframe)
                            # restart_loop = True
                            # break
                        
                        continue # Vai pro proximo, esse já foi processado

                except Exception as e:
                    logger.error(f"Erro ao checar preço {symbol}: {e}")

                # ==========================================================
                # 2. VALIDAÇÃO LENTA (IA + TÉCNICA) - NO FECHAMENTO DE CANDLE
                # ==========================================================
                # Verifica se já validamos neste ciclo de candle (usando timestamp aproximado)
                agora_ts = int(time.time() / 300) # Bloco de 5 min
                chave_check = f"{symbol}_{timeframe}_{agora_ts}"
                
                if get_fechamento_candle(timeframe) and chave_check not in last_ai_check:
                    logger.info(f"🔍 Validando {symbol} [{timeframe}] (Técnica + IA)...")
                    last_ai_check[chave_check] = True # Marca como verificado neste bloco
                    
                    # 2.1 Validação Matemática
                    novo_padrao = analisar_padrao_tecnico(symbol, timeframe)
                    
                    if not novo_padrao:
                        remove_par_watchlist(wl, real_idx, "Padrão desfeito matematicamente", symbol, padrao_nome, timeframe)
                        restart_loop = True
                        break
                    
                    # Se mudou o tipo de padrão (ex: Cunha virou Bandeira), remove antigo
                    if novo_padrao.nome != padrao_nome or novo_padrao.direcao != direcao:
                        remove_par_watchlist(wl, real_idx, "Padrão mudou configuração", symbol, padrao_nome, timeframe)
                        restart_loop = True
                        break
                    
                    # 2.2 Validação Vision AI (NOVO v2.3.1)
                    if vision_validator:
                        logger.info(f"🧠 Vision AI analisando Watchlist: {symbol}...")
                        ai_aprovado = vision_validator.validate_pattern(symbol, timeframe, par)
                        
                        if not ai_aprovado:
                            remove_par_watchlist(wl, real_idx, "Vision AI REJECTED (Visual Inválido)", symbol, padrao_nome, timeframe)
                            restart_loop = True
                            break
                    
                    # Se passou por tudo, atualiza níveis finos
                    if novo_padrao.neckline_price != neckline:
                        wl['pares'][real_idx]['neckline'] = novo_padrao.neckline_price
                        wl['pares'][real_idx]['target'] = novo_padrao.target_price
                        wl['pares'][real_idx]['stop_loss'] = novo_padrao.stop_loss_price
                        watchlist_mgr.write(wl)
                        logger.info(f"♻️ Níveis atualizados para {symbol}")

            # Limpeza do cache de checks (para não crescer infinito)
            if len(last_ai_check) > 100:
                last_ai_check.clear()

            if restart_loop:
                continue

            time.sleep(10) # Loop principal

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Erro fatal monitor loop: {e}")
            time.sleep(5)

if __name__ == "__main__":
    monitorar_watchlist()
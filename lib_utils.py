import json
import os
import time
import fcntl
import logging

logger = logging.getLogger("Utils")

class JsonManager:
    """
    Gerenciador seguro de arquivos JSON com File Locking (Phase 1 Fix).
    Evita que Scanner e Executores corrompam a watchlist ao escreverem juntos.
    """
    def __init__(self, filepath):
        self.filepath = filepath

    def _acquire_lock(self, file_handle):
        try:
            fcntl.flock(file_handle, fcntl.LOCK_EX)
        except IOError as e:
            logger.error(f"Erro ao adquirir lock: {e}")
            raise

    def _release_lock(self, file_handle):
        try:
            fcntl.flock(file_handle, fcntl.LOCK_UN)
        except IOError:
            pass

    def read(self):
        """Lê o JSON com lock compartilhado ou exclusivo momentâneo"""
        if not os.path.exists(self.filepath):
            return {}
        
        try:
            with open(self.filepath, 'r') as f:
                self._acquire_lock(f)
                try:
                    content = f.read()
                    if not content: return {}
                    return json.loads(content)
                finally:
                    self._release_lock(f)
        except json.JSONDecodeError:
            logger.error(f"Arquivo {self.filepath} corrompido. Retornando vazio.")
            return {}
        except Exception as e:
            logger.error(f"Erro de leitura segura: {e}")
            return {}

    def write(self, data):
        """Escreve no JSON com lock exclusivo"""
        try:
            # Open with 'r+' to allow locking before truncation, or 'w' if strict
            # To be safe against race conditions during open, we use a separate lock file or flock strictly
            with open(self.filepath, 'w') as f:
                self._acquire_lock(f)
                try:
                    json.dump(data, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno()) # Força gravação no disco
                finally:
                    self._release_lock(f)
            return True
        except Exception as e:
            logger.error(f"Erro de escrita segura: {e}")
            return False

def check_btc_trend(exchange, timeframe='4h'):
    """
    Phase 2: Filtro de Tendência do BTC.
    Retorna 'LONG', 'SHORT' ou 'NEUTRAL'.
    """
    try:
        # Usa média móvel de 200 períodos
        candles = exchange.fetch_ohlcv('BTC/USDT', timeframe=timeframe, limit=201)
        if len(candles) < 201: return 'NEUTRAL'
        
        closes = [c[4] for c in candles]
        current_price = closes[-1]
        
        # Simples SMA 200 (pode ser melhorada para EMA)
        sma200 = sum(closes[:-1]) / 200
        
        if current_price > sma200:
            return 'LONG'
        else:
            return 'SHORT'
    except Exception as e:
        logger.error(f"Erro ao checar tendencia BTC: {e}")
        return 'NEUTRAL'


def check_btc_dominance_webhook():
    """
    SEVERINO: Lê BTC.D do webhook do TradingView (MÉTODO PRINCIPAL)
    Retorna 'LONG' (subindo), 'SHORT' (caindo) ou 'NEUTRAL'
    
    Fallback para proxy se dados estiverem antigos (>30 min)
    """
    BTCD_FILE = '/root/bot_sniper_bybit/btcd_data.json'
    MAX_AGE_SECONDS = 1800  # 30 minutos
    
    try:
        # Verificar se arquivo existe
        if not os.path.exists(BTCD_FILE):
            logger.warning("Webhook BTC.D: arquivo não existe ainda. Usando fallback proxy.")
            return None  # Indica para usar fallback
        
        # Ler dados
        with open(BTCD_FILE, 'r') as f:
            data = json.load(f)
        
        # Verificar idade dos dados
        age = time.time() - data.get('timestamp', 0)
        
        if age > MAX_AGE_SECONDS:
            logger.warning(f"Webhook BTC.D: dados antigos ({age/60:.1f} min). Usando fallback proxy.")
            return None  # Indica para usar fallback
        
        # Dados válidos
        direction = data.get('direction', 'NEUTRAL')
        logger.info(f"✅ BTC.D Webhook: {data.get('btc_d_value', 'N/A')}% → {direction} (atualizado há {age:.0f}s)")
        
        return direction
        
    except Exception as e:
        logger.error(f"Erro ao ler BTC.D webhook: {e}")
        return None  # Indica para usar fallback


def check_btc_dominance_proxy(exchange, timeframe='4h'):
    """
    SEVERINO: Análise de Bitcoin Dominance (BTC.D) via Proxy
    Retorna 'LONG' (subindo), 'SHORT' (caindo) ou 'NEUTRAL'
    
    BTC.D subindo = dinheiro indo pro BTC (ruim para alts)
    BTC.D caindo = dinheiro saindo do BTC (bom para alts)
    
    Método: Compara performance do BTC vs principais alts (ETH, SOL, BNB)
    Se BTC performa melhor = dominância subindo
    Se alts performam melhor = dominância caindo
    """
    try:
        # Buscar candles do BTC e principais alts
        btc_candles = exchange.fetch_ohlcv('BTC/USDT', timeframe=timeframe, limit=21)
        
        # Principais alts para comparação
        alt_symbols = ['ETH/USDT', 'SOL/USDT', 'BNB/USDT']
        alt_performances = []
        
        for alt_symbol in alt_symbols:
            try:
                alt_candles = exchange.fetch_ohlcv(alt_symbol, timeframe=timeframe, limit=21)
                
                if len(alt_candles) >= 21 and len(btc_candles) >= 21:
                    # Calcula performance percentual (últimos 20 candles)
                    btc_start = btc_candles[-21][4]  # Close 20 candles atrás
                    btc_end = btc_candles[-1][4]     # Close atual
                    btc_perf = ((btc_end - btc_start) / btc_start) * 100
                    
                    alt_start = alt_candles[-21][4]
                    alt_end = alt_candles[-1][4]
                    alt_perf = ((alt_end - alt_start) / alt_start) * 100
                    
                    # Diferença de performance
                    # Se positivo: BTC performou melhor (dominância subindo)
                    # Se negativo: Alt performou melhor (dominância caindo)
                    alt_performances.append(btc_perf - alt_perf)
                    
            except Exception as e:
                logger.debug(f"Erro ao buscar {alt_symbol}: {e}")
                continue
        
        if not alt_performances:
            logger.warning("Não foi possível calcular BTC Dominance. Usando NEUTRAL.")
            return 'NEUTRAL'
        
        # Média das performances relativas
        avg_relative_perf = sum(alt_performances) / len(alt_performances)
        
        # Se BTC performou >1% melhor que alts em média = dominância subindo
        if avg_relative_perf > 1.0:
            logger.info(f"BTC.D Proxy: SUBINDO (+{avg_relative_perf:.2f}% vs alts)")
            return 'LONG'  # BTC.D subindo
        # Se BTC performou >1% pior que alts = dominância caindo
        elif avg_relative_perf < -1.0:
            logger.info(f"BTC.D Proxy: CAINDO ({avg_relative_perf:.2f}% vs alts)")
            return 'SHORT'  # BTC.D caindo
        else:
            logger.info(f"BTC.D Proxy: LATERAL ({avg_relative_perf:.2f}% vs alts)")
            return 'NEUTRAL'  # Lateral
            
    except Exception as e:
        logger.error(f"Erro ao checar BTC Dominance: {e}")
        return 'NEUTRAL'


def get_market_scenario(btc_trend, btc_dominance_trend):
    """
    SEVERINO: Retorna cenário de mercado (1-5) baseado em BTC + BTC.D
    
    Cenários:
    1. BTC ↗ + BTC.D ↗ = Dinheiro indo pro BTC (evitar LONGs alts)
    2. BTC ↘ + BTC.D ↗ = Pânico nas alts (SHORTs OK)
    3. BTC ↗ + BTC.D ↘ = Altseason local (MELHOR para LONGs alts)
    4. BTC ↘ + BTC.D ↘ = Alts segurando (neutro)
    5. BTC ~ + BTC.D ~ = Lateral (seguir BTC)
    """
    # Normalizar para maiúsculas
    btc = btc_trend.upper()
    btcd = btc_dominance_trend.upper()
    
    # Cenário 1: BTC Alta + BTC.D Alta
    if btc == 'LONG' and btcd == 'LONG':
        return 1, "BTC_DOMINANTE", "⚠️ Dinheiro indo pro BTC. Evite LONGs em Alts."
    
    # Cenário 2: BTC Baixa + BTC.D Alta
    elif btc == 'SHORT' and btcd == 'LONG':
        return 2, "PANICO_ALTS", "⚠️ Pânico nas Alts. SHORTs OK, LONGs evitar."
    
    # Cenário 3: BTC Alta + BTC.D Baixa (MELHOR)
    elif btc == 'LONG' and btcd == 'SHORT':
        return 3, "ALTSEASON", "✅ Altseason local! MELHOR cenário para LONGs em Alts."
    
    # Cenário 4: BTC Baixa + BTC.D Baixa
    elif btc == 'SHORT' and btcd == 'SHORT':
        return 4, "ALTS_SEGURANDO", "⚠️ Alts segurando. BTC cai mas alts resistem."
    
    # Cenário 5: Neutral (lateral)
    else:
        return 5, "LATERAL", "ℹ️ Mercado lateral. Alts seguem BTC."


def should_trade_in_scenario(scenario_number, trade_direction):
    """
    SEVERINO: Decide se deve operar baseado no cenário e direção
    
    Args:
        scenario_number: 1-5 (cenário de mercado)
        trade_direction: 'LONG' ou 'SHORT'
    
    Returns:
        (should_trade: bool, reason: str)
    """
    direction = trade_direction.upper()
    
    # Cenário 1: BTC Dominante - Evitar LONGs em alts
    if scenario_number == 1:
        if direction == 'LONG':
            return False, "Cenário 1: Dinheiro indo pro BTC, evitando LONGs em alts"
        else:
            return True, ""  # SHORTs OK
    
    # Cenário 2: Pânico nas Alts - SHORTs favorecidos
    elif scenario_number == 2:
        if direction == 'LONG':
            return False, "Cenário 2: Pânico nas alts, evitando LONGs"
        else:
            return True, ""  # SHORTs muito bons
    
    # Cenário 3: Altseason - MELHOR para LONGs
    elif scenario_number == 3:
        if direction == 'LONG':
            return True, ""  # LONGs muito bons!
        else:
            return False, "Cenário 3: Altseason, evitando SHORTs"
    
    # Cenário 4: Alts segurando - Neutro, permite ambos mas com cautela
    elif scenario_number == 4:
        return True, ""  # Permite ambos
    
    # Cenário 5: Lateral - Permite ambos
    elif scenario_number == 5:
        return True, ""  # Permite ambos
    
    # Fallback
    return True, ""


def get_market_analysis(exchange, timeframe='4h'):
    """
    SEVERINO: Análise completa de mercado (BTC + BTC.D + Cenário)
    
    BTC.D: Tenta webhook primeiro, fallback para proxy se necessário
    
    Returns:
        {
            'btc_trend': 'LONG/SHORT/NEUTRAL',
            'btcd_trend': 'LONG/SHORT/NEUTRAL',
            'btcd_source': 'webhook' ou 'proxy',
            'scenario_number': 1-5,
            'scenario_name': str,
            'scenario_description': str
        }
    """
    btc_trend = check_btc_trend(exchange, timeframe)
    
    # Tentar webhook primeiro
    btcd_trend = check_btc_dominance_webhook()
    btcd_source = 'webhook'
    
    # Fallback para proxy se webhook não disponível
    if btcd_trend is None:
        btcd_trend = check_btc_dominance_proxy(exchange, timeframe)
        btcd_source = 'proxy'
    
    scenario_num, scenario_name, scenario_desc = get_market_scenario(btc_trend, btcd_trend)
    
    return {
        'btc_trend': btc_trend,
        'btcd_trend': btcd_trend,
        'btcd_source': btcd_source,
        'scenario_number': scenario_num,
        'scenario_name': scenario_name,
        'scenario_description': scenario_desc
    }

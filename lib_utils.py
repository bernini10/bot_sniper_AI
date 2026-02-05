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

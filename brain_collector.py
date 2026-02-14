import sqlite3
import json
import logging
import threading
import time
from datetime import datetime

# Configuração de Log Isolada
logger = logging.getLogger("BrainCollector")
DB_NAME = 'sniper_brain.db'

class BrainCollector:
    def __init__(self):
        self.enabled = True
        
    def _save_task(self, symbol, timeframe, pattern, direction, candles):
        """Executa a gravação em thread separada para não bloquear o trade"""
        try:
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            
            # Converter candles para JSON (Open, High, Low, Close, Volume apenas)
            # Candles formato ccxt: [timestamp, open, high, low, close, volume]
            ohlcv_clean = [
                [c[0], c[1], c[2], c[3], c[4], c[5]] for c in candles[-100:] # Pega ultimos 100
            ]
            
            c.execute('''
                INSERT INTO raw_samples 
                (symbol, timeframe, timestamp_detection, pattern_detected, direction, ohlcv_json, status)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING')
            ''', (
                symbol, 
                timeframe, 
                int(time.time()), 
                pattern,
                direction,
                json.dumps(ohlcv_clean)
            ))
            
            conn.commit()
            conn.close()
            # logger.info(f"🧠 Amostra salva para {symbol} [{pattern}]")
            
        except Exception as e:
            logger.error(f"Erro ao salvar amostra no cérebro: {e}")

    def collect(self, symbol, timeframe, pattern, direction, candles):
        """Método público não-bloqueante"""
        if not self.enabled: return
        
        # Fire and Forget
        t = threading.Thread(
            target=self._save_task, 
            args=(symbol, timeframe, pattern, direction, candles)
        )
        t.daemon = True
        t.start()

# Singleton
collector = BrainCollector()

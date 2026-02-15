"""
Validador Visual de Padrões Pré-Entrada (Watchlist)
"""

import ccxt
import time
import json
import os
import logging
import requests
import pandas as pd
import mplfinance as mpf
from datetime import datetime
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("VisionValidatorWatchlist")

# Telegram config
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Google AI config
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')

# Diretório de imagens
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, 'brain_images')

if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

class VisionValidatorWatchlist:
    """
    Valida visualmente os padrões na Watchlist (Pré-Trade) usando Gemini Vision AI.
    Funciona como um filtro extra antes de gastar dinheiro.
    """

    def __init__(self, exchange: ccxt.bybit):
        self.exchange = exchange
        self.gemini_model = None
        
        if GOOGLE_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=GOOGLE_API_KEY)
                self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
                logger.info("✅ Gemini Vision AI configurado para Watchlist Validator")
            except Exception as e:
                logger.error(f"❌ Erro ao configurar Gemini: {e}")
        else:
            logger.warning("⚠️ GOOGLE_API_KEY ausente - Vision Validator Watchlist desabilitado")

    def _generate_chart_image(self, symbol: str, timeframe: str, pattern: str) -> Optional[str]:
        """Gera imagem do gráfico candlestick para análise"""
        try:
            # Busca candles suficientes para visualização do padrão
            candles = self.exchange.fetch_ohlcv(symbol, timeframe, limit=50)
            if len(candles) < 10: return None

            df = pd.DataFrame(candles, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df['Date'] = pd.to_datetime(df['Date'], unit='ms')
            df.set_index('Date', inplace=True)

            safe_symbol = symbol.replace('/', '')
            timestamp = int(time.time())
            filename = f"{IMG_DIR}/watchlist_{safe_symbol}_{timestamp}.png"

            mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', edge='inherit', wick='inherit', volume='in')
            s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds')

            mpf.plot(df, type='candle', volume=False, style=s,
                     savefig=dict(fname=filename, dpi=100, bbox_inches='tight'),
                     title=f"{symbol} - {pattern} (Watchlist)",
                     axisoff=True)

            return filename

        except Exception as e:
            logger.error(f"Erro ao gerar imagem watchlist: {e}")
            return None

    def _cleanup_old_images(self):
        """Remove imagens antigas (> 1 hora)"""
        try:
            cutoff = time.time() - 3600
            for f in os.listdir(IMG_DIR):
                if f.startswith('watchlist_'):
                    fpath = os.path.join(IMG_DIR, f)
                    if os.path.getmtime(fpath) < cutoff:
                        os.remove(fpath)
        except Exception: pass

    def validate_pattern(self, symbol: str, timeframe: str, pattern_data: Dict) -> bool:
        """
        Consulta Gemini Vision AI para validar se o padrão na Watchlist é visualmente promissor.
        Returns: True (Válido/Aprovado) ou False (Inválido/Rejeitado)
        """
        if not self.gemini_model:
            return True # Se API falhar/ausente, aprova por padrão (fallback para lógica matemática)

        try:
            # Gera imagem
            pattern_name = pattern_data.get('padrao', 'Unknown')
            image_path = self._generate_chart_image(symbol, timeframe, pattern_name)
            
            if not image_path: return True

            from PIL import Image
            direction = pattern_data.get('direcao', '')
            
            prompt = f"""
Atue como um Trader Institucional Sênior.

CONTEXTO:
- Estamos monitorando {symbol} para uma possível entrada.
- Padrão detectado matematicamente: {pattern_name} ({direction})

MISSÃO:
Analise o gráfico e valide se este padrão é VISUALMENTE VÁLIDO e PROMISSOR para operar.

CRITÉRIOS DE APROVAÇÃO (VALID):
- O padrão gráfico (ex: Cunha, Bandeira, OCO) é claramente reconhecível?
- A tendência do timeframe favorece a direção do padrão?
- O preço está "respeitando" a estrutura?

CRITÉRIOS DE REJEIÇÃO (INVALID):
- O gráfico está "sujo", lateral demais ou sem tendência clara?
- O padrão parece forçado ou inexistente visualmente?
- Há resistências/suportes muito próximos que bloqueiam o alvo?

Responda ESTRITAMENTE neste formato JSON:
{{
    "verdict": "VALID" ou "INVALID",
    "confidence": 0.0 a 1.0,
    "reasoning": "Explicação técnica breve"
}}
"""
            img = Image.open(image_path)
            result = self.gemini_model.generate_content([prompt, img])
            
            response_text = result.text.replace('```json', '').replace('```', '').strip()
            parsed = json.loads(response_text)
            
            verdict = parsed.get('verdict', 'VALID')
            confidence = parsed.get('confidence', 0)
            reasoning = parsed.get('reasoning', '')
            
            self._cleanup_old_images()

            if verdict == 'INVALID' and confidence > 0.75:
                logger.warning(f"🚫 WATCHLIST REJEITADO PELA IA: {symbol} (conf: {confidence:.2f}) - {reasoning}")
                return False
            
            logger.info(f"✅ WATCHLIST APROVADO PELA IA: {symbol} (conf: {confidence:.2f})")
            return True

        except Exception as e:
            logger.error(f"❌ Erro Vision AI Watchlist: {e}")
            return True # Em caso de erro, aprova para não travar o bot

"""
Validador Pós-Entrada com Vision AI - Bot Sniper
Severino - 2026-02-14

ATUALIZACAO v2.3.1:
- Aumento de Threshold de Invalidação: 0.70 -> 0.85
- Lógica de Confirmação Dupla: Exige 2 candles consecutivos INVALID para fechar.
- Tolerância a Pullbacks: Prompt ajustado.

A cada fechamento de candle, gera imagem atualizada do gráfico e envia para
Gemini Vision AI validar se o padrão continua válido.
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

logger = logging.getLogger("PostEntryValidator")

# Telegram config
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Importar sistema de fallback
try:
    from gemini_fallback import get_gemini_fallback
    GEMINI_FALLBACK = get_gemini_fallback()
    HAS_FALLBACK = True
except ImportError:
    # Fallback para sistema antigo
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
    GEMINI_FALLBACK = None
    HAS_FALLBACK = False

# Diretório de imagens
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, 'brain_images')
ALERT_LOG_FILE = os.path.join(BASE_DIR, 'vision_alerts.log')

if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)


def send_telegram_alert(message: str):
    """Envia alerta para o Telegram"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram não configurado para alertas")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        logger.error(f"Erro ao enviar alerta Telegram: {e}")


def log_vision_alert(message: str):
    """Registra alerta no arquivo de log do painel"""
    try:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(ALERT_LOG_FILE, 'a') as f:
            f.write(f"{timestamp} - {message}\n")
    except Exception as e:
        logger.error(f"Erro ao gravar alert log: {e}")


class PostEntryValidator:
    """
    Valida continuamente se o padrão que gerou a entrada ainda é válido
    usando Gemini Vision AI no fechamento de cada candle.
    """

    def __init__(self, exchange: ccxt.bybit, symbol: str, entry_price: float,
                 side: str, pattern_data: Dict, timeframe: str = '15m'):
        self.exchange = exchange
        self.symbol = symbol
        self.entry_price = entry_price
        self.side = side
        self.pattern_data = pattern_data
        self.timeframe = timeframe
        self.entry_time = time.time()

        # Converte timeframe para segundos
        self.tf_seconds = self._timeframe_to_seconds(timeframe)

        # Controle de candle
        self.last_candle_time = 0  # timestamp do último candle validado

        # Contadores
        self.validations_count = 0
        self.api_failures_count = 0
        self.consecutive_api_failures = 0
        self.MAX_CONSECUTIVE_FAILURES = 3  # Alerta após 3 falhas seguidas

        # Confidence threshold para fechar (AUMENTADO v2.3.1)
        self.INVALID_CONFIDENCE_THRESHOLD = 0.85
        
        # Controle de Confirmação Dupla (v2.3.1)
        self.consecutive_invalid_candles = 0
        self.REQUIRED_INVALID_CANDLES = 2

        # Configurar Gemini
        self._setup_gemini()

        logger.info(f"👁️ Vision PostValidator v2.3.1 (Tolerante) inicializado: {symbol} | TF: {timeframe}")

    def _setup_gemini(self):
        """Configura o modelo Gemini com fallback"""
        self.gemini_model = None
        
        if HAS_FALLBACK and GEMINI_FALLBACK:
            try:
                # Usar sistema de fallback
                api_key = GEMINI_FALLBACK.configure_genai()
                import google.generativeai as genai
                self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
                
                # Testar conexão
                success, msg = GEMINI_FALLBACK.test_connection()
                if success:
                    logger.info(f"✅ Gemini Vision AI configurado (com fallback): {msg}")
                else:
                    logger.warning(f"⚠️ Gemini com problemas: {msg}")
                    
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Erro ao configurar Gemini: {error_msg}")
                
                # Registrar falha no sistema de fallback
                if HAS_FALLBACK:
                    GEMINI_FALLBACK.record_failure(error_msg)
                    
                self._alert_api_failure(f"Falha ao inicializar Gemini: {error_msg}")
        else:
            # Sistema antigo (sem fallback)
            GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')
            if GOOGLE_API_KEY:
                try:
                    import google.generativeai as genai
                    genai.configure(api_key=GOOGLE_API_KEY)
                    self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
                    logger.info("✅ Gemini Vision AI configurado (sistema antigo)")
                except Exception as e:
                    logger.error(f"❌ Erro ao configurar Gemini: {e}")
                    self._alert_api_failure(f"Falha ao inicializar Gemini: {e}")
            else:
                logger.warning("⚠️ GOOGLE_API_KEY ausente - Vision AI desabilitado")
                self._alert_api_failure("GOOGLE_API_KEY não configurada - validação por IA desabilitada")

    def _timeframe_to_seconds(self, tf: str) -> int:
        unit = tf[-1]
        value = int(tf[:-1])
        if unit == 'm': return value * 60
        if unit == 'h': return value * 3600
        if unit == 'd': return value * 86400
        return 900  # Default 15m

    def _is_candle_closed(self) -> bool:
        """
        Verifica se um novo candle fechou desde a última validação.
        """
        try:
            # Busca os 2 últimos candles
            candles = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=2)
            if len(candles) < 2:
                return False

            # O penúltimo candle é o último fechado
            last_closed_time = candles[-2][0]  # timestamp em ms

            if last_closed_time > self.last_candle_time:
                self.last_candle_time = last_closed_time
                return True

            return False

        except Exception as e:
            logger.error(f"Erro ao verificar candle: {e}")
            return False

    def _generate_chart_image(self) -> Optional[str]:
        """Gera imagem atualizada do gráfico candlestick"""
        try:
            # Busca candles suficientes para visualização do padrão
            candles = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=50)
            if len(candles) < 10:
                return None

            df = pd.DataFrame(candles, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df['Date'] = pd.to_datetime(df['Date'], unit='ms')
            df.set_index('Date', inplace=True)

            safe_symbol = self.symbol.replace('/', '')
            timestamp = int(time.time())
            filename = f"{IMG_DIR}/postval_{safe_symbol}_{timestamp}.png"

            mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', edge='inherit', wick='inherit', volume='in')
            s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds')

            # Adicionar linha horizontal no entry price
            hlines = dict(hlines=[self.entry_price], colors=['cyan'], linestyle='--', linewidths=1)

            mpf.plot(df, type='candle', volume=False, style=s,
                     savefig=dict(fname=filename, dpi=100, bbox_inches='tight'),
                     title=f"{self.symbol} - {self.pattern_data.get('pattern_name', '')} (Post-Entry)",
                     hlines=hlines,
                     axisoff=True)

            return filename

        except Exception as e:
            logger.error(f"Erro ao gerar imagem pós-entrada: {e}")
            return None

    def _consult_vision_ai(self, image_path: str) -> Optional[Dict]:
        """Consulta Gemini Vision AI para validar se o padrão continua válido"""
        if not self.gemini_model:
            return None

        try:
            from PIL import Image

            pattern_name = self.pattern_data.get('pattern_name', 'Unknown')
            direction = self.pattern_data.get('direction', '')
            side_text = "LONG (compra)" if self.side == 'buy' else "SHORT (venda)"

            prompt = f"""
Atue como um Trader Institucional Sênior.

CONTEXTO:
- Estamos em uma posição {side_text} em {self.symbol}
- Padrão que originou a entrada: {pattern_name} ({direction})
- Preço de entrada: {self.entry_price}
- A linha ciano pontilhada marca o preço de entrada

MISSÃO:
Analise o gráfico ATUALIZADO e determine se o padrão {pattern_name} continua 
tecnicamente válido e se a posição deve ser mantida.

CRITÉRIOS PARA MANTER (VALID):
- Estrutura do padrão preservada
- Preço respeitando suportes/resistências chave
- Sem reversão clara contra a posição
- **PULLBACKS SÃO NORMAIS:** Correções pequenas contra a tendência NÃO invalidam o padrão.
- Só invalide se houver quebra estrutural CLARA (ex: rompimento forte de suporte no Long).

CRITÉRIOS PARA FECHAR (INVALID):
- Padrão claramente desconfigurado
- Quebra de estrutura contra a posição com volume
- Reversão confirmada no price action (não apenas ruído)

Seja TOLERANTE com ruídos de mercado. Só invalide se a tese do trade estiver morta.

Responda ESTRITAMENTE neste formato JSON:
{{
    "verdict": "VALID" ou "INVALID",
    "confidence": 0.0 a 1.0,
    "reasoning": "Explicação técnica breve (max 2 frases)"
}}
"""

            img = Image.open(image_path)
            result = self.gemini_model.generate_content([prompt, img])

            response_text = result.text.replace('```json', '').replace('```', '').strip()
            parsed = json.loads(response_text)

            # Reset contador de falhas consecutivas API
            self.consecutive_api_failures = 0

            return parsed

        except Exception as e:
            self.api_failures_count += 1
            self.consecutive_api_failures += 1
            logger.error(f"❌ Erro Vision AI pós-entrada: {e}")

            # Alerta se falhas consecutivas
            if self.consecutive_api_failures >= self.MAX_CONSECUTIVE_FAILURES:
                self._alert_api_failure(
                    f"Gemini API com {self.consecutive_api_failures} falhas consecutivas "
                    f"para {self.symbol}. Erro: {str(e)[:200]}"
                )

            return None

    def _alert_api_failure(self, message: str):
        """Envia alerta de falha da API via Telegram e log do painel"""
        alert_text = f"🚨 *ALERTA VISION AI*\n\n{message}\n\n⚠️ Posição protegida pelo SL na corretora."

        # Telegram - REATIVADO (nova API key funcionando)
        send_telegram_alert(alert_text)
        logger.info(f"Alertas Telegram reativados: {message[:100]}...")

        # Log do painel
        log_vision_alert(f"🚨 API FAILURE: {message}")

        # Log normal
        logger.warning(f"🚨 ALERTA: {message}")

    def _cleanup_old_images(self):
        """Remove imagens de validação antigas (> 1 hora)"""
        try:
            cutoff = time.time() - 3600
            for f in os.listdir(IMG_DIR):
                if f.startswith('postval_'):
                    fpath = os.path.join(IMG_DIR, f)
                    if os.path.getmtime(fpath) < cutoff:
                        os.remove(fpath)
        except Exception:
            pass

    def should_exit(self) -> Tuple[bool, str]:
        """
        Verifica se devemos sair da posição.
        Só valida no fechamento de candle (não a cada tick).

        Returns:
            (should_exit: bool, reason: str)
        """
        try:
            # Só validar quando um novo candle fechar
            if not self._is_candle_closed():
                return False, ""

            self.validations_count += 1
            logger.info(f"🕯️ Candle fechou - Validação #{self.validations_count} para {self.symbol}")

            # Gerar imagem atualizada
            image_path = self._generate_chart_image()
            if not image_path:
                logger.warning("⚠️ Não foi possível gerar imagem - mantendo posição")
                return False, ""

            # Consultar Vision AI
            ai_result = self._consult_vision_ai(image_path)

            if ai_result is None:
                # API falhou - manter posição (SL protege)
                logger.warning("⚠️ Vision AI indisponível - posição mantida (SL ativo)")
                return False, ""

            verdict = ai_result.get('verdict', 'VALID')
            confidence = ai_result.get('confidence', 0)
            reasoning = ai_result.get('reasoning', '')

            logger.info(f"👁️ Vision AI: {verdict} (conf: {confidence:.2f}) - {reasoning}")

            # Registrar no log do painel
            log_vision_alert(
                f"VALIDATION #{self.validations_count} | {self.symbol} | "
                f"{verdict} ({confidence:.2f}) | {reasoning}"
            )

            if verdict == 'INVALID':
                if confidence >= self.INVALID_CONFIDENCE_THRESHOLD:
                    # Invalidação detectada com alta confiança
                    self.consecutive_invalid_candles += 1
                    
                    if self.consecutive_invalid_candles < self.REQUIRED_INVALID_CANDLES:
                        # Primeiro aviso
                        logger.warning(f"⚠️ AVISO DE INVALIDAÇÃO #1: {self.symbol} ({confidence:.2f}). Aguardando confirmação no próximo candle.")
                        return False, ""
                    else:
                        # Segundo candle consecutivo INVALID -> FECHAR
                        exit_reason = (
                            f"Vision AI: Padrão invalidado em 2 candles consecutivos (conf: {confidence:.2f}). "
                            f"{reasoning}"
                        )

                        # Alerta no Telegram
                        side_emoji = "📈" if self.side == 'buy' else "📉"
                        alert = (
                            f"👁️ *VISION AI - POSIÇÃO FECHADA*\n\n"
                            f"{side_emoji} *{self.symbol}* ({self.side.upper()})\n"
                            f"Entry: `{self.entry_price}`\n"
                            f"Padrão: {self.pattern_data.get('pattern_name', '?')}\n\n"
                            f"❌ *Veredicto: INVALID* (Confirmado 2x)\n"
                            f"📝 {reasoning}\n\n"
                            f"🔄 Validações realizadas: {self.validations_count}"
                        )
                        send_telegram_alert(alert)

                        # Limpar imagens antigas
                        self._cleanup_old_images()

                        return True, exit_reason
                else:
                    # IA incerta (INVALID mas confiança baixa) -> Resetar contador
                    logger.info(
                        f"⚠️ IA acha INVALID mas com baixa confiança ({confidence:.2f}) - "
                        f"mantendo posição e resetando contador."
                    )
                    self.consecutive_invalid_candles = 0 # Reset para exigir 2 fortes seguidos
                    return False, ""

            else:
                # VALID - padrão continua
                logger.info(f"✅ Padrão continua válido para {self.symbol} (conf: {confidence:.2f})")
                self.consecutive_invalid_candles = 0 # Reset contador se voltar a ser VALID
                return False, ""

        except Exception as e:
            logger.error(f"Erro no should_exit: {e}")
            return False, ""


# === TESTE ===
if __name__ == "__main__":
    print("PostEntryValidator v2.3.1 - Vision AI Tolerante")
    print("Integrado no bot_executor.py via loop de monitoramento")

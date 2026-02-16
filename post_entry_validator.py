"""
Validador Pós-Entrada com Vision AI - Bot Sniper V2
ATUALIZAÇÃO: Adiciona monitoramento de mudança de cenário BTC.D

Severino - 2026-02-16
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

logger = logging.getLogger("PostEntryValidatorV2")

# Telegram config
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '')

# Google AI config
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY', '')

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

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        logger.error(f"Erro ao enviar alerta Telegram: {e}")


class PostEntryValidatorV2:
    """
    Validador Pós-Entrada com Vision AI + Monitoramento de Cenário
    """

    def __init__(self, symbol: str, entry_price: float, side: str, timeframe: str = '5m',
                 pattern_name: str = 'Unknown', direction: str = '', neckline: float = None,
                 target: float = None, stop_loss: float = None, entry_scenario: int = 5):
        
        self.symbol = symbol
        self.entry_price = entry_price
        self.side = side  # 'buy' ou 'sell'
        self.timeframe = timeframe
        self.pattern_name = pattern_name
        self.direction = direction  # 'long' ou 'short'
        self.neckline = neckline
        self.target = target
        self.stop_loss = stop_loss
        self.entry_scenario = entry_scenario  # NOVO: Cenário na entrada
        
        self.exchange = ccxt.bybit({
            'enableRateLimit': True,
            'options': {'defaultType': 'linear'}
        })
        
        self.gemini_model = None
        self.setup_gemini()
        
        # Contadores de validação
        self.validation_count = 0
        self.consecutive_invalid = 0
        self.consecutive_valid = 0
        
        # NOVO: Monitor de cenário
        self.market_context_monitor = MarketContextMonitor()
        self.last_scenario_check = 0
        self.scenario_check_interval = 900  # 15 minutos
        
        logger.info(f"👁️ Vision PostValidator V2 inicializado: {symbol} | TF: {timeframe} | Entry Scenario: {entry_scenario}")

    def setup_gemini(self):
        """Configura Gemini Vision AI"""
        if not GOOGLE_API_KEY:
            logger.warning("⚠️ GOOGLE_API_KEY ausente - Vision AI desabilitado")
            return

        try:
            import google.generativeai as genai
            genai.configure(api_key=GOOGLE_API_KEY)
            self.gemini_model = genai.GenerativeModel('gemini-2.0-flash')
            logger.info("✅ Gemini Vision AI configurado para validação pós-entrada")
        except Exception as e:
            logger.error(f"❌ Erro ao configurar Gemini: {e}")

    def _generate_chart_image(self) -> Optional[str]:
        """Gera imagem do gráfico candlestick atual"""
        try:
            # Busca candles suficientes para visualização
            candles = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, limit=50)
            if len(candles) < 10:
                return None

            df = pd.DataFrame(candles, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df['Date'] = pd.to_datetime(df['Date'], unit='ms')
            df.set_index('Date', inplace=True)

            safe_symbol = self.symbol.replace('/', '').replace(':', '')
            timestamp = int(time.time())
            filename = f"{IMG_DIR}/postentry_{safe_symbol}_{timestamp}.png"

            mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', edge='inherit', wick='inherit', volume='in')
            s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds')

            mpf.plot(df, type='candle', volume=False, style=s,
                     savefig=dict(fname=filename, dpi=100, bbox_inches='tight'),
                     title=f"{self.symbol} - {self.pattern_name} (Post-Entry)",
                     axisoff=True)

            return filename

        except Exception as e:
            logger.error(f"Erro ao gerar imagem pós-entrada: {e}")
            return None

    def _cleanup_old_images(self):
        """Remove imagens antigas (> 1 hora)"""
        try:
            cutoff = time.time() - 3600
            for f in os.listdir(IMG_DIR):
                if f.startswith('postentry_'):
                    fpath = os.path.join(IMG_DIR, f)
                    if os.path.getmtime(fpath) < cutoff:
                        os.remove(fpath)
        except Exception:
            pass

    def _check_market_scenario_change(self) -> Tuple[bool, str]:
        """
        NOVO: Verifica se o cenário de mercado mudou significativamente
        Retorna: (should_close: bool, reason: str)
        """
        current_time = time.time()
        
        # Verificar apenas a cada 15 minutos
        if current_time - self.last_scenario_check < self.scenario_check_interval:
            return False, ""
        
        self.last_scenario_check = current_time
        
        try:
            from market_context_validator import MarketContextValidator
            validator = MarketContextValidator(self.exchange)
            
            current_analysis = validator.get_market_analysis()
            current_scenario = current_analysis.get('scenario_number', 5)
            
            logger.info(f"🔍 Verificação de cenário: Entrada={self.entry_scenario}, Atual={current_scenario}")
            
            # Se cenário mudou significativamente
            if self.direction == 'long':
                # LONGs devem ser fechados se cenário mudou para 1 ou 2
                if current_scenario in [1, 2] and self.entry_scenario not in [1, 2]:
                    reason = f"🚨 CENÁRIO MUDOU: {self.entry_scenario} → {current_scenario} (bearish para LONG)"
                    logger.warning(reason)
                    return True, reason
            
            elif self.direction == 'short':
                # SHORTs devem ser fechados se cenário mudou para 3
                if current_scenario == 3 and self.entry_scenario != 3:
                    reason = f"🚨 CENÁRIO MUDOU: {self.entry_scenario} → {current_scenario} (bullish para SHORT)"
                    logger.warning(reason)
                    return True, reason
            
            # Verificar se direção ainda é permitida
            should_trade, trade_reason = validator.should_enter_trade(self.direction.upper(), self.symbol)
            if not should_trade:
                reason = f"🚨 DIREÇÃO NÃO MAIS PERMITIDA: {trade_reason}"
                logger.warning(reason)
                return True, reason
            
            return False, f"Cenário estável: {current_scenario}"
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar cenário: {e}")
            return False, f"Erro na verificação: {str(e)}"

    def validate_with_vision_ai(self) -> Tuple[bool, float, str]:
        """
        Consulta Gemini Vision AI para validar se o padrão continua válido.
        Returns: (is_valid: bool, confidence: float, reasoning: str)
        """
        if not self.gemini_model:
            return True, 0.5, "Vision AI não disponível"

        try:
            image_path = self._generate_chart_image()
            if not image_path:
                return True, 0.5, "Não foi possível gerar imagem"

            from PIL import Image
            
            prompt = f"""
Atue como um Trader Institucional Sênior.

CONTEXTO PÓS-ENTRADA:
- Estamos numa posição {self.side.upper()} em {self.symbol}
- Entramos a ${self.entry_price:.4f} com padrão {self.pattern_name}
- Tempo decorrido desde entrada: {self.validation_count * self._timeframe_to_minutes()} minutos

MISSÃO CRÍTICA:
Analise o gráfico ATUAL e determine se devemos PERMANECER na posição ou FECHAR.

CRITÉRIOS PARA PERMANECER (VALID):
- O padrão gráfico original ainda é reconhecível?
- A estrutura de suporte/resistência ainda é respeitada?
- A tendência ainda favorece nossa direção?
- Não há sinais claros de reversão contra nossa posição.

CRITÉRIOS PARA FECHAR (INVALID):
- O padrão foi claramente quebrado/rompido
- Sinais fortes de reversão contra nossa posição
- A estrutura técnica não suporta mais nossa tese

⚠️ SEJA CONSERVADOR! Prefira fechar cedo do que perder mais.

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
            
            is_valid = (verdict == 'VALID')
            
            return is_valid, confidence, reasoning

        except Exception as e:
            logger.error(f"❌ Erro Vision AI pós-entrada: {e}")
            return True, 0.5, f"Erro na análise: {str(e)}"

    def _timeframe_to_minutes(self) -> int:
        """Converte timeframe para minutos"""
        tf_map = {'1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '4h': 240}
        return tf_map.get(self.timeframe, 15)

    def check_candle_close(self) -> bool:
        """Verifica se o candle fechou (simplificado)"""
        # Implementação simplificada - na prática usar timestamps reais
        return True

    def run_validation_cycle(self):
        """Executa um ciclo completo de validação"""
        self.validation_count += 1
        
        logger.info(f"🕯️ Candle fechou - Validação #{self.validation_count} para {self.symbol}")
        
        # 1. Verificar mudança de cenário (NOVO)
        should_close_scenario, scenario_reason = self._check_market_scenario_change()
        
        if should_close_scenario:
            logger.error(f"🚨 FECHAMENTO POR MUDANÇA DE CENÁRIO: {scenario_reason}")
            self._trigger_closure(scenario_reason)
            return False
        
        # 2. Validação Vision AI
        is_valid, confidence, reasoning = self.validate_with_vision_ai()
        
        if is_valid:
            self.consecutive_valid += 1
            self.consecutive_invalid = 0
            
            logger.info(f"👁️ Vision AI: VALID (conf: {confidence:.2f}) - {reasoning}")
            logger.info(f"✅ Padrão continua válido para {self.symbol} (conf: {confidence:.2f})")
            
            # Alertar se confiança baixa mas ainda válido
            if confidence < 0.60:
                warning_msg = f"⚠️ {self.symbol}: Confiança baixa ({confidence:.2f}) mas ainda válido"
                logger.warning(warning_msg)
                send_telegram_alert(warning_msg)
            
            return True
            
        else:
            self.consecutive_invalid += 1
            self.consecutive_valid = 0
            
            logger.warning(f"👁️ Vision AI: INVALID (conf: {confidence:.2f}) - {reasoning}")
            
            # Exige 2 candles consecutivos INVALID para fechar (v2.3.1)
            if self.consecutive_invalid >= 2:
                closure_reason = f"Padrão invalidado: {reasoning}"
                logger.error(f"🚨 FECHAMENTO DISPARADO: {closure_reason}")
                self._trigger_closure(closure_reason)
                return False
            else:
                logger.info(f"⚠️ Primeira invalidação - Aguardando confirmação no próximo candle")
                return True

    def _trigger_closure(self, reason: str):
        """Dispara fechamento da posição"""
        alert_msg = f"🚨 FECHAMENTO DISPARADO: {self.symbol}\nMotivo: {reason}"
        
        logger.error(alert_msg)
        send_telegram_alert(alert_msg)
        
        # Registrar no log de alertas
        try:
            with open(ALERT_LOG_FILE, 'a') as f:
                f.write(f"{datetime.now().isoformat()} - {alert_msg}\n")
        except Exception as e:
            logger.error(f"Erro ao registrar alerta: {e}")
        
        # Aqui seria chamado o fechamento real da posição
        # Por enquanto apenas log

    def run(self, max_validations: int = 48):
        """
        Loop principal de validação
        max_validations: máximo de candles a validar (ex: 48 candles de 15m = 12 horas)
        """
        logger.info(f"🔄 Iniciando monitoramento pós-entrada para {self.symbol}")
        
        validation_count = 0
        
        while validation_count < max_validations:
            try:
                # Aguardar fechamento do candle
                # Na prática: sleep baseado no timeframe
                sleep_minutes = self._timeframe_to_minutes()
                time.sleep(sleep_minutes * 60)
                
                # Verificar se candle fechou
                if self.check_candle_close():
                    should_continue = self.run_validation_cycle()
                    
                    if not should_continue:
                        logger.info(f"🛑 Monitoramento encerrado para {self.symbol}")
                        break
                    
                    validation_count += 1
                    
            except KeyboardInterrupt:
                logger.info("👋 Monitoramento interrompido pelo usuário")
                break
            except Exception as e:
                logger.error(f"❌ Erro no ciclo de validação: {e}")
                time.sleep(60)  # Esperar 1 minuto antes de tentar novamente
        
        logger.info(f"✅ Monitoramento concluído para {self.symbol} ({validation_count} validações)")


class MarketContextMonitor:
    """Monitor simples de contexto de mercado"""
    
    def __init__(self):
        self.last_check = 0


# Função de conveniência para uso rápido
def create_validator(symbol: str, entry_price: float, side: str, **kwargs) -> PostEntryValidatorV2:
    """Cria um validador pós-entrada"""
    return PostEntryValidatorV2(symbol, entry_price, side, **kwargs)


if __name__ == "__main__":
    # Teste do sistema
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🧪 TESTE DO POST ENTRY VALIDATOR V2")
    print("="*60)
    
    # Simular um trade
    validator = PostEntryValidatorV2(
        symbol="BTC/USDT",
        entry_price=50000,
        side="buy",
        timeframe="15m",
        pattern_name="FUNDO_DUPLO",
        direction="long",
        neckline=49500,
        target=52000,
        stop_loss=49000,
        entry_scenario=3  # Altseason na entrada
    )
    
    print("✅ Validador criado com sucesso")
    print(f"   Symbol: {validator.symbol}")
    print(f"   Entry: ${validator.entry_price}")
    print(f"   Direction: {validator.direction}")
    print(f"   Entry Scenario: {validator.entry_scenario}")
    
    # Testar uma validação
    print("\n🧪 Testando validação...")
    is_valid, confidence, reasoning = validator.validate_with_vision_ai()
    
    print(f"   Resultado: {'VALID' if is_valid else 'INVALID'}")
    print(f"   Confiança: {confidence:.2f}")
    print(f"   Motivo: {reasoning}")
    
    print("\n✅ Teste concluído!")
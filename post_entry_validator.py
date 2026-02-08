"""
Validador Pós-Entrada para Bot Sniper
Severino - 2026-02-08

Monitora trades abertos e invalida padrão se ele se desfizer após entrada.
Reduz drawdown e preserva capital.
"""

import ccxt
import time
import json
import os
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

logger = logging.getLogger("PostEntryValidator")

class PostEntryValidator:
    """
    Valida continuamente se o padrão que gerou a entrada ainda é válido.
    Se invalidar, fecha posição imediatamente (antes do SL).
    """
    
    def __init__(self, exchange: ccxt.bybit, symbol: str, entry_price: float, 
                 side: str, pattern_data: Dict):
        """
        Args:
            exchange: Instância do ccxt Bybit
            symbol: Par negociado (ex: BTC/USDT)
            entry_price: Preço de entrada
            side: 'buy' ou 'sell'
            pattern_data: Dict com info do padrão original
                {
                    'pattern_name': 'HCO',
                    'direction': 'bullish',
                    'neckline': 50000,
                    'target': 52000,
                    'stop_loss': 49000
                }
        """
        self.exchange = exchange
        self.symbol = symbol
        self.entry_price = entry_price
        self.side = side
        self.pattern_data = pattern_data
        self.entry_time = time.time()
        
        # Configurações de invalidação
        self.MAX_ADVERSE_MOVE_PCT = 0.3  # 0.3% contra = invalidar
        self.MAX_TIME_NO_PROGRESS_SEC = 300  # 5 min sem progresso
        self.MIN_CANDLES_TO_VALIDATE = 2  # Valida após 2 candles
        
    def should_exit(self) -> Tuple[bool, str]:
        """
        Verifica se devemos sair da posição.
        
        Returns:
            (should_exit: bool, reason: str)
        """
        try:
            # 1. INVALIDAÇÃO POR PREÇO (Price Action)
            current_price = self._get_current_price()
            if current_price is None:
                return False, ""
            
            adverse_move = self._calculate_adverse_move(current_price)
            if adverse_move > self.MAX_ADVERSE_MOVE_PCT:
                return True, f"Movimento adverso de {adverse_move:.2f}% (limite {self.MAX_ADVERSE_MOVE_PCT}%)"
            
            # 2. INVALIDAÇÃO POR PADRÃO (Pattern Breakdown)
            # Só valida após alguns candles para evitar false positives
            time_in_trade = time.time() - self.entry_time
            if time_in_trade > 60:  # Após 1 minuto
                pattern_valid, reason = self._validate_pattern()
                if not pattern_valid:
                    return True, f"Padrão invalidado: {reason}"
            
            # 3. INVALIDAÇÃO POR TEMPO (No Progress)
            if time_in_trade > self.MAX_TIME_NO_PROGRESS_SEC:
                progress = self._calculate_progress(current_price)
                if abs(progress) < 0.1:  # Menos de 0.1% de movimento
                    return True, f"Sem progresso após {time_in_trade/60:.1f} minutos"
            
            # 4. INVALIDAÇÃO POR CANDLE DE REVERSÃO
            if time_in_trade > 30:  # Após 30 segundos
                reversal = self._check_reversal_candle()
                if reversal:
                    return True, "Candle de reversão detectado"
            
            return False, ""
            
        except Exception as e:
            logger.error(f"Erro ao validar saída: {e}")
            return False, ""
    
    def _get_current_price(self) -> Optional[float]:
        """Obtém preço atual do par"""
        try:
            ticker = self.exchange.fetch_ticker(self.symbol)
            return float(ticker['last'])
        except Exception as e:
            logger.error(f"Erro ao buscar preço: {e}")
            return None
    
    def _calculate_adverse_move(self, current_price: float) -> float:
        """
        Calcula movimento adverso (contra nossa posição) em %.
        
        Returns:
            % de movimento adverso (positivo = contra nós)
        """
        if self.side == 'buy':
            # Long: adverso = preço caiu
            move_pct = ((current_price - self.entry_price) / self.entry_price) * 100
            return abs(min(0, move_pct))  # Retorna só se negativo
        else:
            # Short: adverso = preço subiu
            move_pct = ((self.entry_price - current_price) / self.entry_price) * 100
            return abs(min(0, move_pct))
    
    def _calculate_progress(self, current_price: float) -> float:
        """
        Calcula progresso em direção ao target (em %).
        Positivo = indo na direção certa, Negativo = indo contra
        """
        if self.side == 'buy':
            return ((current_price - self.entry_price) / self.entry_price) * 100
        else:
            return ((self.entry_price - current_price) / self.entry_price) * 100
    
    def _validate_pattern(self) -> Tuple[bool, str]:
        """
        Revalida o padrão gráfico.
        Verifica se ainda existe e se não mudou de direção.
        
        Returns:
            (is_valid: bool, reason: str)
        """
        try:
            # Busca candles atuais
            timeframe = '15m'  # Ajustar conforme config
            candles = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=20)
            
            if len(candles) < 10:
                return True, ""  # Dados insuficientes, mantém posição
            
            # Extrai preços
            closes = [c[4] for c in candles]
            highs = [c[2] for c in candles]
            lows = [c[3] for c in candles]
            
            # VALIDAÇÕES ESPECÍFICAS POR PADRÃO
            pattern_name = self.pattern_data.get('pattern_name', '').upper()
            direction = self.pattern_data.get('direction', '')
            
            # 1. Verifica se neckline/suporte foi quebrada
            neckline = self.pattern_data.get('neckline')
            if neckline:
                if direction == 'bullish' and closes[-1] < neckline:
                    return False, f"Suporte {neckline} quebrado (bullish invalidado)"
                elif direction == 'bearish' and closes[-1] > neckline:
                    return False, f"Resistência {neckline} quebrada (bearish invalidado)"
            
            # 2. Verifica se houve reversão clara (3 candles na direção oposta)
            if len(closes) >= 5:
                last_3_candles = closes[-3:]
                if direction == 'bullish':
                    # Bullish: espera closes crescentes. Se 3 quedas seguidas = invalidado
                    if all(last_3_candles[i] > last_3_candles[i+1] for i in range(len(last_3_candles)-1)):
                        return False, "3 candles de queda consecutivos (bullish invalidado)"
                else:
                    # Bearish: espera closes decrescentes. Se 3 altas seguidas = invalidado
                    if all(last_3_candles[i] < last_3_candles[i+1] for i in range(len(last_3_candles)-1)):
                        return False, "3 candles de alta consecutivos (bearish invalidado)"
            
            # 3. Verifica volume (se disponível)
            # TODO: Implementar validação por volume
            
            return True, ""
            
        except Exception as e:
            logger.error(f"Erro ao validar padrão: {e}")
            return True, ""  # Em caso de erro, mantém posição (conservador)
    
    def _check_reversal_candle(self) -> bool:
        """
        Detecta candles de reversão fortes (engolfo, martelo invertido, etc.)
        
        Returns:
            True se detectou reversão contra nossa posição
        """
        try:
            # Busca últimos 3 candles
            timeframe = '5m'  # Timeframe menor para detecção rápida
            candles = self.exchange.fetch_ohlcv(self.symbol, timeframe, limit=3)
            
            if len(candles) < 2:
                return False
            
            # Último candle fechado (penúltimo da lista, pois último ainda está aberto)
            last = candles[-2]
            prev = candles[-3] if len(candles) >= 3 else candles[-2]
            
            open_price = last[1]
            high = last[2]
            low = last[3]
            close = last[4]
            
            body = abs(close - open_price)
            upper_wick = high - max(close, open_price)
            lower_wick = min(close, open_price) - low
            
            # LONG: reversal bearish (martelo invertido, shooting star)
            if self.side == 'buy':
                # Shooting star: corpo pequeno no topo, pavio superior grande
                if upper_wick > body * 2 and close < open_price:
                    return True
                # Engolfo bearish: candle bearish que engole anterior bullish
                prev_bullish = candles[-3][4] > candles[-3][1]
                current_bearish = close < open_price
                if prev_bullish and current_bearish and body > abs(candles[-3][4] - candles[-3][1]):
                    return True
            
            # SHORT: reversal bullish (martelo, morning star)
            else:
                # Martelo: corpo pequeno no fundo, pavio inferior grande
                if lower_wick > body * 2 and close > open_price:
                    return True
                # Engolfo bullish
                prev_bearish = candles[-3][4] < candles[-3][1]
                current_bullish = close > open_price
                if prev_bearish and current_bullish and body > abs(candles[-3][4] - candles[-3][1]):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erro ao checar candle de reversão: {e}")
            return False


# === EXEMPLO DE USO ===
if __name__ == "__main__":
    # Teste básico (requer credenciais)
    print("Post Entry Validator - Teste")
    print("Para usar: integrar no bot_executor.py no loop de monitoramento")

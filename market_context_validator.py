#!/usr/bin/env python3
"""
🎯 VALIDADOR DE CONTEXTO DE MERCADO (BTC + BTC.D)
Baseado no PROTOCOLO SEVERINO
"""

import ccxt
import time
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger("MarketContextValidator")

class MarketContextValidator:
    """
    Valida contexto de mercado baseado em BTC trend + BTC.D
    Implementa o PROTOCOLO SEVERINO de cenários
    """
    
    def __init__(self, exchange: ccxt.bybit = None):
        self.exchange = exchange or ccxt.bybit({
            'enableRateLimit': True,
            'options': {'defaultType': 'linear'}
        })
        self.last_analysis = None
        self.last_update = 0
        self.cache_duration = 300  # 5 minutos
    
    def get_market_analysis(self) -> Dict:
        """
        Análise completa de mercado (BTC + BTC.D + Cenário)
        Retorna: {
            'btc_trend': 'LONG/SHORT/NEUTRAL',
            'btcd_trend': 'LONG/SHORT/NEUTRAL',
            'btcd_source': 'webhook/proxy',
            'scenario_number': 1-5,
            'scenario_name': str,
            'scenario_description': str,
            'should_trade_long': bool,
            'should_trade_short': bool,
            'timestamp': int
        }
        """
        # Usar cache se recente
        current_time = time.time()
        if self.last_analysis and (current_time - self.last_update) < self.cache_duration:
            return self.last_analysis
        
        try:
            # Importar funções do lib_utils
            from lib_utils import get_market_analysis as lib_get_market_analysis
            
            analysis = lib_get_market_analysis(self.exchange)
            
            # Adicionar regras de trading baseadas no cenário
            scenario = analysis.get('scenario_number', 5)
            
            # PROTOCOLO SEVERINO - Regras de trading
            should_trade_long = True
            should_trade_short = True
            trading_rules = ""
            
            if scenario == 1:  # BTC ↗ + BTC.D ↗
                should_trade_long = False
                should_trade_short = True
                trading_rules = "⚠️ Evitar LONGs em alts (dinheiro indo pro BTC)"
                
            elif scenario == 2:  # BTC ↘ + BTC.D ↗
                should_trade_long = False
                should_trade_short = True
                trading_rules = "⚠️ SHORTs favorecidos (pânico nas alts)"
                
            elif scenario == 3:  # BTC ↗ + BTC.D ↘
                should_trade_long = True
                should_trade_short = False
                trading_rules = "✅ MELHOR cenário para LONGs em alts (Altseason)"
                
            elif scenario == 4:  # BTC ↘ + BTC.D ↘
                should_trade_long = True
                should_trade_short = True
                trading_rules = "⚠️ Alts segurando (permite ambos com cautela)"
                
            else:  # Cenário 5 ou desconhecido
                should_trade_long = True
                should_trade_short = True
                trading_rules = "ℹ️ Mercado lateral (permite ambos)"
            
            # Resultado completo
            result = {
                **analysis,
                'should_trade_long': should_trade_long,
                'should_trade_short': should_trade_short,
                'trading_rules': trading_rules,
                'timestamp': int(current_time),
                'human_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            # Atualizar cache
            self.last_analysis = result
            self.last_update = current_time
            
            logger.info(f"📊 Análise mercado: Cenário {scenario} - {analysis.get('scenario_name')}")
            logger.info(f"   Regras: {trading_rules}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Erro na análise de mercado: {e}")
            
            # Fallback: cenário neutro
            return {
                'btc_trend': 'NEUTRAL',
                'btcd_trend': 'NEUTRAL',
                'btcd_source': 'error',
                'scenario_number': 5,
                'scenario_name': 'FALLBACK',
                'scenario_description': 'Erro na análise - usando fallback',
                'should_trade_long': True,  # Permite por segurança
                'should_trade_short': True,
                'trading_rules': '⚠️ Fallback ativado (erro na análise)',
                'timestamp': int(time.time()),
                'human_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def should_enter_trade(self, direction: str, symbol: str = None) -> Tuple[bool, str]:
        """
        Verifica se deve entrar em trade baseado no contexto
        Retorna: (deve_entrar: bool, motivo: str)
        """
        direction = direction.upper()
        
        if direction not in ['LONG', 'SHORT']:
            return False, f"Direção inválida: {direction}"
        
        analysis = self.get_market_analysis()
        scenario = analysis.get('scenario_number', 5)
        
        # Verificar regras do PROTOCOLO SEVERINO
        if direction == 'LONG':
            should_trade = analysis.get('should_trade_long', True)
            if not should_trade:
                return False, f"Cenário {scenario}: {analysis.get('trading_rules', 'LONG não permitido')}"
        
        elif direction == 'SHORT':
            should_trade = analysis.get('should_trade_short', True)
            if not should_trade:
                return False, f"Cenário {scenario}: {analysis.get('trading_rules', 'SHORT não permitido')}"
        
        # Se passou todas as validações
        scenario_name = analysis.get('scenario_name', 'Desconhecido')
        return True, f"Cenário {scenario} ({scenario_name}): OK para {direction}"
    
    def check_and_close_if_scenario_changed(self, open_trades: Dict) -> Dict:
        """
        Verifica trades abertos e fecha se cenário mudou
        open_trades: {symbol: {'direction': 'LONG/SHORT', 'entry_scenario': int, ...}}
        Retorna: {symbol: {'should_close': bool, 'reason': str, ...}}
        """
        current_analysis = self.get_market_analysis()
        current_scenario = current_analysis.get('scenario_number', 5)
        
        results = {}
        
        for symbol, trade_info in open_trades.items():
            direction = trade_info.get('direction', '').upper()
            entry_scenario = trade_info.get('entry_scenario', 5)
            
            should_close = False
            reason = ""
            
            # Se cenário mudou significativamente
            if direction == 'LONG':
                # LONGs devem ser fechados se cenário mudou para 1 ou 2
                if current_scenario in [1, 2] and entry_scenario not in [1, 2]:
                    should_close = True
                    reason = f"Cenário mudou de {entry_scenario} para {current_scenario} (bearish para LONG)"
            
            elif direction == 'SHORT':
                # SHORTs devem ser fechados se cenário mudou para 3
                if current_scenario == 3 and entry_scenario != 3:
                    should_close = True
                    reason = f"Cenário mudou de {entry_scenario} para {current_scenario} (bullish para SHORT)"
            
            # Se direção não é mais permitida no cenário atual
            if not should_close:
                can_trade, trade_reason = self.should_enter_trade(direction, symbol)
                if not can_trade:
                    should_close = True
                    reason = f"Direção {direction} não mais permitida: {trade_reason}"
            
            results[symbol] = {
                'should_close': should_close,
                'reason': reason,
                'current_scenario': current_scenario,
                'entry_scenario': entry_scenario,
                'direction': direction,
                'symbol': symbol
            }
        
        return results
    
    def get_trading_rules_summary(self) -> str:
        """Retorna resumo das regras de trading atuais"""
        analysis = self.get_market_analysis()
        
        scenario = analysis.get('scenario_number', 5)
        name = analysis.get('scenario_name', 'Desconhecido')
        desc = analysis.get('scenario_description', '')
        rules = analysis.get('trading_rules', '')
        
        summary = f"""
📊 CENÁRIO DE MERCADO: {scenario} - {name}
📝 {desc}
🎯 REGRAS: {rules}

✅ PERMITIDO: {'LONG' if analysis.get('should_trade_long') else '❌ LONG'} | {'SHORT' if analysis.get('should_trade_short') else '❌ SHORT'}
📈 BTC Trend: {analysis.get('btc_trend', 'N/A')}
📉 BTC.D Trend: {analysis.get('btcd_trend', 'N/A')} (via {analysis.get('btcd_source', 'N/A')})
🕐 Atualizado: {analysis.get('human_time', 'N/A')}
"""
        return summary


# Função de conveniência para uso rápido
def validate_trade_entry(direction: str, symbol: str = None) -> Tuple[bool, str]:
    """Validação rápida para entrada de trade"""
    validator = MarketContextValidator()
    return validator.should_enter_trade(direction, symbol)

def get_current_market_summary() -> str:
    """Resumo rápido do mercado atual"""
    validator = MarketContextValidator()
    return validator.get_trading_rules_summary()

if __name__ == "__main__":
    # Teste do sistema
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🧪 TESTE DO VALIDADOR DE CONTEXTO DE MERCADO")
    print("="*60)
    
    validator = MarketContextValidator()
    
    # Obter análise atual
    analysis = validator.get_market_analysis()
    
    print("\n📊 ANÁLISE ATUAL:")
    print(f"  Cenário: {analysis.get('scenario_number')} - {analysis.get('scenario_name')}")
    print(f"  Descrição: {analysis.get('scenario_description')}")
    print(f"  Regras: {analysis.get('trading_rules')}")
    print(f"  BTC Trend: {analysis.get('btc_trend')}")
    print(f"  BTC.D Trend: {analysis.get('btcd_trend')} (via {analysis.get('btcd_source')})")
    
    print("\n🎯 TESTE DE VALIDAÇÃO:")
    
    # Testar validações
    test_directions = ['LONG', 'SHORT']
    
    for direction in test_directions:
        should_enter, reason = validator.should_enter_trade(direction)
        status = "✅" if should_enter else "❌"
        print(f"  {status} {direction}: {reason}")
    
    print("\n📋 RESUMO COMPLETO:")
    print(validator.get_trading_rules_summary())
    
    # Simular trades abertos
    print("\n🧪 SIMULAÇÃO DE MONITORAMENTO:")
    open_trades = {
        'BTC/USDT': {'direction': 'LONG', 'entry_scenario': 3},
        'ETH/USDT': {'direction': 'SHORT', 'entry_scenario': 2},
    }
    
    close_decisions = validator.check_and_close_if_scenario_changed(open_trades)
    
    for symbol, decision in close_decisions.items():
        action = "FECHAR" if decision['should_close'] else "MANTER"
        print(f"  {symbol} ({decision['direction']}): {action} - {decision.get('reason', 'N/A')}")
    
    print("\n✅ Sistema pronto para integração!")
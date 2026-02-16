#!/usr/bin/env python3
"""
🧠 BRAIN INTEGRATION - Integração do Sistema de Aprendizado com o Bot
"""

import logging
import time
import json
import os
from datetime import datetime
from typing import Dict, Optional

# Importar módulos do bot
try:
    from lib_utils import get_market_analysis
    import ccxt
except ImportError:
    print("⚠️ Módulos do bot não encontrados. Executando em modo standalone.")

# Importar brain trainer
try:
    from brain_trainer import BrainTrainer
    BRAIN_AVAILABLE = True
except ImportError:
    print("⚠️ Brain Trainer não disponível. Execute setup primeiro.")
    BRAIN_AVAILABLE = False

logger = logging.getLogger("BrainIntegration")

class BrainIntegration:
    """
    Integra o sistema de aprendizado com o bot operacional
    """
    
    def __init__(self):
        self.brain_trainer = None
        self.exchange = None
        self.market_context = None
        
        if BRAIN_AVAILABLE:
            self.brain_trainer = BrainTrainer()
            logger.info("✅ Brain Integration inicializado")
        else:
            logger.warning("⚠️ Brain Integration em modo fallback (sem aprendizado)")
    
    def initialize(self):
        """Inicializa o sistema"""
        if not BRAIN_AVAILABLE:
            return False
        
        try:
            # Conectar ao database
            self.brain_trainer.connect_db()
            
            # Inicializar exchange para contexto de mercado
            self.exchange = ccxt.bybit({
                'enableRateLimit': True,
                'options': {'defaultType': 'linear'}
            })
            
            # Treinamento inicial rápido
            self.brain_trainer.train_offline(episodes=10)
            
            logger.info("✅ Brain Integration inicializado com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar Brain Integration: {e}")
            return False
    
    def update_market_context(self):
        """Atualiza contexto de mercado"""
        try:
            if self.exchange:
                self.market_context = get_market_analysis(self.exchange)
                logger.debug(f"📊 Contexto de mercado: {self.market_context.get('scenario_name')}")
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar contexto: {e}")
            self.market_context = None
    
    def should_enter_trade(self, pattern_data: Dict) -> Dict:
        """
        Decide se deve entrar no trade usando o cérebro
        Retorna: {
            'decision': 'ENTER' ou 'SKIP',
            'confidence': 0.0-1.0,
            'reason': 'explicação',
            'brain_advice': 'ENTER_LONG'/'ENTER_SHORT'/'SKIP'
        }
        """
        if not BRAIN_AVAILABLE or not self.brain_trainer:
            # Fallback: aprova tudo (comportamento antigo)
            return {
                'decision': 'ENTER',
                'confidence': 0.5,
                'reason': 'Brain não disponível - usando fallback',
                'brain_advice': 'ENTER_LONG' if pattern_data.get('direction') == 'LONG' else 'ENTER_SHORT'
            }
        
        try:
            # Atualizar contexto de mercado
            self.update_market_context()
            
            # Extrair features do estado
            state = self.brain_trainer.extract_state_features(pattern_data, self.market_context)
            
            # Pedir decisão ao cérebro
            action, confidence = self.brain_trainer.predict(state)
            
            # Traduzir ação para decisão
            if action == 'SKIP':
                decision = 'SKIP'
                reason = f"Brain recomendou SKIP (conf: {confidence:.2f})"
            else:
                # Verificar se ação combina com direção do padrão
                pattern_direction = pattern_data.get('direction', 'NEUTRAL')
                action_matches = (
                    (action == 'ENTER_LONG' and pattern_direction == 'LONG') or
                    (action == 'ENTER_SHORT' and pattern_direction == 'SHORT')
                )
                
                if action_matches:
                    decision = 'ENTER'
                    reason = f"Brain recomendou {action} (conf: {confidence:.2f})"
                else:
                    decision = 'SKIP'
                    reason = f"Brain recomendou {action} mas padrão é {pattern_direction} (conf: {confidence:.2f})"
            
            return {
                'decision': decision,
                'confidence': confidence,
                'reason': reason,
                'brain_advice': action,
                'state_features': state
            }
            
        except Exception as e:
            logger.error(f"❌ Erro na decisão do brain: {e}")
            return {
                'decision': 'ENTER',  # Fallback seguro
                'confidence': 0.3,
                'reason': f'Erro no brain: {str(e)}',
                'brain_advice': 'SKIP'
            }
    
    def record_trade_result(self, trade_data: Dict):
        """
        Registra resultado do trade para aprendizado futuro
        trade_data: {
            'symbol': str,
            'entry_price': float,
            'exit_price': float,
            'entry_time': timestamp,
            'exit_time': timestamp,
            'direction': 'LONG'/'SHORT',
            'profit_pct': float,
            'pattern': str,
            'timeframe': str,
            'ai_confidence': float,
            'brain_decision': Dict (from should_enter_trade)
        }
        """
        if not BRAIN_AVAILABLE or not self.brain_trainer:
            return
        
        try:
            # Calcular recompensa
            reward = self.brain_trainer.brain.calculate_reward({
                'profit_pct': trade_data.get('profit_pct', 0),
                'duration_hours': (trade_data.get('exit_time', 0) - trade_data.get('entry_time', 0)) / 3600,
                'max_drawdown': trade_data.get('max_drawdown', 0)
            })
            
            # Estado original (da decisão)
            original_state = trade_data.get('brain_decision', {}).get('state_features', {})
            
            # Próximo estado (após trade)
            next_state = original_state  # Por enquanto, mesmo estado
            
            # Atualizar Q-learning
            action = trade_data.get('brain_decision', {}).get('brain_advice', 'SKIP')
            self.brain_trainer.brain.update(
                state=original_state,
                action=action,
                reward=reward,
                next_state=next_state,
                done=True
            )
            
            # Experience replay
            self.brain_trainer.brain.experience_replay(batch_size=16)
            
            # Salvar modelo periodicamente
            if self.brain_trainer.brain.training_stats['episodes'] % 10 == 0:
                self.brain_trainer.brain.save_model()
            
            logger.info(f"📝 Trade registrado: {trade_data['symbol']} | Reward: {reward:.2f} | Profit: {trade_data.get('profit_pct', 0):.2f}%")
            
        except Exception as e:
            logger.error(f"❌ Erro ao registrar trade: {e}")
    
    def get_brain_stats(self) -> Dict:
        """Retorna estatísticas do cérebro"""
        if not BRAIN_AVAILABLE or not self.brain_trainer:
            return {'status': 'NOT_AVAILABLE'}
        
        try:
            stats = self.brain_trainer.brain.get_stats()
            stats['status'] = 'ACTIVE'
            stats['market_context'] = self.market_context
            return stats
        except Exception as e:
            return {'status': 'ERROR', 'error': str(e)}
    
    def continuous_learning(self, interval_minutes=60):
        """
        Executa aprendizado contínuo em background
        """
        if not BRAIN_AVAILABLE:
            return
        
        logger.info(f"🔄 Iniciando aprendizado contínuo (intervalo: {interval_minutes}min)")
        
        while True:
            try:
                # Treinamento offline periódico
                self.brain_trainer.train_offline(episodes=5)
                
                # Salvar modelo
                self.brain_trainer.brain.save_model()
                
                # Log estatísticas
                stats = self.get_brain_stats()
                logger.info(f"🧠 Aprendizado contínuo: {stats.get('states', 0)} estados | Win rate: {stats.get('win_rate', 0):.2f}")
                
                # Aguardar próximo ciclo
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"❌ Erro no aprendizado contínuo: {e}")
                time.sleep(300)  # 5 minutos antes de tentar novamente


# Integração com o bot_monitor.py existente
def integrate_with_monitor():
    """
    Função para integrar com o bot_monitor.py existente
    """
    brain_integration = BrainIntegration()
    
    if brain_integration.initialize():
        print("✅ Brain Integration pronto para uso")
        
        # Exemplo de uso:
        # No bot_monitor.py, substituir a decisão de entrada por:
        """
        # ANTES (linha ~130 em bot_monitor.py):
        if acionar_gatilho:
            disparar_trade(wl, real_idx, preco_atual)
        
        # DEPOIS:
        if acionar_gatilho:
            # Consultar o cérebro
            brain_decision = brain_integration.should_enter_trade(par)
            
            if brain_decision['decision'] == 'ENTER':
                disparar_trade(wl, real_idx, preco_atual)
                # Registrar decisão para tracking
                par['brain_decision'] = brain_decision
            else:
                logger.info(f"🧠 Brain rejeitou entrada: {brain_decision['reason']}")
                # Opcional: remover do watchlist
        """
        
        return brain_integration
    else:
        print("⚠️ Brain Integration falhou. Usando fallback.")
        return None


if __name__ == "__main__":
    # Teste do sistema
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("🧠 TESTE DO BRAIN INTEGRATION")
    print("=" * 50)
    
    brain = BrainIntegration()
    
    if brain.initialize():
        print("✅ Sistema inicializado")
        
        # Testar decisão com dados de exemplo
        test_pattern = {
            'symbol': 'BTC/USDT',
            'timeframe': '15m',
            'pattern': 'OCO',
            'direction': 'LONG',
            'ai_confidence': 0.8,
            'neckline': 50000,
            'stop_loss': 49000,
            'target': 52000
        }
        
        decision = brain.should_enter_trade(test_pattern)
        print(f"\n📊 Decisão de teste:")
        print(f"  Ação: {decision['decision']}")
        print(f"  Confiança: {decision['confidence']:.2f}")
        print(f"  Razão: {decision['reason']}")
        print(f"  Conselho: {decision['brain_advice']}")
        
        # Mostrar estatísticas
        stats = brain.get_brain_stats()
        print(f"\n📈 Estatísticas do cérebro:")
        for key, value in stats.items():
            if key not in ['market_context']:
                print(f"  {key}: {value}")
        
        print("\n🎯 Sistema pronto para integração com o bot!")
        
        # Iniciar aprendizado contínuo em background (opcional)
        # import threading
        # learning_thread = threading.Thread(target=brain.continuous_learning, daemon=True)
        # learning_thread.start()
        # print("🔄 Aprendizado contínuo iniciado em background")
        
    else:
        print("❌ Falha na inicialização")
        sys.exit(1)
#!/usr/bin/env python3
"""
🧠 BRAIN TRAINER - Sistema de Aprendizado End-to-End
Modelo: Q-Learning Avançado com Experience Replay
"""

import sqlite3
import json
import numpy as np
import pickle
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import random
from collections import deque
import math

# Configuração
logger = logging.getLogger("BrainTrainer")
DB_NAME = 'sniper_brain.db'
MODEL_PATH = 'brain_models/q_learning_model.pkl'

class QLearningBrain:
    """
    Sistema de Q-Learning avançado para trading
    """
    
    def __init__(self, alpha=0.1, gamma=0.9, epsilon=0.3):
        self.alpha = alpha  # Taxa de aprendizado
        self.gamma = gamma  # Fator de desconto
        self.epsilon = epsilon  # Exploração vs Exploração
        
        # Q-table: estado -> ação -> valor
        self.q_table = {}
        
        # Experience replay
        self.memory = deque(maxlen=10000)
        
        # Estatísticas
        self.training_stats = {
            'episodes': 0,
            'total_reward': 0,
            'wins': 0,
            'losses': 0,
            'last_update': None
        }
        
        # Carregar modelo se existir
        self.load_model()
    
    def _state_to_key(self, state: Dict) -> str:
        """Converte estado para chave da Q-table"""
        # Features principais para estado
        features = [
            state.get('pattern', 'UNKNOWN'),
            state.get('timeframe', '15m'),
            state.get('direction', 'NEUTRAL'),
            state.get('ai_confidence', 0),
            state.get('market_scenario', 5),
            state.get('btc_trend', 'NEUTRAL'),
            state.get('btcd_trend', 'NEUTRAL')
        ]
        return '|'.join(str(f) for f in features)
    
    def _get_actions(self) -> List[str]:
        """Lista de ações possíveis"""
        return ['ENTER_LONG', 'ENTER_SHORT', 'SKIP']
    
    def get_action(self, state: Dict) -> str:
        """
        Escolhe ação baseada na política ε-greedy
        """
        state_key = self._state_to_key(state)
        
        # Inicializar estado se não existir
        if state_key not in self.q_table:
            self.q_table[state_key] = {a: 0.0 for a in self._get_actions()}
        
        # ε-greedy: explorar ou explorar
        if random.random() < self.epsilon:
            # Explorar: ação aleatória
            return random.choice(self._get_actions())
        else:
            # Explorar: melhor ação
            q_values = self.q_table[state_key]
            return max(q_values, key=q_values.get)
    
    def update(self, state: Dict, action: str, reward: float, next_state: Dict, done: bool):
        """
        Atualiza Q-value usando fórmula Q-Learning
        """
        state_key = self._state_to_key(state)
        next_state_key = self._state_to_key(next_state)
        
        # Inicializar se necessário
        if state_key not in self.q_table:
            self.q_table[state_key] = {a: 0.0 for a in self._get_actions()}
        if next_state_key not in self.q_table:
            self.q_table[next_state_key] = {a: 0.0 for a in self._get_actions()}
        
        # Valor Q atual
        current_q = self.q_table[state_key][action]
        
        # Melhor valor Q do próximo estado
        if done:
            next_max_q = 0
        else:
            next_max_q = max(self.q_table[next_state_key].values())
        
        # Fórmula Q-Learning
        new_q = current_q + self.alpha * (reward + self.gamma * next_max_q - current_q)
        
        # Atualizar Q-table
        self.q_table[state_key][action] = new_q
        
        # Salvar experiência para replay
        self.memory.append((state_key, action, reward, next_state_key, done))
        
        # Atualizar estatísticas
        self.training_stats['total_reward'] += reward
        if reward > 0:
            self.training_stats['wins'] += 1
        elif reward < 0:
            self.training_stats['losses'] += 1
        
        return new_q
    
    def experience_replay(self, batch_size=32):
        """
        Treina com experiências passadas (replay)
        """
        if len(self.memory) < batch_size:
            return
        
        batch = random.sample(list(self.memory), batch_size)
        
        for state_key, action, reward, next_state_key, done in batch:
            # Garantir que estados existam
            if state_key not in self.q_table:
                self.q_table[state_key] = {a: 0.0 for a in self._get_actions()}
            if next_state_key not in self.q_table:
                self.q_table[next_state_key] = {a: 0.0 for a in self._get_actions()}
            
            # Atualizar
            current_q = self.q_table[state_key][action]
            next_max_q = 0 if done else max(self.q_table[next_state_key].values())
            new_q = current_q + self.alpha * (reward + self.gamma * next_max_q - current_q)
            self.q_table[state_key][action] = new_q
    
    def calculate_reward(self, trade_result: Dict) -> float:
        """
        Calcula recompensa baseada no resultado do trade
        """
        profit_pct = trade_result.get('profit_pct', 0)
        duration_hours = trade_result.get('duration_hours', 1)
        
        # Recompensa base: profit percentual
        reward = profit_pct
        
        # Penalizar trades longos (oportunidade custo)
        if duration_hours > 24:
            reward -= 0.5
        
        # Bônus para trades rápidos e lucrativos
        if profit_pct > 2 and duration_hours < 6:
            reward += 1.0
        
        # Penalizar grandes drawdowns
        max_drawdown = trade_result.get('max_drawdown', 0)
        if max_drawdown > 5:
            reward -= 2.0
        
        return reward
    
    def save_model(self):
        """Salva modelo em disco"""
        try:
            import os
            os.makedirs('brain_models', exist_ok=True)
            
            model_data = {
                'q_table': self.q_table,
                'training_stats': self.training_stats,
                'alpha': self.alpha,
                'gamma': self.gamma,
                'epsilon': self.epsilon,
                'saved_at': datetime.now().isoformat()
            }
            
            with open(MODEL_PATH, 'wb') as f:
                pickle.dump(model_data, f)
            
            logger.info(f"✅ Modelo salvo: {MODEL_PATH}")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao salvar modelo: {e}")
            return False
    
    def load_model(self):
        """Carrega modelo do disco"""
        try:
            import os
            if os.path.exists(MODEL_PATH):
                with open(MODEL_PATH, 'rb') as f:
                    model_data = pickle.load(f)
                
                self.q_table = model_data.get('q_table', {})
                self.training_stats = model_data.get('training_stats', self.training_stats)
                self.alpha = model_data.get('alpha', 0.1)
                self.gamma = model_data.get('gamma', 0.9)
                self.epsilon = model_data.get('epsilon', 0.3)
                
                logger.info(f"✅ Modelo carregado: {len(self.q_table)} estados")
                return True
        except Exception as e:
            logger.error(f"❌ Erro ao carregar modelo: {e}")
        
        return False
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas do modelo"""
        total_trades = self.training_stats['wins'] + self.training_stats['losses']
        win_rate = self.training_stats['wins'] / max(1, total_trades)
        avg_reward = self.training_stats['total_reward'] / max(1, self.training_stats['episodes'])
        
        return {
            'states': len(self.q_table),
            'memory_size': len(self.memory),
            'episodes': self.training_stats['episodes'],
            'total_reward': self.training_stats['total_reward'],
            'win_rate': win_rate,
            'avg_reward': avg_reward,
            'last_update': self.training_stats.get('last_update')
        }


class BrainTrainer:
    """
    Sistema principal de treinamento end-to-end
    """
    
    def __init__(self):
        self.brain = QLearningBrain()
        self.db_conn = None
        
    def connect_db(self):
        """Conecta ao database"""
        try:
            self.db_conn = sqlite3.connect(DB_NAME)
            logger.info(f"✅ Conectado ao database: {DB_NAME}")
            return True
        except Exception as e:
            logger.error(f"❌ Erro ao conectar ao database: {e}")
            return False
    
    def get_training_data(self, limit=1000) -> List[Dict]:
        """
        Busca dados de treinamento do database
        """
        if not self.db_conn:
            self.connect_db()
        
        try:
            cursor = self.db_conn.cursor()
            
            # Buscar amostras com validação AI
            query = """
            SELECT 
                id, symbol, timeframe, timestamp_detection,
                pattern_detected, direction, ohlcv_json,
                ai_verdict, ai_confidence, ai_reasoning,
                status
            FROM raw_samples 
            WHERE ai_verdict IS NOT NULL 
            ORDER BY timestamp_detection DESC 
            LIMIT ?
            """
            
            cursor.execute(query, (limit,))
            rows = cursor.fetchall()
            
            training_data = []
            for row in rows:
                data = {
                    'id': row[0],
                    'symbol': row[1],
                    'timeframe': row[2],
                    'timestamp': row[3],
                    'pattern': row[4],
                    'direction': row[5],
                    'ohlcv': json.loads(row[6]) if row[6] else [],
                    'ai_verdict': row[7],
                    'ai_confidence': row[8] or 0,
                    'ai_reasoning': row[9],
                    'status': row[10]
                }
                training_data.append(data)
            
            logger.info(f"📊 {len(training_data)} amostras para treinamento")
            return training_data
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar dados: {e}")
            return []
    
    def extract_state_features(self, sample: Dict, market_context: Dict = None) -> Dict:
        """
        Extrai features do estado para o modelo
        """
        # Features básicas do padrão
        state = {
            'pattern': sample.get('pattern', 'UNKNOWN'),
            'timeframe': sample.get('timeframe', '15m'),
            'direction': sample.get('direction', 'NEUTRAL'),
            'ai_confidence': sample.get('ai_confidence', 0),
            'symbol': sample.get('symbol', 'UNKNOWN')
        }
        
        # Adicionar contexto de mercado se disponível
        if market_context:
            state.update({
                'market_scenario': market_context.get('scenario_number', 5),
                'btc_trend': market_context.get('btc_trend', 'NEUTRAL'),
                'btcd_trend': market_context.get('btcd_trend', 'NEUTRAL'),
                'btcd_source': market_context.get('btcd_source', 'unknown')
            })
        
        # Calcular features técnicas se OHLCV disponível
        ohlcv = sample.get('ohlcv', [])
        if len(ohlcv) >= 20:
            try:
                closes = [c[4] for c in ohlcv[-20:]]  # Últimos 20 closes
                
                # Médias móveis
                sma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else closes[-1]
                sma20 = sum(closes[-20:]) / 20
                
                state.update({
                    'price_trend': 'UP' if closes[-1] > sma10 else 'DOWN',
                    'volatility': (max(closes) - min(closes)) / min(closes) * 100,
                    'sma_distance': (closes[-1] - sma20) / sma20 * 100
                })
            except:
                pass
        
        return state
    
    def simulate_trade(self, sample: Dict, action: str) -> Dict:
        """
        Simula resultado do trade (para treinamento offline)
        """
        # Em produção real, isso viria do banco de dados de trades reais
        # Por enquanto, simulamos baseado na confiança da AI
        
        ai_confidence = sample.get('ai_confidence', 0.5)
        direction = sample.get('direction', 'NEUTRAL')
        
        # Baseado em dados históricos (aproximação)
        if action == 'SKIP':
            return {'profit_pct': 0, 'duration_hours': 0, 'max_drawdown': 0}
        
        # Verificar se ação combina com direção
        action_matches = (
            (action == 'ENTER_LONG' and direction == 'LONG') or
            (action == 'ENTER_SHORT' and direction == 'SHORT')
        )
        
        if not action_matches:
            # Entrar contra a direção do padrão geralmente dá prejuízo
            return {'profit_pct': -random.uniform(1, 5), 'duration_hours': random.uniform(2, 48), 'max_drawdown': random.uniform(3, 10)}
        
        # Simular resultado baseado na confiança da AI
        if ai_confidence > 0.7:
            # Alta confiança → maior chance de lucro
            profit = random.uniform(0.5, 5.0) if random.random() < 0.7 else random.uniform(-2, -0.5)
        elif ai_confidence > 0.5:
            # Média confiança → resultado misto
            profit = random.uniform(-1, 3) if random.random() < 0.6 else random.uniform(-3, -0.5)
        else:
            # Baixa confiança → maior chance de prejuízo
            profit = random.uniform(-3, 1) if random.random() < 0.4 else random.uniform(-5, -1)
        
        return {
            'profit_pct': profit,
            'duration_hours': random.uniform(1, 24),
            'max_drawdown': abs(profit * random.uniform(0.5, 2))
        }
    
    def train_offline(self, episodes=100):
        """
        Treinamento offline com dados históricos
        """
        logger.info(f"🚀 Iniciando treinamento offline ({episodes} episódios)")
        
        training_data = self.get_training_data(limit=500)
        if not training_data:
            logger.warning("❌ Nenhum dado para treinamento")
            return
        
        for episode in range(episodes):
            episode_reward = 0
            
            # Embaralhar dados
            random.shuffle(training_data)
            
            for i, sample in enumerate(training_data[:50]):  # Limitar por episódio
                # Extrair estado
                state = self.extract_state_features(sample)
                
                # Escolher ação
                action = self.brain.get_action(state)
                
                # Simular resultado
                trade_result = self.simulate_trade(sample, action)
                reward = self.brain.calculate_reward(trade_result)
                
                # Próximo estado (mesmo para simulação)
                next_state = state  # Em simulação simples
                
                # Atualizar Q-learning
                self.brain.update(state, action, reward, next_state, done=True)
                
                episode_reward += reward
            
            # Experience replay
            self.brain.experience_replay(batch_size=32)
            
            # Atualizar estatísticas
            self.brain.training_stats['episodes'] += 1
            self.brain.training_stats['last_update'] = datetime.now().isoformat()
            
            # Salvar periodicamente
            if episode % 10 == 0:
                self.brain.save_model()
                logger.info(f"📈 Episódio {episode}: Recompensa = {episode_reward:.2f}")
        
        # Salvar modelo final
        self.brain.save_model()
        stats = self.brain.get_stats()
        logger.info(f"✅ Treinamento completo: {stats}")
    
    def predict(self, state: Dict) -> Tuple[str, float]:
        """
        Predição em tempo real
        Retorna: (ação, confiança)
        """
        action = self.brain.get_action(state)
        
        # Calcular confiança baseada nos Q-values
        state_key = self.brain._state_to_key(state)
        if state_key in self.brain.q_table:
            q_values = self.brain.q_table[state_key]
            max_q = max(q_values.values())
            min_q = min(q_values.values())
            
            if max_q == min_q:
                confidence = 0.5
            else:
                # Normalizar para 0-1
                confidence = (q_values[action] - min_q) / (max_q - min_q)
        else:
            confidence = 0.5  # Estado novo
        
        return action, confidence
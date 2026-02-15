#!/usr/bin/env python3
"""
SEVERINO: Sistema de Aprendizado Contínuo
Treina modelo incrementalmente preservando conhecimento anterior
"""

import sqlite3
import numpy as np
import json
import time
import logging
import threading
import pickle
import os
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger("BrainContinuousLearning")

class ContinuousLearningEngine:
    def __init__(self, db_path='sniper_brain.db', models_dir='brain_models/'):
        self.db_path = db_path
        self.models_dir = models_dir
        self.is_training = False
        self.training_thread = None
        
        # Parâmetros de treinamento
        self.batch_size = 50  # Treina a cada 50 novas amostras
        self.min_pattern_samples = 10  # Mínimo de amostras por padrão para treinar
        
        # Cria diretório de modelos
        os.makedirs(models_dir, exist_ok=True)
        
        # Estado atual do modelo
        self.current_model_version = self._get_latest_model_version()
        self.pattern_weights = self._load_pattern_weights()
        
    def _get_latest_model_version(self):
        """Retorna a versão mais recente do modelo"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute('SELECT model_version FROM training_states ORDER BY id DESC LIMIT 1')
            result = c.fetchone()
            conn.close()
            
            return result[0] if result else "v1.0.0"
        except:
            return "v1.0.0"
    
    def _load_pattern_weights(self):
        """Carrega pesos atuais dos padrões"""
        try:
            weights_file = os.path.join(self.models_dir, f'pattern_weights_{self.current_model_version}.pkl')
            if os.path.exists(weights_file):
                with open(weights_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível carregar pesos existentes: {e}")
        
        # Pesos padrão se não existir modelo anterior
        return {
            'OCO': {'confidence_base': 0.8, 'success_weight': 1.0},
            'TOPO_DUPLO': {'confidence_base': 0.75, 'success_weight': 1.0},
            'FUNDO_DUPLO': {'confidence_base': 0.75, 'success_weight': 1.0},
            'BANDEIRA_ALTA': {'confidence_base': 0.7, 'success_weight': 1.0},
            'BANDEIRA_BAIXA': {'confidence_base': 0.7, 'success_weight': 1.0},
            'TRIANGULO_ASCENDENTE': {'confidence_base': 0.72, 'success_weight': 1.0},
            'TRIANGULO_DESCENDENTE': {'confidence_base': 0.72, 'success_weight': 1.0},
            'CUNHA_ASCENDENTE': {'confidence_base': 0.68, 'success_weight': 1.0},
            'CUNHA_DESCENDENTE': {'confidence_base': 0.68, 'success_weight': 1.0},
        }
    
    def check_training_trigger(self):
        """Verifica se deve iniciar novo ciclo de treinamento"""
        if self.is_training:
            return False
            
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Conta amostras não processadas para treinamento
            c.execute('''
                SELECT COUNT(*) FROM raw_samples 
                WHERE status = 'PROCESSED' 
                AND id NOT IN (SELECT DISTINCT brain_sample_id FROM trade_performance WHERE brain_sample_id IS NOT NULL)
            ''')
            
            untrained_samples = c.fetchone()[0]
            
            # Conta feedbacks de performance disponíveis para aprendizado
            c.execute('SELECT COUNT(*) FROM trade_performance WHERE created_at > ?', 
                     (time.time() - 86400,))  # Últimas 24h
            
            recent_feedbacks = c.fetchone()[0]
            
            conn.close()
            
            # Critérios para iniciar treinamento
            should_train = (
                untrained_samples >= self.batch_size or 
                recent_feedbacks >= 20
            )
            
            if should_train:
                logger.info(f"🧠 Trigger de treinamento: {untrained_samples} amostras + {recent_feedbacks} feedbacks")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar trigger de treinamento: {e}")
            return False
    
    def start_incremental_training(self):
        """Inicia treinamento incremental em thread separada"""
        if self.is_training:
            logger.warning("⚠️ Treinamento já está em progresso")
            return False
        
        self.training_thread = threading.Thread(target=self._incremental_training_worker)
        self.training_thread.daemon = True
        self.training_thread.start()
        
        return True
    
    def _incremental_training_worker(self):
        """Worker que executa treinamento incremental"""
        self.is_training = True
        start_time = time.time()
        
        try:
            logger.info("🚀 Iniciando treinamento incremental...")
            
            # 1. Coleta dados de performance
            performance_data = self._collect_performance_data()
            
            # 2. Atualiza pesos dos padrões baseado em feedback real
            updated_weights = self._update_pattern_weights_from_performance(performance_data)
            
            # 3. Treina modelo de confiança adaptiva
            confidence_model = self._train_adaptive_confidence_model(performance_data)
            
            # 4. Valida melhorias
            validation_score = self._validate_model_improvements(updated_weights, confidence_model)
            
            # 5. Salva novo modelo se houver melhoria
            if validation_score > 0.05:  # Melhoria mínima de 5%
                new_version = self._increment_model_version()
                self._save_trained_model(new_version, updated_weights, confidence_model, validation_score)
                
                # Atualiza estado ativo
                self.pattern_weights = updated_weights
                self.current_model_version = new_version
                
                logger.info(f"✅ Modelo {new_version} treinado com sucesso! Melhoria: {validation_score:.1%}")
            else:
                logger.info(f"📊 Treinamento concluído sem melhoria significativa ({validation_score:.1%})")
            
            # 6. Compacta dados antigos
            self._compact_old_training_data()
            
            elapsed = time.time() - start_time
            logger.info(f"⏱️ Treinamento concluído em {elapsed:.1f}s")
            
        except Exception as e:
            logger.error(f"❌ Erro durante treinamento incremental: {e}")
        finally:
            self.is_training = False
    
    def _collect_performance_data(self):
        """Coleta dados de performance para treinamento"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Busca dados de performance com features
            c.execute('''
                SELECT 
                    tp.pattern_detected,
                    tp.ai_confidence,
                    tp.success_binary,
                    tp.actual_pnl,
                    tp.performance_score,
                    tp.trade_duration_hours,
                    rs.ai_confidence as technical_confidence
                FROM trade_performance tp
                LEFT JOIN raw_samples rs ON tp.brain_sample_id = rs.id
                WHERE tp.created_at > ?
                ORDER BY tp.created_at DESC
            ''', (time.time() - (30 * 86400),))  # Últimos 30 dias
            
            data = c.fetchall()
            conn.close()
            
            # Organiza dados por padrão
            performance_by_pattern = defaultdict(list)
            for row in data:
                pattern = row[0]
                performance_by_pattern[pattern].append({
                    'ai_confidence': row[1] or 0,
                    'success': row[2],
                    'pnl': row[3] or 0,
                    'performance_score': row[4] or 0,
                    'duration': row[5] or 0,
                    'technical_confidence': row[6] or 0
                })
            
            logger.info(f"📊 Coletados dados de {len(data)} trades para {len(performance_by_pattern)} padrões")
            return performance_by_pattern
            
        except Exception as e:
            logger.error(f"❌ Erro ao coletar dados de performance: {e}")
            return {}
    
    def _update_pattern_weights_from_performance(self, performance_data):
        """Atualiza pesos dos padrões baseado em performance real"""
        updated_weights = self.pattern_weights.copy()
        
        for pattern, samples in performance_data.items():
            if len(samples) < self.min_pattern_samples:
                continue
                
            # Calcula métricas do padrão
            success_rate = np.mean([s['success'] for s in samples])
            avg_pnl = np.mean([s['pnl'] for s in samples])
            avg_score = np.mean([s['performance_score'] for s in samples])
            
            # Calcula novo peso baseado em performance
            # Fórmula: peso = baseline * (success_rate * 0.6 + normalized_pnl * 0.4)
            baseline_weight = updated_weights.get(pattern, {}).get('success_weight', 1.0)
            
            # Normaliza PnL para escala 0-2
            normalized_pnl = max(0, min(2.0, 1.0 + avg_pnl / 5.0))
            
            new_weight = baseline_weight * 0.3 + (success_rate * 0.4 + normalized_pnl * 0.3) * 0.7
            new_weight = max(0.2, min(2.0, new_weight))  # Limita entre 0.2x e 2.0x
            
            # Ajusta confiança base
            confidence_adjustment = 0.5 + (avg_score * 0.5)  # Entre 0.5 e 1.0
            new_confidence = updated_weights.get(pattern, {}).get('confidence_base', 0.7)
            new_confidence = new_confidence * 0.7 + confidence_adjustment * 0.3
            new_confidence = max(0.3, min(0.95, new_confidence))
            
            # Atualiza pesos
            if pattern not in updated_weights:
                updated_weights[pattern] = {}
            
            updated_weights[pattern].update({
                'confidence_base': new_confidence,
                'success_weight': new_weight,
                'samples_count': len(samples),
                'success_rate': success_rate,
                'avg_pnl': avg_pnl,
                'last_updated': time.time()
            })
            
            logger.info(f"📊 {pattern}: Peso {baseline_weight:.2f}→{new_weight:.2f}, "
                       f"Conf {new_confidence:.2f} (SR: {success_rate:.1%})")
        
        return updated_weights
    
    def _train_adaptive_confidence_model(self, performance_data):
        """Treina modelo simples de confiança adaptiva"""
        try:
            # Modelo simples baseado em regressão linear dos fatores
            confidence_model = {}
            
            for pattern, samples in performance_data.items():
                if len(samples) < self.min_pattern_samples:
                    continue
                
                # Features: AI conf, technical conf, duration
                X = np.array([[s['ai_confidence'], s['technical_confidence'], 
                             min(24, s['duration'])] for s in samples])
                y = np.array([s['performance_score'] for s in samples])
                
                if len(X) > 5:  # Mínimo para regressão
                    # Regressão linear simples (sem bibliotecas externas)
                    # y = a*ai_conf + b*tech_conf + c*duration + d
                    X_with_bias = np.column_stack([X, np.ones(len(X))])
                    
                    try:
                        coefficients = np.linalg.lstsq(X_with_bias, y, rcond=None)[0]
                        confidence_model[pattern] = {
                            'ai_coeff': coefficients[0],
                            'tech_coeff': coefficients[1], 
                            'duration_coeff': coefficients[2],
                            'bias': coefficients[3],
                            'samples': len(samples)
                        }
                    except:
                        # Fallback para média simples se falhar
                        confidence_model[pattern] = {
                            'ai_coeff': 0.6,
                            'tech_coeff': 0.3,
                            'duration_coeff': 0.1,
                            'bias': 0.1,
                            'samples': len(samples)
                        }
            
            logger.info(f"🤖 Modelo de confiança treinado para {len(confidence_model)} padrões")
            return confidence_model
            
        except Exception as e:
            logger.error(f"❌ Erro ao treinar modelo de confiança: {e}")
            return {}
    
    def _validate_model_improvements(self, new_weights, new_confidence_model):
        """Valida se o novo modelo tem performance melhor"""
        try:
            # Simulação de performance com pesos antigos vs novos
            # (Implementação simplificada - em produção seria mais robusta)
            
            old_score = sum([w.get('success_weight', 1.0) * w.get('success_rate', 0.5) 
                           for w in self.pattern_weights.values()])
            
            new_score = sum([w.get('success_weight', 1.0) * w.get('success_rate', 0.5) 
                           for w in new_weights.values()])
            
            if old_score > 0:
                improvement = (new_score - old_score) / old_score
            else:
                improvement = 0.1  # Default para primeiro modelo
            
            return improvement
            
        except Exception as e:
            logger.error(f"❌ Erro ao validar melhorias: {e}")
            return 0.0
    
    def _increment_model_version(self):
        """Incrementa versão do modelo"""
        current = self.current_model_version.replace('v', '').split('.')
        major, minor, patch = map(int, current)
        
        # Incrementa patch para melhorias menores
        patch += 1
        if patch >= 10:  # Depois de 10 patches, incrementa minor
            patch = 0
            minor += 1
        
        return f"v{major}.{minor}.{patch}"
    
    def _save_trained_model(self, version, weights, confidence_model, improvement):
        """Salva modelo treinado"""
        try:
            # Salva pesos dos padrões
            weights_file = os.path.join(self.models_dir, f'pattern_weights_{version}.pkl')
            with open(weights_file, 'wb') as f:
                pickle.dump(weights, f)
            
            # Salva modelo de confiança
            confidence_file = os.path.join(self.models_dir, f'confidence_model_{version}.pkl')
            with open(confidence_file, 'wb') as f:
                pickle.dump(confidence_model, f)
            
            # Registra no banco
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''
                INSERT INTO training_states
                (model_version, training_data_count, validation_accuracy, 
                 training_completed_at, model_path, performance_improvement, status)
                VALUES (?, ?, ?, ?, ?, ?, 'ACTIVE')
            ''', (version, sum([w.get('samples_count', 0) for w in weights.values()]),
                  improvement, int(time.time()), weights_file, improvement))
            
            # Marca versão anterior como inativa
            c.execute("UPDATE training_states SET status = 'INACTIVE' WHERE model_version != ?", (version,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"💾 Modelo {version} salvo com sucesso")
            
        except Exception as e:
            logger.error(f"❌ Erro ao salvar modelo: {e}")
    
    def _compact_old_training_data(self):
        """Move dados antigos de treinamento para arquivo compactado"""
        try:
            # Move dados de performance > 90 dias para tabela de arquivo
            cutoff_time = time.time() - (90 * 86400)
            
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Cria tabela de arquivo se não existir
            c.execute('''
                CREATE TABLE IF NOT EXISTS trade_performance_archive AS 
                SELECT * FROM trade_performance WHERE 1=0
            ''')
            
            # Move dados antigos
            c.execute('''
                INSERT INTO trade_performance_archive 
                SELECT * FROM trade_performance WHERE created_at < ?
            ''', (cutoff_time,))
            
            archived_count = c.rowcount
            
            # Remove da tabela principal
            c.execute('DELETE FROM trade_performance WHERE created_at < ?', (cutoff_time,))
            
            conn.commit()
            conn.close()
            
            if archived_count > 0:
                logger.info(f"🗄️ Arquivados {archived_count} registros de performance antigos")
                
        except Exception as e:
            logger.error(f"❌ Erro ao compactar dados antigos: {e}")
    
    def get_enhanced_confidence(self, pattern, ai_confidence, technical_confidence, market_conditions=None):
        """Retorna confiança melhorada baseada no modelo treinado"""
        try:
            # Aplica pesos do padrão
            pattern_weight = self.pattern_weights.get(pattern, {}).get('success_weight', 1.0)
            base_confidence = self.pattern_weights.get(pattern, {}).get('confidence_base', ai_confidence)
            
            # Combina confiâncias
            enhanced_confidence = (
                base_confidence * 0.4 + 
                ai_confidence * 0.3 + 
                technical_confidence * 0.3
            ) * pattern_weight
            
            # Aplica limites
            enhanced_confidence = max(0.1, min(0.95, enhanced_confidence))
            
            return enhanced_confidence
            
        except Exception as e:
            logger.error(f"❌ Erro ao calcular confiança melhorada: {e}")
            return ai_confidence
    
    def get_training_status(self):
        """Retorna status atual do sistema de treinamento"""
        return {
            'is_training': self.is_training,
            'current_model_version': self.current_model_version,
            'patterns_count': len(self.pattern_weights),
            'models_dir': self.models_dir,
            'batch_size': self.batch_size
        }

# Singleton para uso global
continuous_learning = ContinuousLearningEngine()
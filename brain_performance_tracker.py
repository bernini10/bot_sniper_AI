#!/usr/bin/env python3
"""
SEVERINO: Sistema Completo de Feedback Learning
Conecta predições da IA com resultados reais de P&L
"""

import sqlite3
import json
import time
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("BrainPerformanceTracker")

class BrainPerformanceTracker:
    def __init__(self, db_path='sniper_brain.db'):
        self.db_path = db_path
        self._init_performance_tables()
    
    def _init_performance_tables(self):
        """Cria tabelas de performance se não existirem"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Tabela de Performance (conecta predições com resultados)
            c.execute('''
                CREATE TABLE IF NOT EXISTS trade_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    brain_sample_id INTEGER,
                    symbol TEXT NOT NULL,
                    pattern_detected TEXT,
                    ai_prediction TEXT,
                    ai_confidence REAL,
                    actual_pnl REAL,
                    actual_direction TEXT,
                    success_binary INTEGER,
                    performance_score REAL,
                    trade_duration_hours REAL,
                    opened_at INTEGER,
                    closed_at INTEGER,
                    created_at INTEGER DEFAULT (strftime('%s', 'now')),
                    FOREIGN KEY (brain_sample_id) REFERENCES raw_samples(id)
                )
            ''')
            
            # Tabela de Métricas Agregadas por Padrão
            c.execute('''
                CREATE TABLE IF NOT EXISTS pattern_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_name TEXT UNIQUE,
                    total_trades INTEGER DEFAULT 0,
                    successful_trades INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.0,
                    avg_pnl REAL DEFAULT 0.0,
                    avg_duration_hours REAL DEFAULT 0.0,
                    confidence_adjustment REAL DEFAULT 1.0,
                    last_updated INTEGER DEFAULT (strftime('%s', 'now'))
                )
            ''')
            
            # Tabela de Estados de Treinamento
            c.execute('''
                CREATE TABLE IF NOT EXISTS training_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_version TEXT,
                    training_data_count INTEGER,
                    validation_accuracy REAL,
                    training_completed_at INTEGER,
                    model_path TEXT,
                    performance_improvement REAL,
                    status TEXT DEFAULT 'ACTIVE'
                )
            ''')
            
            # Índices para performance
            c.execute('CREATE INDEX IF NOT EXISTS idx_performance_symbol ON trade_performance(symbol)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_performance_pattern ON trade_performance(pattern_detected)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_performance_created ON trade_performance(created_at)')
            
            conn.commit()
            conn.close()
            logger.info("✅ Tabelas de performance inicializadas")
            
        except Exception as e:
            logger.error(f"❌ Erro ao inicializar tabelas: {e}")
    
    def match_prediction_with_result(self, closed_trade_data):
        """
        Conecta um trade fechado com a predição original da IA
        closed_trade_data: dados do trade fechado (symbol, pnl, opened_at, closed_at, etc)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            symbol = closed_trade_data.get('symbol', '').replace('USDT', '/USDT')
            opened_at = closed_trade_data.get('opened_at', 0) // 1000  # Bybit usa milissegundos
            closed_at = closed_trade_data.get('closed_at', 0) // 1000
            actual_pnl = float(closed_trade_data.get('pnl', 0))
            
            # Busca predições da IA próximas ao horário de abertura (±2h)
            time_window = 2 * 60 * 60  # 2 horas em segundos
            
            c.execute('''
                SELECT id, pattern_detected, direction, ai_confidence, timestamp_detection
                FROM raw_samples 
                WHERE symbol = ? 
                AND timestamp_detection BETWEEN ? AND ?
                AND status = 'PROCESSED'
                ORDER BY ABS(timestamp_detection - ?) ASC
                LIMIT 1
            ''', (symbol, opened_at - time_window, opened_at + time_window, opened_at))
            
            prediction = c.fetchone()
            
            if prediction:
                brain_sample_id, pattern, ai_direction, ai_conf, pred_time = prediction
                
                # Calcula métricas de performance
                actual_direction = "PROFIT" if actual_pnl > 0 else "LOSS"
                success_binary = 1 if actual_pnl > 0 else 0
                
                # Score de performance (0-1) baseado em P&L e direção
                if ai_direction == "LONG" and actual_pnl > 0:
                    performance_score = min(1.0, (actual_pnl / 10.0) + 0.5)  # Normaliza P&L
                elif ai_direction == "SHORT" and actual_pnl > 0:
                    performance_score = min(1.0, (actual_pnl / 10.0) + 0.5)
                else:
                    performance_score = max(0.0, 0.5 - abs(actual_pnl / 10.0))
                
                trade_duration = (closed_at - opened_at) / 3600.0  # horas
                
                # Salva feedback de performance
                c.execute('''
                    INSERT INTO trade_performance 
                    (brain_sample_id, symbol, pattern_detected, ai_prediction, ai_confidence,
                     actual_pnl, actual_direction, success_binary, performance_score,
                     trade_duration_hours, opened_at, closed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (brain_sample_id, symbol, pattern, ai_direction, ai_conf,
                      actual_pnl, actual_direction, success_binary, performance_score,
                      trade_duration, opened_at, closed_at))
                
                # Atualiza métricas agregadas do padrão
                self._update_pattern_metrics(c, pattern)
                
                conn.commit()
                logger.info(f"🎯 Feedback registrado: {symbol} {pattern} → P&L: {actual_pnl:.3f} (Score: {performance_score:.2f})")
                return True
            else:
                logger.warning(f"⚠️ Nenhuma predição encontrada para {symbol} em {datetime.fromtimestamp(opened_at)}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Erro ao processar feedback: {e}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def _update_pattern_metrics(self, cursor, pattern_name):
        """Atualiza métricas agregadas de um padrão específico"""
        try:
            # Calcula estatísticas do padrão
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(success_binary) as successes,
                    AVG(actual_pnl) as avg_pnl,
                    AVG(trade_duration_hours) as avg_duration,
                    AVG(performance_score) as avg_score
                FROM trade_performance 
                WHERE pattern_detected = ?
            ''', (pattern_name,))
            
            stats = cursor.fetchone()
            total, successes, avg_pnl, avg_duration, avg_score = stats
            
            if total > 0:
                success_rate = successes / total
                
                # Ajuste de confiança baseado em performance
                # Se success_rate > 60%, aumenta confiança; se < 40%, diminui
                if success_rate > 0.6:
                    confidence_adj = 1.0 + (success_rate - 0.6) * 0.5
                elif success_rate < 0.4:
                    confidence_adj = 1.0 - (0.4 - success_rate) * 0.5
                else:
                    confidence_adj = 1.0
                
                confidence_adj = max(0.3, min(1.5, confidence_adj))  # Limita entre 0.3x e 1.5x
                
                # Insere ou atualiza métricas
                cursor.execute('''
                    INSERT OR REPLACE INTO pattern_metrics 
                    (pattern_name, total_trades, successful_trades, success_rate, 
                     avg_pnl, avg_duration_hours, confidence_adjustment, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (pattern_name, total, successes, success_rate, avg_pnl or 0, 
                      avg_duration or 0, confidence_adj, int(time.time())))
                
                logger.info(f"📊 Métricas atualizadas: {pattern_name} - Taxa: {success_rate:.1%}, Ajuste: {confidence_adj:.2f}x")
                
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar métricas do padrão {pattern_name}: {e}")
    
    def get_pattern_confidence_multiplier(self, pattern_name):
        """Retorna o multiplicador de confiança baseado em performance histórica"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('SELECT confidence_adjustment FROM pattern_metrics WHERE pattern_name = ?', 
                     (pattern_name,))
            result = c.fetchone()
            
            conn.close()
            
            if result:
                return result[0]
            else:
                return 1.0  # Neutro se não há dados históricos
                
        except Exception as e:
            logger.error(f"❌ Erro ao buscar multiplicador de confiança: {e}")
            return 1.0
    
    def get_performance_summary(self):
        """Retorna resumo geral de performance do sistema"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Estatísticas gerais
            c.execute('''
                SELECT 
                    COUNT(*) as total_feedback,
                    SUM(success_binary) as total_successes,
                    AVG(actual_pnl) as avg_pnl,
                    SUM(actual_pnl) as total_pnl,
                    AVG(performance_score) as avg_score
                FROM trade_performance
            ''')
            
            general_stats = c.fetchone()
            
            # Top padrões por performance
            c.execute('''
                SELECT pattern_name, success_rate, total_trades, avg_pnl, confidence_adjustment
                FROM pattern_metrics
                ORDER BY success_rate DESC
                LIMIT 10
            ''')
            
            top_patterns = c.fetchall()
            
            conn.close()
            
            return {
                'general': {
                    'total_feedback': general_stats[0] or 0,
                    'success_rate': (general_stats[1] or 0) / max(1, general_stats[0] or 1),
                    'avg_pnl': general_stats[2] or 0,
                    'total_pnl': general_stats[3] or 0,
                    'avg_performance_score': general_stats[4] or 0
                },
                'top_patterns': [
                    {
                        'pattern': row[0],
                        'success_rate': row[1],
                        'total_trades': row[2],
                        'avg_pnl': row[3],
                        'confidence_adjustment': row[4]
                    } for row in top_patterns
                ]
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar resumo de performance: {e}")
            return None
    
    def process_closed_trades_batch(self, closed_trades_file='closed_pnl_cache.json'):
        """Processa lote de trades fechados para gerar feedback"""
        try:
            with open(closed_trades_file, 'r') as f:
                data = json.load(f)
            
            processed = 0
            for trade in data.get('trades', []):
                if self.match_prediction_with_result(trade):
                    processed += 1
            
            logger.info(f"✅ Processados {processed} feedbacks de performance")
            return processed
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar lote de trades fechados: {e}")
            return 0

# Singleton para uso global
performance_tracker = BrainPerformanceTracker()
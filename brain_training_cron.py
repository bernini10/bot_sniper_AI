#!/usr/bin/env python3
"""
SEVERINO: Sistema de Cron Job para Treinamento Automático da IA
Executa treinamento a cada 50 feedbacks coletados
Sistema independente que não interfere com funcionamento existente
"""

import time
import logging
import sqlite3
import os
import sys
from datetime import datetime

# Configuração de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - BRAIN_CRON - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("brain_training_cron.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BrainTrainingCron")

# Importar sistemas necessários
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from brain_performance_tracker import BrainPerformanceTracker
    from brain_continuous_learning import continuous_learning
    from brain_maintenance import BrainMaintenance
except ImportError as e:
    logger.error(f"❌ Erro ao importar módulos: {e}")
    sys.exit(1)

class BrainTrainingCron:
    def __init__(self):
        self.db_path = 'sniper_brain.db'
        self.tracker = BrainPerformanceTracker()
        self.maintenance = BrainMaintenance()
        
        # Configurações
        self.feedback_threshold = 50  # Treinar a cada 50 feedbacks
        self.check_interval = 43200   # Verificar a cada 12 horas (43200 segundos)
        self.min_training_interval = 86400  # Mínimo 24h entre treinamentos
        
        # Estado
        self.last_training_time = 0
        self.last_check_time = 0
        
    def get_feedback_stats(self):
        """Retorna estatísticas de feedbacks disponíveis"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # Total de feedbacks
            c.execute('SELECT COUNT(*) FROM trade_performance')
            total_feedbacks = c.fetchone()[0]
            
            # Feedbacks não usados para treinamento
            c.execute('''
                SELECT COUNT(*) 
                FROM trade_performance tp
                LEFT JOIN raw_samples rs ON tp.brain_sample_id = rs.id
                WHERE rs.training_used = 0 OR rs.training_used IS NULL
            ''')
            untrained_feedbacks = c.fetchone()[0]
            
            # Feedbacks das últimas 24h
            c.execute('SELECT COUNT(*) FROM trade_performance WHERE created_at > ?', 
                     (time.time() - 86400,))
            recent_feedbacks = c.fetchone()[0]
            
            conn.close()
            
            return {
                'total_feedbacks': total_feedbacks,
                'untrained_feedbacks': untrained_feedbacks,
                'recent_feedbacks': recent_feedbacks
            }
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter estatísticas de feedback: {e}")
            return None
    
    def should_run_training(self):
        """Verifica se deve executar treinamento"""
        stats = self.get_feedback_stats()
        if not stats:
            return False
        
        current_time = time.time()
        
        # Critérios para treinamento
        criteria_met = []
        
        # 1. Feedbacks não treinados >= threshold
        if stats['untrained_feedbacks'] >= self.feedback_threshold:
            criteria_met.append(f"Feedbacks não treinados: {stats['untrained_feedbacks']}/{self.feedback_threshold}")
        
        # 2. Mínimo intervalo entre treinamentos
        time_since_last_training = current_time - self.last_training_time
        if time_since_last_training < self.min_training_interval:
            logger.info(f"⏳ Aguardando intervalo mínimo: {int((self.min_training_interval - time_since_last_training)/3600)}h restantes")
            return False
        
        # 3. Sistema não está em treinamento
        if continuous_learning.is_training:
            logger.info("⏳ Sistema já está em treinamento")
            return False
        
        if criteria_met:
            logger.info(f"🎯 Critérios para treinamento atendidos:")
            for criterion in criteria_met:
                logger.info(f"   ✅ {criterion}")
            return True
        
        return False
    
    def process_pending_feedbacks(self):
        """Processa trades fechados pendentes"""
        try:
            logger.info("🔄 Processando trades fechados pendentes...")
            
            feedbacks_processed = self.tracker.process_closed_trades_from_cache()
            
            if feedbacks_processed > 0:
                logger.info(f"✅ Processados {feedbacks_processed} novos feedbacks")
            else:
                logger.info("📭 Nenhum novo feedback para processar")
            
            return feedbacks_processed
            
        except Exception as e:
            logger.error(f"❌ Erro ao processar feedbacks pendentes: {e}")
            return 0
    
    def run_maintenance(self):
        """Executa manutenção do banco de dados"""
        try:
            logger.info("🔧 Executando manutenção do banco de dados...")
            self.maintenance.run_maintenance()
            return True
        except Exception as e:
            logger.error(f"❌ Erro na manutenção: {e}")
            return False
    
    def run_training_cycle(self):
        """Executa ciclo completo de treinamento"""
        try:
            logger.info("🚀 INICIANDO CICLO DE TREINAMENTO AUTOMÁTICO")
            logger.info("=" * 60)
            
            # 1. Processar feedbacks pendentes
            new_feedbacks = self.process_pending_feedbacks()
            
            # 2. Verificar se deve treinar
            if not self.should_run_training():
                logger.info("⏳ Critérios não atendidos para treinamento")
                return False
            
            # 3. Executar manutenção antes do treinamento
            self.run_maintenance()
            
            # 4. Iniciar treinamento
            logger.info("🧠 Iniciando treinamento incremental da IA...")
            
            success = continuous_learning.start_incremental_training()
            
            if success:
                self.last_training_time = time.time()
                
                # Aguardar conclusão (máximo 5 minutos)
                max_wait = 300  # 5 minutos
                start_wait = time.time()
                
                while continuous_learning.is_training:
                    elapsed = time.time() - start_wait
                    if elapsed > max_wait:
                        logger.warning("⚠️ Tempo máximo de treinamento excedido")
                        break
                    
                    logger.info(f"⏳ Treinamento em progresso... ({int(elapsed)}s)")
                    time.sleep(10)
                
                if not continuous_learning.is_training:
                    logger.info("✅ Treinamento concluído com sucesso!")
                    
                    # Verificar nova versão do modelo
                    status = continuous_learning.get_training_status()
                    logger.info(f"🏷️ Nova versão do modelo: {status['current_model_version']}")
                    
                    return True
                else:
                    logger.error("❌ Treinamento não concluído dentro do tempo limite")
                    return False
            else:
                logger.error("❌ Não foi possível iniciar treinamento")
                return False
            
        except Exception as e:
            logger.error(f"❌ Erro no ciclo de treinamento: {e}")
            return False
    
    def run_continuous(self):
        """Executa em loop contínuo (para uso com systemd/cron)"""
        logger.info("🤖 BRAIN TRAINING CRON INICIADO")
        logger.info(f"📊 Configuração: Treinar a cada {self.feedback_threshold} feedbacks")
        logger.info(f"⏰ Verificar a cada {self.check_interval/3600:.1f} horas")
        logger.info(f"⏳ Intervalo mínimo entre treinamentos: {self.min_training_interval/3600:.1f} horas")
        
        while True:
            try:
                current_time = time.time()
                
                # Verificar se é hora de checar
                if current_time - self.last_check_time >= self.check_interval:
                    logger.info("🔍 Verificando condições para treinamento...")
                    
                    # Obter estatísticas atuais
                    stats = self.get_feedback_stats()
                    if stats:
                        logger.info(f"📊 Estatísticas: {stats['total_feedbacks']} feedbacks total, "
                                   f"{stats['untrained_feedbacks']} não treinados, "
                                   f"{stats['recent_feedbacks']} recentes (24h)")
                    
                    # Executar ciclo se necessário
                    self.run_training_cycle()
                    
                    self.last_check_time = current_time
                
                # Aguardar próximo ciclo
                sleep_time = max(60, self.check_interval - (time.time() - self.last_check_time))
                logger.info(f"💤 Próxima verificação em {sleep_time/60:.1f} minutos")
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("👋 Interrompido pelo usuário")
                break
            except Exception as e:
                logger.error(f"❌ Erro no loop principal: {e}")
                time.sleep(300)  # Esperar 5 minutos em caso de erro

def run_once():
    """Executa uma única verificação (para cron job)"""
    cron = BrainTrainingCron()
    
    # Processar feedbacks pendentes
    cron.process_pending_feedbacks()
    
    # Executar ciclo se necessário
    if cron.should_run_training():
        cron.run_training_cycle()
    else:
        logger.info("⏳ Condições não atendidas para treinamento")
    
    # Executar manutenção
    cron.run_maintenance()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Brain Training Cron Job')
    parser.add_argument('--mode', choices=['continuous', 'once'], default='once',
                       help='Modo de execução: continuous (loop) ou once (uma vez)')
    
    args = parser.parse_args()
    
    cron = BrainTrainingCron()
    
    if args.mode == 'continuous':
        cron.run_continuous()
    else:
        run_once()
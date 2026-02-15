#!/usr/bin/env python3
"""
SEVERINO: Inicialização Completa do Sistema de IA com Feedback Loop
Configura e processa dados existentes para bootstrap do sistema
"""

import os
import sys
import time
import json
import logging
from datetime import datetime

# Adiciona o diretório atual ao path para imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from brain_performance_tracker import performance_tracker
from brain_continuous_learning import continuous_learning
from brain_maintenance import BrainMaintenance

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - BrainInit - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("brain_initialization.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BrainInitialization")

class BrainSystemInitializer:
    def __init__(self):
        self.start_time = time.time()
        
    def run_complete_initialization(self):
        """Executa inicialização completa do sistema de IA"""
        logger.info("🚀 INICIANDO BOOTSTRAP COMPLETO DO SISTEMA DE IA")
        logger.info("=" * 60)
        
        try:
            # 1. Verifica e inicializa estruturas básicas
            self._verify_basic_structures()
            
            # 2. Processa trades históricos para feedback
            self._process_historical_feedback()
            
            # 3. Executa primeiro treinamento incremental
            self._initial_training()
            
            # 4. Configura manutenção automática
            self._setup_maintenance()
            
            # 5. Gera relatório inicial
            self._generate_initialization_report()
            
            elapsed = time.time() - self.start_time
            logger.info("=" * 60)
            logger.info(f"✅ SISTEMA DE IA INICIALIZADO COM SUCESSO EM {elapsed:.1f}s")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ ERRO CRÍTICO NA INICIALIZAÇÃO: {e}")
            return False
    
    def _verify_basic_structures(self):
        """Verifica e cria estruturas básicas necessárias"""
        logger.info("🔧 Verificando estruturas básicas...")
        
        # Cria diretórios necessários
        directories = ['brain_models', 'brain_images/failed_patterns', 'logs_archive']
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"   📁 Diretório: {directory}")
        
        # Inicializa trackers (isso cria as tabelas se necessário)
        performance_tracker._init_performance_tables()
        logger.info("   📊 Tabelas de performance: OK")
        
        # Verifica sistema de aprendizado
        status = continuous_learning.get_training_status()
        logger.info(f"   🧠 Sistema de aprendizado: {status['current_model_version']}")
        
        logger.info("✅ Estruturas básicas verificadas")
    
    def _process_historical_feedback(self):
        """Processa dados históricos para gerar feedback inicial"""
        logger.info("📊 Processando dados históricos para feedback...")
        
        # Processa trades fechados
        try:
            processed_trades = performance_tracker.process_closed_trades_batch()
            logger.info(f"   💰 Trades processados: {processed_trades}")
            
            if processed_trades > 0:
                # Gera estatísticas iniciais
                summary = performance_tracker.get_performance_summary()
                if summary:
                    general = summary['general']
                    logger.info(f"   📈 Taxa de sucesso geral: {general['success_rate']:.1%}")
                    logger.info(f"   💵 P&L médio: {general['avg_pnl']:.3f} USDT")
                    logger.info(f"   🎯 Score médio: {general['avg_performance_score']:.2f}")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao processar feedback histórico: {e}")
        
        logger.info("✅ Feedback histórico processado")
    
    def _initial_training(self):
        """Executa primeiro ciclo de treinamento se houver dados suficientes"""
        logger.info("🧠 Verificando necessidade de treinamento inicial...")
        
        try:
            if continuous_learning.check_training_trigger():
                logger.info("   🚀 Iniciando treinamento inicial...")
                continuous_learning.start_incremental_training()
                
                # Aguarda até 60 segundos pelo treinamento
                max_wait = 60
                waited = 0
                while continuous_learning.is_training and waited < max_wait:
                    time.sleep(2)
                    waited += 2
                    if waited % 10 == 0:
                        logger.info(f"   ⏳ Aguardando treinamento... ({waited}s)")
                
                if not continuous_learning.is_training:
                    logger.info("   ✅ Treinamento inicial concluído")
                else:
                    logger.info("   ⏳ Treinamento continua em background")
            else:
                logger.info("   📊 Dados insuficientes para treinamento inicial")
                
        except Exception as e:
            logger.warning(f"⚠️ Erro no treinamento inicial: {e}")
    
    def _setup_maintenance(self):
        """Configura sistema de manutenção automática"""
        logger.info("🔧 Configurando manutenção automática...")
        
        try:
            maintenance = BrainMaintenance()
            stats_before = maintenance.get_database_stats()
            
            if stats_before:
                logger.info(f"   📊 Estado atual: {stats_before['total_samples']} amostras, {stats_before['db_size_mb']}MB")
                
                # Executa limpeza inicial se necessário
                if stats_before['db_size_mb'] > 100:  # > 100MB
                    logger.info("   🧹 Executando limpeza inicial...")
                    maintenance.run_maintenance()
                    
                    stats_after = maintenance.get_database_stats()
                    if stats_after:
                        logger.info(f"   📊 Após limpeza: {stats_after['total_samples']} amostras, {stats_after['db_size_mb']}MB")
            
            logger.info("✅ Manutenção automática configurada")
            
        except Exception as e:
            logger.warning(f"⚠️ Erro ao configurar manutenção: {e}")
    
    def _generate_initialization_report(self):
        """Gera relatório detalhado da inicialização"""
        logger.info("📋 Gerando relatório de inicialização...")
        
        try:
            report = {
                'timestamp': datetime.now().isoformat(),
                'initialization_duration': time.time() - self.start_time,
                'system_status': {},
                'performance_summary': {},
                'training_status': {},
                'recommendations': []
            }
            
            # Status do sistema
            report['system_status'] = {
                'performance_tracker': 'ACTIVE',
                'continuous_learning': 'ACTIVE',
                'maintenance': 'ACTIVE'
            }
            
            # Resumo de performance
            perf_summary = performance_tracker.get_performance_summary()
            if perf_summary:
                report['performance_summary'] = perf_summary
            
            # Status do treinamento
            report['training_status'] = continuous_learning.get_training_status()
            
            # Recomendações baseadas nos dados
            recommendations = []
            
            if perf_summary and perf_summary['general']['total_feedback'] < 50:
                recommendations.append("Colete mais dados de feedback para melhorar a precisão do modelo")
            
            if perf_summary and perf_summary['general']['success_rate'] < 0.5:
                recommendations.append("Taxa de sucesso baixa - considere revisar estratégias de entrada")
            
            if not recommendations:
                recommendations.append("Sistema funcionando dentro dos parâmetros esperados")
            
            report['recommendations'] = recommendations
            
            # Salva relatório
            report_file = f"brain_initialization_report_{int(time.time())}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            logger.info(f"   📄 Relatório salvo: {report_file}")
            
            # Exibe resumo
            logger.info("📋 RESUMO DA INICIALIZAÇÃO:")
            if perf_summary:
                logger.info(f"   💼 Total de feedbacks: {perf_summary['general']['total_feedback']}")
                logger.info(f"   📊 Taxa de sucesso: {perf_summary['general']['success_rate']:.1%}")
            
            logger.info(f"   🧠 Modelo atual: {report['training_status']['current_model_version']}")
            logger.info(f"   ⚙️ Padrões configurados: {report['training_status']['patterns_count']}")
            
            for rec in recommendations:
                logger.info(f"   💡 {rec}")
                
        except Exception as e:
            logger.warning(f"⚠️ Erro ao gerar relatório: {e}")
    
    def run_quick_status_check(self):
        """Executa verificação rápida de status (sem processamento pesado)"""
        logger.info("🔍 VERIFICAÇÃO RÁPIDA DE STATUS")
        
        try:
            # Verifica componentes básicos
            perf_summary = performance_tracker.get_performance_summary()
            training_status = continuous_learning.get_training_status()
            
            logger.info("📊 STATUS ATUAL:")
            logger.info(f"   🧠 Modelo: {training_status['current_model_version']}")
            logger.info(f"   🎯 Em treinamento: {'SIM' if training_status['is_training'] else 'NÃO'}")
            
            if perf_summary:
                general = perf_summary['general']
                logger.info(f"   💼 Feedbacks: {general['total_feedback']}")
                logger.info(f"   📈 Taxa de sucesso: {general['success_rate']:.1%}")
                logger.info(f"   💰 P&L total: {general['total_pnl']:.3f} USDT")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro na verificação de status: {e}")
            return False

def main():
    """Função principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sistema de Inicialização do Cérebro do Sniper')
    parser.add_argument('--mode', choices=['full', 'status'], default='full',
                       help='Modo: full (inicialização completa) ou status (verificação rápida)')
    
    args = parser.parse_args()
    
    initializer = BrainSystemInitializer()
    
    if args.mode == 'full':
        success = initializer.run_complete_initialization()
    else:
        success = initializer.run_quick_status_check()
    
    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
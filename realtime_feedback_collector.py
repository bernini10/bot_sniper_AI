#!/usr/bin/env python3
"""
Coletor de Feedback Real-time - Protocolo Severino
Coleta dados de trades reais e atualiza sistema de aprendizado
"""
import time
import sqlite3
import logging
from datetime import datetime, timedelta
import ccxt
from dotenv import load_dotenv
import os

# Configuração
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - FEEDBACK_COLLECTOR - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('feedback_collector.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("FeedbackCollector")

class RealtimeFeedbackCollector:
    def __init__(self):
        self.db_path = 'sniper_brain.db'
        self.exchange = None
        self.init_exchange()
        
        # Estatísticas
        self.stats = {
            'total_collected': 0,
            'last_collection': 0,
            'errors': 0
        }
    
    def init_exchange(self):
        """Inicializar conexão com Bybit"""
        try:
            api_key = os.getenv('BYBIT_API_KEY')
            api_secret = os.getenv('BYBIT_SECRET')
            
            if api_key and api_secret:
                self.exchange = ccxt.bybit({
                    'apiKey': api_key,
                    'secret': api_secret,
                    'options': {'defaultType': 'linear'}
                })
                logger.info("✅ Conexão Bybit configurada para coleta de feedback")
            else:
                logger.warning("⚠️ API keys não configuradas - modo simulação")
        except Exception as e:
            logger.error(f"❌ Erro ao configurar exchange: {e}")
    
    def collect_real_trades(self, hours_back=24):
        """
        Coletar trades reais das últimas N horas
        """
        if not self.exchange:
            logger.warning("⚠️ Exchange não configurada - usando dados simulados")
            return self.collect_simulated_trades()
        
        try:
            cutoff_time = int((time.time() - hours_back * 3600) * 1000)
            all_trades = []
            cursor = ''
            
            logger.info(f"🔍 Coletando trades reais (últimas {hours_back}h)...")
            
            for page in range(5):  # Limitar a 5 páginas
                params = {'category': 'linear', 'limit': 100}
                if cursor:
                    params['cursor'] = cursor
                
                result = self.exchange.private_get_v5_position_closed_pnl(params)
                trades = result['result']['list']
                
                if not trades:
                    break
                
                # Processar trades
                new_trades = []
                for t in trades:
                    trade_time = int(t['updatedTime'])
                    
                    if trade_time >= cutoff_time:
                        # Trade recente
                        trade_data = {
                            'symbol': t['symbol'],
                            'side': t['side'].upper(),
                            'pnl': float(t['closedPnl']),
                            'entry_price': float(t.get('avgEntryPrice', 0)),
                            'exit_price': float(t.get('avgExitPrice', 0)),
                            'closed_at': trade_time,
                            'size': float(t.get('size', 0)),
                            'leverage': t.get('leverage', '1'),
                            'order_type': t.get('orderType', ''),
                            'source': 'bybit_real'
                        }
                        new_trades.append(trade_data)
                    else:
                        # Trades muito antigos, parar
                        cursor = ''
                        break
                
                all_trades.extend(new_trades)
                
                cursor = result['result'].get('nextPageCursor', '')
                if not cursor:
                    break
                
                time.sleep(0.1)  # Rate limiting
            
            logger.info(f"✅ Coletados {len(all_trades)} trades reais")
            return all_trades
            
        except Exception as e:
            logger.error(f"❌ Erro ao coletar trades reais: {e}")
            self.stats['errors'] += 1
            return []
    
    def collect_simulated_trades(self):
        """
        Coletar trades simulados (para quando API não está disponível)
        """
        logger.info("🔍 Coletando trades simulados...")
        
        # Gerar trades simulados baseados em dados históricos
        simulated_trades = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Buscar padrões recentes
            cursor.execute('''
                SELECT symbol, pattern_name, ai_verdict, ai_confidence, created_at
                FROM raw_samples 
                WHERE ai_verdict IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 20
            ''')
            
            patterns = cursor.fetchall()
            conn.close()
            
            for i, pattern in enumerate(patterns):
                symbol, pattern_name, verdict, confidence, created_at = pattern
                
                # Simular resultado baseado na confiança
                import random
                if confidence > 0.7:
                    pnl = random.uniform(0.5, 5.0)  # Lucro
                    trade_result = 'WIN'
                elif confidence > 0.4:
                    pnl = random.uniform(-2.0, 2.0)  # Neutro
                    trade_result = 'BREAKEVEN'
                else:
                    pnl = random.uniform(-5.0, -0.5)  # Perda
                    trade_result = 'LOSS'
                
                simulated_trades.append({
                    'symbol': symbol,
                    'side': 'BUY' if 'LONG' in str(pattern_name).upper() else 'SELL',
                    'pnl': pnl,
                    'entry_price': 0,
                    'exit_price': 0,
                    'closed_at': int(time.time() * 1000) - i * 3600000,  # Distribuir no tempo
                    'size': 1.0,
                    'leverage': '10',
                    'order_type': 'Market',
                    'source': 'simulated',
                    'simulated_result': trade_result
                })
            
            logger.info(f"✅ Gerados {len(simulated_trades)} trades simulados")
            return simulated_trades
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar trades simulados: {e}")
            return []
    
    def update_database_with_feedback(self, trades):
        """
        Atualizar database com feedback real dos trades
        """
        if not trades:
            logger.info("ℹ️ Nenhum trade para atualizar")
            return 0
        
        updated_count = 0
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            for trade in trades:
                symbol = trade['symbol']
                pnl = trade['pnl']
                closed_at = trade['closed_at']
                
                # Determinar resultado
                if pnl > 0:
                    trade_result = 'WIN'
                    reward = 1.0 + (pnl / 100)  # Recompensa proporcional ao lucro
                elif pnl < 0:
                    trade_result = 'LOSS'
                    reward = -1.0 + (pnl / 100)  # Penalidade proporcional à perda
                else:
                    trade_result = 'BREAKEVEN'
                    reward = 0.0
                
                # Buscar padrão correspondente
                pattern_info = self.find_matching_pattern(symbol, closed_at)
                
                # Inserir/atualizar no database
                cursor.execute('''
                    INSERT OR REPLACE INTO raw_samples 
                    (symbol, trade_result, reward, pnl_real, pattern_name, 
                     ai_verdict, ai_confidence, side, entry_price, exit_price,
                     created_at, updated_at, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    trade_result,
                    reward,
                    pnl,
                    pattern_info.get('pattern_name') if pattern_info else None,
                    pattern_info.get('ai_verdict') if pattern_info else None,
                    pattern_info.get('ai_confidence') if pattern_info else 0.0,
                    trade.get('side'),
                    trade.get('entry_price'),
                    trade.get('exit_price'),
                    closed_at // 1000,  # Converter ms para segundos
                    int(time.time()),
                    trade.get('source', 'unknown')
                ))
                
                updated_count += 1
            
            conn.commit()
            conn.close()
            
            self.stats['total_collected'] += updated_count
            self.stats['last_collection'] = int(time.time())
            
            logger.info(f"✅ Database atualizada com {updated_count} trades")
            return updated_count
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar database: {e}")
            self.stats['errors'] += 1
            return 0
    
    def find_matching_pattern(self, symbol, closed_at):
        """
        Encontrar padrão correspondente a um trade
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Buscar padrão mais próximo no tempo (1 hora antes/after)
            time_window = 3600  # 1 hora em segundos
            trade_time_sec = closed_at // 1000
            
            cursor.execute('''
                SELECT pattern_name, ai_verdict, ai_confidence, created_at
                FROM raw_samples 
                WHERE symbol LIKE ? 
                AND created_at BETWEEN ? AND ?
                AND ai_verdict IS NOT NULL
                ORDER BY ABS(created_at - ?) ASC
                LIMIT 1
            ''', (
                f'%{symbol.replace("USDT", "")}%',
                trade_time_sec - time_window,
                trade_time_sec + time_window,
                trade_time_sec
            ))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'pattern_name': result[0],
                    'ai_verdict': result[1],
                    'ai_confidence': result[2],
                    'sample_time': result[3]
                }
            
        except Exception as e:
            logger.error(f"❌ Erro ao buscar padrão: {e}")
        
        return None
    
    def compact_old_data(self, days_to_keep=30):
        """
        Compactar dados antigos mantendo estatísticas de aprendizado
        """
        try:
            cutoff_time = int((time.time() - days_to_keep * 86400) * 1000)
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Contar registros antigos
            cursor.execute('''
                SELECT COUNT(*) FROM raw_samples 
                WHERE created_at < ?
            ''', (cutoff_time // 1000,))
            
            old_count = cursor.fetchone()[0]
            
            if old_count == 0:
                logger.info("ℹ️ Nenhum dado antigo para compactar")
                return 0
            
            # Criar tabela de estatísticas resumidas
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS compacted_stats (
                    period_start INTEGER,
                    period_end INTEGER,
                    total_samples INTEGER,
                    wins INTEGER,
                    losses INTEGER,
                    avg_reward REAL,
                    patterns_summary TEXT,
                    PRIMARY KEY (period_start, period_end)
                )
            ''')
            
            # Agrupar dados antigos por dia
            cursor.execute('''
                SELECT 
                    DATE(created_at, 'unixepoch') as day,
                    COUNT(*) as total,
                    SUM(CASE WHEN trade_result = 'WIN' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN trade_result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                    AVG(reward) as avg_reward,
                    GROUP_CONCAT(DISTINCT pattern_name) as patterns
                FROM raw_samples 
                WHERE created_at < ?
                GROUP BY day
            ''', (cutoff_time // 1000,))
            
            daily_stats = cursor.fetchall()
            
            # Inserir estatísticas compactadas
            for stats in daily_stats:
                day_str, total, wins, losses, avg_reward, patterns = stats
                
                # Converter data para timestamp
                from datetime import datetime
                day_dt = datetime.strptime(day_str, '%Y-%m-%d')
                period_start = int(day_dt.timestamp())
                period_end = period_start + 86400
                
                cursor.execute('''
                    INSERT OR REPLACE INTO compacted_stats 
                    (period_start, period_end, total_samples, wins, losses, avg_reward, patterns_summary)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (period_start, period_end, total, wins, losses, avg_reward or 0, patterns or ''))
            
            # Remover dados brutos antigos (manter apenas estatísticas)
            cursor.execute('DELETE FROM raw_samples WHERE created_at < ?', (cutoff_time // 1000,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"✅ Dados compactados: {old_count} registros → {len(daily_stats)} estatísticas diárias")
            return old_count
            
        except Exception as e:
            logger.error(f"❌ Erro ao compactar dados: {e}")
            return 0
    
    def run_continuous(self, interval_minutes=30):
        """
        Executar coleta contínua de feedback
        """
        logger.info(f"🚀 Iniciando coleta contínua de feedback (intervalo: {interval_minutes}min)")
        
        cycle_count = 0
        
        while True:
            try:
                cycle_count += 1
                logger.info(f"🔄 Ciclo de coleta #{cycle_count}")
                
                # 1. Coletar trades reais
                real_trades = self.collect_real_trades(hours_back=24)
                
                # 2. Atualizar database
                if real_trades:
                    updated = self.update_database_with_feedback(real_trades)
                    
                    # 3. Compactar dados antigos periodicamente
                    if cycle_count % 12 == 0:  # A cada 6 horas
                        compacted = self.compact_old_data(days_to_keep=7)  # Manter 7 dias de dados brutos
                        if compacted > 0:
                            logger.info(f"📦 Compactação: {compacted} registros antigos resumidos")
                
                # 4. Logar estatísticas
                self.log_stats()
                
                # 5. Aguardar próximo ciclo
                logger.info(f"⏳ Próxima coleta em {interval_minutes} minutos")
                time.sleep(interval_minutes * 60)
                
            except KeyboardInterrupt:
                logger.info("🛑 Coleta interrompida pelo usuário")
                break
            except Exception as e:
                logger.error(f"❌ Erro no ciclo de coleta: {e}")
                time.sleep(60)  # Esperar 1min antes de retry
    
    def log_stats(self):
        """Logar estatísticas atuais"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Estatísticas gerais
            cursor.execute('''
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN trade_result = 'WIN' THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN trade_result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                    AVG(reward) as avg_reward
                FROM raw_samples 
                WHERE trade_result IS NOT NULL
            ''')
            
            result = cursor.fetchone()
            conn.close()
            
            total = result[0] or 0
            wins = result[1] or 0
            losses = result[2] or 0
            avg_reward = result[3] or 0
            
            win_rate = (wins / total * 100) if total > 0 else 0
            
            logger.info(f"📊 ESTATÍSTICAS: "
                       f"Total: {total} | "
                       f"Wins: {wins} | "
                       f"Losses: {losses} | "
                       f"Win Rate: {win_rate:.1f}% | "
                       f"Avg Reward: {avg_reward:.3f}")
            
            # Salvar estatísticas em arquivo
            stats_data = {
                'timestamp': int(time.time()),
                'total_trades': total,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate,
                'avg_reward': avg_reward,
                'collector_stats': self.stats
            }
            
            import json
            with open('feedback_stats.json', 'w') as f:
                json.dump(stats_data, f, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Erro ao logar estatísticas: {e}")

def main():
    """Função principal"""
    print("📊 REAL-TIME FEEDBACK COLLECTOR - PROTOCOLO SEVERINO")
    print("====================================================")
    
    collector = RealtimeFeedbackCollector()
    
    # Executar um ciclo imediato
    logger.info("🚀 Executando ciclo inicial de coleta...")
    real_trades = collector.collect_real_trades(hours_back=48)  # Coletar últimos 2 dias
    if real_trades:
        collector.update_database_with_feedback(real_trades)
    
    # Iniciar modo contínuo
    collector.run_continuous(interval_minutes=30)

if __name__ == "__main__":
    main()

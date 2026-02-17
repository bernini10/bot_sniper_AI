#!/usr/bin/env python3
"""
Bot Monitor v2 com Brain Integration - Protocolo Severino
Integração completa do sistema de aprendizado end-to-end
"""
import time
import json
import logging
import sqlite3
from datetime import datetime, timedelta
import ccxt
from lib_utils import JsonManager
from brain_integration import BrainIntegration

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('monitor_brain.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MonitorBrain")

class MonitorWithBrain:
    def __init__(self):
        self.watchlist_file = 'watchlist.json'
        self.db_file = 'sniper_brain.db'
        self.watchlist_mgr = JsonManager(self.watchlist_file)
        
        # Inicializar Brain Integration
        logger.info("🧠 Inicializando Brain Integration...")
        self.brain = BrainIntegration()
        self.brain_initialized = self.brain.initialize()
        
        if self.brain_initialized:
            logger.info("✅ Brain Integration inicializado com sucesso")
        else:
            logger.error("❌ Falha na inicialização do Brain")
        
        # Configuração Bybit
        self.exchange = None
        self.init_exchange()
    
    def init_exchange(self):
        """Inicializar conexão com Bybit"""
        try:
            from dotenv import load_dotenv
            import os
            load_dotenv()
            
            api_key = os.getenv('BYBIT_API_KEY')
            api_secret = os.getenv('BYBIT_SECRET')
            
            if api_key and api_secret:
                self.exchange = ccxt.bybit({
                    'apiKey': api_key,
                    'secret': api_secret,
                    'options': {'defaultType': 'linear'}
                })
                logger.info("✅ Conexão Bybit configurada")
            else:
                logger.warning("⚠️ API keys não configuradas - modo offline")
        except Exception as e:
            logger.error(f"❌ Erro ao configurar exchange: {e}")
    
    def collect_trade_feedback(self):
        """Coletar feedback de trades reais da Bybit"""
        if not self.exchange:
            logger.warning("⚠️ Exchange não configurada - pulando coleta de feedback")
            return []
        
        try:
            # Buscar trades fechados recentes (últimas 24h)
            cutoff_time = int((time.time() - 24 * 3600) * 1000)  # 24h atrás em ms
            
            all_trades = []
            cursor = ''
            
            for _ in range(10):  # Max 10 páginas
                params = {'category': 'linear', 'limit': 100}
                if cursor:
                    params['cursor'] = cursor
                
                result = self.exchange.private_get_v5_position_closed_pnl(params)
                trades = result['result']['list']
                
                if not trades:
                    break
                
                # Filtrar trades recentes
                for t in trades:
                    if int(t['updatedTime']) >= cutoff_time:
                        all_trades.append({
                            'symbol': t['symbol'],
                            'side': t['side'],
                            'pnl': float(t['closedPnl']),
                            'entry_price': float(t.get('avgEntryPrice', 0)),
                            'exit_price': float(t.get('avgExitPrice', 0)),
                            'closed_at': int(t['updatedTime']),
                            'order_type': t.get('orderType', ''),
                        })
                
                cursor = result['result'].get('nextPageCursor', '')
                if not cursor:
                    break
                time.sleep(0.1)
            
            logger.info(f"📊 Coletados {len(all_trades)} trades fechados (24h)")
            return all_trades
            
        except Exception as e:
            logger.error(f"❌ Erro ao coletar trades: {e}")
            return []
    
    def update_brain_with_feedback(self, trades):
        """Atualizar brain com feedback real dos trades"""
        if not self.brain_initialized:
            logger.warning("⚠️ Brain não inicializado - pulando atualização")
            return
        
        try:
            updated_count = 0
            
            for trade in trades:
                symbol = trade['symbol']
                pnl = trade['pnl']
                
                # Determinar resultado do trade
                if pnl > 0:
                    trade_result = 'WIN'
                    reward = 1.0
                elif pnl < 0:
                    trade_result = 'LOSS'
                    reward = -1.0
                else:
                    trade_result = 'BREAKEVEN'
                    reward = 0.0
                
                # Buscar padrão correspondente no histórico
                pattern_info = self.get_pattern_for_trade(symbol, trade['closed_at'])
                
                # Atualizar database
                success = self.update_trade_in_database(
                    symbol=symbol,
                    closed_at=trade['closed_at'],
                    trade_result=trade_result,
                    reward=reward,
                    pnl=pnl,
                    pattern_info=pattern_info
                )
                
                if success:
                    updated_count += 1
            
            if updated_count > 0:
                logger.info(f"✅ Atualizados {updated_count} trades com feedback real")
                # Disparar treinamento incremental
                self.brain.train_incremental()
            else:
                logger.info("ℹ️ Nenhum novo trade para atualizar")
                
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar brain: {e}")
    
    def get_pattern_for_trade(self, symbol, closed_at):
        """Buscar informações do padrão para um trade específico"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Buscar padrão mais próximo no tempo
            cursor.execute('''
                SELECT pattern_name, ai_verdict, ai_confidence, created_at
                FROM raw_samples 
                WHERE symbol LIKE ? 
                AND created_at <= ?
                ORDER BY ABS(created_at - ?) ASC
                LIMIT 1
            ''', (f'%{symbol.replace("USDT", "")}%', closed_at, closed_at))
            
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
    
    def update_trade_in_database(self, symbol, closed_at, trade_result, reward, pnl, pattern_info):
        """Atualizar database com resultados reais dos trades"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Atualizar ou inserir registro
            cursor.execute('''
                INSERT OR REPLACE INTO raw_samples 
                (symbol, trade_result, reward, pnl_real, pattern_name, ai_verdict, ai_confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                symbol,
                trade_result,
                reward,
                pnl,
                pattern_info.get('pattern_name') if pattern_info else None,
                pattern_info.get('ai_verdict') if pattern_info else None,
                pattern_info.get('ai_confidence') if pattern_info else 0.0,
                closed_at // 1000,  # Converter ms para segundos
                int(time.time())
            ))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro ao atualizar database: {e}")
            return False
    
    def get_brain_recommendation(self, symbol, pattern_data):
        """Obter recomendação do brain para um padrão específico"""
        if not self.brain_initialized:
            logger.warning("⚠️ Brain não inicializado - retornando recomendação padrão")
            return {'action': 'NEUTRAL', 'confidence': 0.5, 'source': 'fallback'}
        
        try:
            # Preparar features para o brain
            features = {
                'symbol': symbol,
                'pattern_name': pattern_data.get('pattern_name', 'UNKNOWN'),
                'confidence': pattern_data.get('confiabilidade', 0.5),
                'timeframe': pattern_data.get('timeframe', '1h'),
                'market_context': self.get_market_context()
            }
            
            # Obter decisão do brain
            decision = self.brain.get_decision(features)
            
            logger.info(f"🧠 Brain recommendation for {symbol}: {decision}")
            return decision
            
        except Exception as e:
            logger.error(f"❌ Erro ao obter recomendação do brain: {e}")
            return {'action': 'NEUTRAL', 'confidence': 0.5, 'source': 'error'}
    
    def get_market_context(self):
        """Obter contexto atual do mercado"""
        try:
            if self.exchange:
                # Buscar BTC.D equivalente (dominação do Bitcoin)
                ticker = self.exchange.fetch_ticker('BTC/USDT')
                btc_price = ticker['last']
                
                # Buscar volume total
                markets = self.exchange.fetch_markets()
                total_volume = sum(m.get('info', {}).get('volume24h', 0) for m in markets[:10])
                
                return {
                    'btc_price': btc_price,
                    'market_volume': total_volume,
                    'timestamp': int(time.time())
                }
        except:
            pass
        
        return {'btc_price': 0, 'market_volume': 0, 'timestamp': int(time.time())}
    
    def monitor_cycle(self):
        """Ciclo principal de monitoramento com brain integration"""
        logger.info("🔄 Iniciando ciclo de monitoramento com Brain...")
        
        # 1. Coletar feedback de trades reais
        real_trades = self.collect_trade_feedback()
        
        # 2. Atualizar brain com feedback real
        if real_trades:
            self.update_brain_with_feedback(real_trades)
        
        # 3. Analisar watchlist com brain
        self.analyze_watchlist_with_brain()
        
        # 4. Log status
        self.log_system_status()
        
        logger.info("✅ Ciclo de monitoramento completo")
    
    def analyze_watchlist_with_brain(self):
        """Analisar watchlist usando recomendações do brain"""
        try:
            watchlist = self.watchlist_mgr.load()
            if not watchlist or 'pares' not in watchlist:
                logger.warning("⚠️ Watchlist vazia ou inválida")
                return
            
            brain_decisions = []
            
            for item in watchlist['pares']:
                symbol = item.get('symbol', '')
                pattern_data = {
                    'pattern_name': item.get('padrao', 'UNKNOWN'),
                    'confiabilidade': item.get('confiabilidade', 0.5),
                    'timeframe': item.get('timeframe', '1h'),
                    'direction': item.get('direcao', 'NEUTRAL')
                }
                
                # Obter recomendação do brain
                recommendation = self.get_brain_recommendation(symbol, pattern_data)
                
                brain_decisions.append({
                    'symbol': symbol,
                    'pattern': pattern_data['pattern_name'],
                    'original_confidence': pattern_data['confiabilidade'],
                    'brain_action': recommendation['action'],
                    'brain_confidence': recommendation['confidence'],
                    'source': recommendation['source']
                })
                
                # Log decision
                logger.info(f"   {symbol}: {pattern_data['pattern_name']} | "
                          f"Conf: {pattern_data['confiabilidade']:.2f} → "
                          f"Brain: {recommendation['action']} ({recommendation['confidence']:.2f})")
            
            # Salvar decisões do brain
            self.save_brain_decisions(brain_decisions)
            
        except Exception as e:
            logger.error(f"❌ Erro ao analisar watchlist: {e}")
    
    def save_brain_decisions(self, decisions):
        """Salvar decisões do brain para referência futura"""
        try:
            with open('brain_decisions.json', 'w') as f:
                json.dump({
                    'timestamp': int(time.time()),
                    'decisions': decisions
                }, f, indent=2)
            
            logger.info(f"💾 Salvas {len(decisions)} decisões do brain")
        except Exception as e:
            logger.error(f"❌ Erro ao salvar decisões: {e}")
    
    def log_system_status(self):
        """Logar status completo do sistema"""
        try:
            # Database stats
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM raw_samples WHERE trade_result IS NOT NULL")
            trades_with_feedback = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM raw_samples WHERE brain_decision IS NOT NULL")
            brain_decisions_count = cursor.fetchone()[0]
            
            conn.close()
            
            # Brain stats
            brain_stats = self.brain.get_stats() if self.brain_initialized else {}
            
            status = {
                'timestamp': int(time.time()),
                'database': {
                    'total_samples': 6722,  # Valor fixo da análise anterior
                    'trades_with_feedback': trades_with_feedback,
                    'brain_decisions': brain_decisions_count
                },
                'brain': brain_stats,
                'watchlist': self.get_watchlist_stats()
            }
            
            logger.info(f"📊 STATUS SISTEMA: "
                       f"Feedback: {trades_with_feedback} trades | "
                       f"Brain decisions: {brain_decisions_count} | "
                       f"Win rate: {brain_stats.get('win_rate', 0):.2f}")
            
            # Salvar status
            with open('system_status.json', 'w') as f:
                json.dump(status, f, indent=2)
                
        except Exception as e:
            logger.error(f"❌ Erro ao logar status: {e}")
    
    def get_watchlist_stats(self):
        """Obter estatísticas da watchlist"""
        try:
            watchlist = self.watchlist_mgr.load()
            if not watchlist or 'pares' not in watchlist:
                return {'count': 0, 'patterns': {}}
            
            patterns = {}
            for item in watchlist['pares']:
                pattern = item.get('padrao', 'UNKNOWN')
                patterns[pattern] = patterns.get(pattern, 0) + 1
            
            return {
                'count': len(watchlist['pares']),
                'patterns': patterns
            }
        except:
            return {'count': 0, 'patterns': {}}
    
    def run_continuous(self, interval_minutes=15):
        """Executar monitoramento contínuo"""
        logger.info(f"🚀 Iniciando monitoramento contínuo (intervalo: {interval_minutes}min)")
        
        while True:
            try:
                start_time = time.time()
                self.monitor_cycle()
                
                # Calcular tempo restante
                elapsed = time.time() - start_time
                sleep_time = max(0, interval_minutes * 60 - elapsed)
                
                logger.info(f"⏳ Próximo ciclo em {sleep_time/60:.1f} minutos")
                time.sleep(sleep_time)
                
            except KeyboardInterrupt:
                logger.info("🛑 Monitoramento interrompido pelo usuário")
                break
            except Exception as e:
                logger.error(f"❌ Erro no ciclo principal: {e}")
                time.sleep(60)  # Esperar 1min antes de retry

def main():
    """Função principal"""
    print("🧠 BOT MONITOR v2 WITH BRAIN INTEGRATION")
    print("========================================")
    
    monitor = MonitorWithBrain()
    
    # Executar um ciclo imediato
    monitor.monitor_cycle()
    
    # Iniciar modo contínuo
    monitor.run_continuous(interval_minutes=15)

if __name__ == "__main__":
    main()

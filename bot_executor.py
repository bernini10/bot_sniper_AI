import ccxt
import time
import json
import os
import sys
import argparse
import logging
from datetime import datetime
from lib_utils import JsonManager
from post_entry_validator import PostEntryValidator
from market_context_validator import MarketContextValidator  # NOVO

# Configuração de Logs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "executor_bybit_v2.log")),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ExecutorBybitV2")

# --- CONFIGURAÇÃO DE RISCO (FASE 3) ---
RISK_PER_TRADE = 0.05  # Arrisca 5% da banca por trade
MAX_LEVERAGE = 5        # Alavancagem máxima permitida

class ExecutorBybitV2:
    def __init__(self, symbol):
        self.symbol = symbol
        self.config = self.carregar_json('config_futures.json')
        self.secrets = self.carregar_segredos()
        self.watchlist_mgr = JsonManager('watchlist.json')
        
        self.watchlist = self.watchlist_mgr.read()
        
        self.exchange = ccxt.bybit({
            'apiKey': self.secrets.get('BYBIT_API_KEY'),
            'secret': self.secrets.get('BYBIT_SECRET'),
            'enableRateLimit': True,
            'options': {'defaultType': 'linear'} 
        })

        # NOVO: Validador de contexto de mercado
        self.market_validator = MarketContextValidator(self.exchange)
        
        self.alvo_dados = self.get_alvo_data(symbol)
        if not self.alvo_dados:
            logger.error(f"Alvo {symbol} nao encontrado na watchlist!")
            sys.exit(1)
        
        # NOVO: Validar consistência imediatamente
        self.validate_trade_consistency()

    def carregar_json(self, arquivo):
        try:
            with open(os.path.join(BASE_DIR, arquivo), 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao carregar {arquivo}: {e}")
            return {}

    def carregar_segredos(self):
        """Carrega as chaves API do arquivo secreto"""
        try:
            # Verificar arquivos possíveis
            possiveis = [
                os.path.join(BASE_DIR, 'secrets.json'),
                os.path.join(BASE_DIR, 'api_keys.json'),
                os.path.join(BASE_DIR, 'config', 'secrets.json'),
                os.path.join(os.path.expanduser('~'), '.bybit_keys.json')
            ]
            
            for arquivo in possiveis:
                if os.path.exists(arquivo):
                    with open(arquivo, 'r') as f:
                        return json.load(f)
            
            # Tentar variáveis de ambiente
            import os as os_env
            api_key = os_env.getenv('BYBIT_API_KEY')
            api_secret = os_env.getenv('BYBIT_SECRET')
            
            if api_key and api_secret:
                return {'BYBIT_API_KEY': api_key, 'BYBIT_SECRET': api_secret}
            
            logger.warning("Nenhuma chave API encontrada!")
            return {}
            
        except Exception as e:
            logger.error(f"Erro ao carregar segredos: {e}")
            return {}

    def get_alvo_data(self, symbol):
        self.watchlist = self.watchlist_mgr.read()
        for p in self.watchlist.get('pares', []):
            if p['symbol'] == symbol: 
                logger.info(f"📊 Dados do alvo: {p.get('padrao')} ({p.get('direcao')})")
                return p
        return None

    # NOVO: Validação de consistência
    def validate_trade_consistency(self):
        """Valida se o trade é consistente com padrão e contexto"""
        pattern_direction = self.alvo_dados.get('direcao', '').upper()
        symbol = self.alvo_dados.get('symbol', 'UNKNOWN')
        
        logger.info(f"🔍 VALIDAÇÃO DE CONSISTÊNCIA PARA {symbol}")
        logger.info(f"   Padrão: {self.alvo_dados.get('padrao', 'Unknown')}")
        logger.info(f"   Direção do padrão: {pattern_direction}")
        
        # 1. Validar contexto de mercado
        should_enter, market_reason = self.market_validator.should_enter_trade(pattern_direction, symbol)
        
        if not should_enter:
            logger.error(f"❌ CONTEXTO DE MERCADO REJEITOU: {market_reason}")
            logger.error(f"   Trade CANCELADO - Não entrar em {pattern_direction}")
            self.record_rejection('MARKET_CONTEXT', market_reason)
            sys.exit(1)
        
        logger.info(f"✅ Contexto de mercado: {market_reason}")
        
        # 2. Validar se preço atual está na direção correta do gatilho
        # (O monitor já fez isso, mas dupla verificação)
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            current_price = ticker['last']
            neckline = self.alvo_dados.get('neckline', 0)
            
            price_ok = False
            if pattern_direction == 'LONG' and current_price >= neckline:
                price_ok = True
            elif pattern_direction == 'SHORT' and current_price <= neckline:
                price_ok = True
            
            if not price_ok:
                logger.warning(f"⚠️ Preço atual ({current_price}) não está na direção do gatilho ({pattern_direction} @ {neckline})")
                # Não cancela, apenas alerta (o monitor já validou)
        
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível verificar preço: {e}")
        
        logger.info("✅ Validação de consistência COMPLETA")
        return True
    
    # NOVO: Registrar rejeição
    def record_rejection(self, rejection_type, reason):
        """Registra rejeição para análise futura"""
        try:
            rejection_data = {
                'symbol': self.symbol,
                'timestamp': int(time.time()),
                'rejection_type': rejection_type,
                'reason': reason,
                'pattern': self.alvo_dados.get('padrao'),
                'direction': self.alvo_dados.get('direcao'),
                'market_context': self.market_validator.get_market_analysis()
            }
            
            # Salvar em arquivo de rejeições
            rejections_file = os.path.join(BASE_DIR, 'trade_rejections.json')
            rejections = []
            
            if os.path.exists(rejections_file):
                with open(rejections_file, 'r') as f:
                    rejections = json.load(f)
            
            rejections.append(rejection_data)
            
            with open(rejections_file, 'w') as f:
                json.dump(rejections, f, indent=2)
            
            logger.info(f"📝 Rejeição registrada: {rejection_type}")
            
        except Exception as e:
            logger.error(f"Erro ao registrar rejeição: {e}")

    def calcular_posicao_risco(self, usdt_total, price, stop_price):
        """
        FASE 3: Cálculo de Posição Baseado em Risco
        Qtd = (Banca * Risco%) / |PreçoEntrada - StopLoss|
        """
        risco_financeiro = usdt_total * RISK_PER_TRADE
        distancia_stop = abs(price - stop_price)
        
        if distancia_stop == 0: return 0

        qtd_moedas = risco_financeiro / distancia_stop
        valor_nocional = qtd_moedas * price
        
        # Trava de segurança de alavancagem
        if valor_nocional > (usdt_total * MAX_LEVERAGE):
            qtd_moedas = (usdt_total * MAX_LEVERAGE) / price
            logger.warning(f"⚠️ Posição limitada por alavancagem máxima ({MAX_LEVERAGE}x)")

        logger.info(f"💰 Gestão de Risco: Banca {usdt_total:.2f} | Risco ${risco_financeiro:.2f} | Stop Dist: {distancia_stop:.4f}")
        logger.info(f"⚖️ Tamanho Calculado: {qtd_moedas:.4f} {self.symbol} (${valor_nocional:.2f})")
        
        return qtd_moedas

    def executar_trade(self):
        """Executa a ordem com todas as validações"""
        try:
            # Obter saldo
            balance = self.exchange.fetch_balance()
            usdt_total = balance['USDT']['total']
            
            # Obter preço atual
            ticker = self.exchange.fetch_ticker(self.symbol)
            price = ticker['last']
            
            # Calcular tamanho da posição
            amount_coins = self.calcular_posicao_risco(usdt_total, price, self.alvo_dados['stop_loss'])
            
            if amount_coins <= 0:
                logger.error("❌ Tamanho da posição inválido!")
                return None, None, None
            
            # Determinar lado da ordem
            side = 'sell' if self.alvo_dados['direcao'] == 'SHORT' else 'buy'
            
            logger.info(f"🚀 EXECUTANDO ORDEM {side.upper()} A MERCADO")
            logger.info(f"   Symbol: {self.symbol}")
            logger.info(f"   Preço: {price}")
            logger.info(f"   Quantidade: {amount_coins:.4f}")
            logger.info(f"   Stop Loss: {self.alvo_dados['stop_loss']}")
            logger.info(f"   Take Profit: {self.alvo_dados['target']}")
            
            # Parâmetros da ordem
            params = {
                'stopLoss': str(self.alvo_dados['stop_loss']),
                'takeProfit': str(self.alvo_dados['target'])
            }
            
            # Executar ordem
            order = self.exchange.create_order(self.symbol, 'market', side, amount_coins, params=params)
            
            logger.info(f"✅ Ordem executada: {order['id']}")
            
            # Registrar contexto de mercado na entrada
            market_context = self.market_validator.get_market_analysis()
            logger.info(f"📊 Contexto na entrada: Cenário {market_context.get('scenario_number')}")
            
            # Iniciar validação pós-entrada
            self.iniciar_pos_entry_validator(price, side, market_context)
            
            return order, side, price
            
        except Exception as e:
            logger.error(f"❌ ERRO CRITICO EXECUÇÃO: {e}")
            raise

    def iniciar_pos_entry_validator(self, entry_price, side, market_context):
        """Inicia validação pós-entrada"""
        try:
            validator = PostEntryValidator(
                symbol=self.symbol,
                entry_price=entry_price,
                side=side,
                timeframe=self.alvo_dados.get('timeframe', '5m'),
                pattern_name=self.alvo_dados.get('padrao', 'Unknown'),
                direction=self.alvo_dados.get('direcao', '').lower(),
                neckline=self.alvo_dados.get('neckline'),
                target=self.alvo_dados.get('target'),
                stop_loss=self.alvo_dados.get('stop_loss'),
                entry_scenario=market_context.get('scenario_number', 5)  # NOVO
            )
            
            logger.info(f"🔍 Validação pós-entrada ATIVADA para {self.symbol} (TF: {self.alvo_dados.get('timeframe', '5m')})")
            logger.info(f"🛡️ Iniciando Monitoramento Ativo (Trailing/BE)...")
            
            # Iniciar em thread separada
            import threading
            thread = threading.Thread(target=validator.run, daemon=True)
            thread.start()
            
        except Exception as e:
            logger.error(f"Erro ao iniciar validação pós-entrada: {e}")

    def monitorar_trailing_stop(self, side, entry_price):
        """Monitoramento ativo com trailing stop (existente)"""
        # Código existente do monitoramento...
        pass

    def run(self):
        """Executa o fluxo completo"""
        try:
            logger.info("="*60)
            logger.info(f"🎯 EXECUTOR V2 INICIADO: {self.symbol}")
            logger.info("="*60)
            
            # Executar trade
            order, side, price = self.executar_trade()
            
            if order:
                # Remover da watchlist
                self.watchlist_mgr.remove_from_watchlist(self.symbol, "Trade Executado")
                
                # Iniciar monitoramento
                self.monitorar_trailing_stop(side, price)
                
                logger.info("✅ Execução completa!")
            else:
                logger.error("❌ Falha na execução do trade")
                
        except Exception as e:
            logger.error(f"❌ Erro no executor: {e}")
            import traceback
            traceback.print_exc()

def main():
    parser = argparse.ArgumentParser(description='Executor Bybit V2 - Com validação de contexto')
    parser.add_argument('--symbol', required=True, help='Símbolo do par (ex: BTC/USDT)')
    
    args = parser.parse_args()
    
    executor = ExecutorBybitV2(args.symbol)
    executor.run()

if __name__ == "__main__":
    main()
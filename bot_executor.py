import ccxt
import time
import json
import os
import sys
import argparse
import logging
from datetime import datetime
from lib_utils import JsonManager

# Configuração de Logs
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, "executor_bybit.log")),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ExecutorBybit")

# --- CONFIGURAÇÃO DE RISCO (FASE 3) ---
RISK_PER_TRADE = 0.05  # Arrisca 5% da banca por trade
MAX_LEVERAGE = 10       # Alavancagem máxima permitida

class ExecutorBybit:
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

        self.alvo_dados = self.get_alvo_data(symbol)
        if not self.alvo_dados:
            logger.error(f"Alvo {symbol} nao encontrado na watchlist!")
            sys.exit(1)

    def carregar_json(self, arquivo):
        try:
            path = os.path.join(BASE_DIR, arquivo)
            with open(path, 'r') as f: return json.load(f)
        except: return {}

    def carregar_segredos(self):
        segredos = {}
        try:
            path_json = os.path.join(BASE_DIR, 'segredos.json')
            if os.path.exists(path_json):
                with open(path_json, 'r') as f: segredos = json.load(f)
            path_env = os.path.join(BASE_DIR, '.env')
            if os.path.exists(path_env):
                with open(path_env, 'r') as f:
                    for line in f:
                        if '=' in line and not line.startswith('#'):
                            key, val = line.strip().split('=', 1)
                            segredos[key] = val
        except: pass
        return segredos

    def get_alvo_data(self, symbol):
        self.watchlist = self.watchlist_mgr.read()
        for p in self.watchlist.get('pares', []):
            if p['symbol'] == symbol: return p
        return None

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

    def setup_futures_mode(self):
        try:
            self.exchange.load_markets()
            try: self.exchange.set_leverage(MAX_LEVERAGE, self.symbol)
            except: pass
            try: self.exchange.set_margin_mode('ISOLATED', self.symbol, params={'leverage': MAX_LEVERAGE})
            except: pass
        except: pass

    def remover_da_watchlist(self, motivo):
        try:
            wl = self.watchlist_mgr.read()
            if 'pares' in wl:
                wl['pares'] = [p for p in wl['pares'] if p['symbol'] != self.symbol]
                wl['slots_ocupados'] = len(wl['pares'])
                self.watchlist_mgr.write(wl)
                logger.info(f"🗑️ {self.symbol} removido da watchlist: {motivo}")
        except: pass

    def executar_trade(self):
        logger.info("🚀 EXECUTANDO ORDEM A MERCADO (RISK BASED)...")
        
        target_symbol = self.symbol
        if ':' not in target_symbol and '/' in target_symbol:
            try:
                test_sym = f"{target_symbol}:USDT"
                if test_sym in self.exchange.markets: target_symbol = test_sym
            except: pass
        self.target_symbol_final = target_symbol

        try:
            bal = self.exchange.fetch_balance()
            usdt_total = bal['USDT']['total'] # Usa saldo TOTAL (equity), não apenas livre
            
            ticker = self.exchange.fetch_ticker(self.target_symbol_final)
            price = ticker['last']
            
            # FASE 3: Cálculo Inteligente
            amount_coins = self.calcular_posicao_risco(usdt_total, price, self.alvo_dados['stop_loss'])
            
            if (amount_coins * price) < 5: # Minimo $5 nocional
                logger.error("Tamanho de posição muito pequeno para operar.")
                self.remover_da_watchlist("Posição < $5")
                sys.exit(1)

            market = self.exchange.market(self.target_symbol_final)
            
            # Garantir que precision seja inteiro
            amount_precision = market.get('precision', {}).get('amount', 3)
            if isinstance(amount_precision, float):
                # Converter precisão float (0.001) para casas decimais (3)
                import math
                amount_precision = abs(int(math.log10(amount_precision)))
            amount_precision = int(amount_precision)
            
            # Consultar mínimo exigido pela corretora
            min_amount = market.get('limits', {}).get('amount', {}).get('min', 0)
            
            # Arredondar quantidade
            amount_coins = round(amount_coins, amount_precision)
            
            # Se quantidade arredondada for menor que o mínimo, arredondar para cima
            if min_amount and amount_coins < min_amount:
                # Calcular próximo valor válido acima do mínimo
                import math
                step = 10 ** (-amount_precision)
                amount_coins = math.ceil(min_amount / step) * step
                logger.warning(f"⚠️ Quantidade ajustada para mínimo da corretora: {amount_coins:.{amount_precision}f}")
            
            side = 'sell' if self.alvo_dados['direcao'] == 'SHORT' else 'buy'
            
            params = {
                'stopLoss': str(self.alvo_dados['stop_loss']),
                'takeProfit': str(self.alvo_dados['target'])
            }

            order = self.exchange.create_order(self.target_symbol_final, 'market', side, amount_coins, params=params)
            logger.info(f"✅ Ordem executada: {order['id']}")
            
            self.registrar_entrada(price, amount_coins, usdt_total * RISK_PER_TRADE)
            self.remover_da_watchlist("Trade Executado")
            
            return order, side, price
            
        except Exception as e:
            logger.error(f"ERRO CRITICO EXECUÇÃO: {e}")
            self.remover_da_watchlist("Erro de execução")
            sys.exit(1)

    def registrar_entrada(self, entry_price, size, risco):
        try:
            history_file = os.path.join(BASE_DIR, 'trades_history.json')
            history = []
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    try: history = json.load(f)
                    except: pass
            
            history.append({
                "symbol": self.symbol,
                "side": self.alvo_dados['direcao'],
                "entry_price": entry_price,
                "size": size,
                "risco_estimado": risco,
                "opened_at": str(datetime.now()),
                "status": "OPEN"
            })
            with open(history_file, 'w') as f: json.dump(history[-50:], f, indent=2)
        except: pass

    def monitorar_trailing_stop(self, side, entry_price):
        """
        FASE 4: Break-Even e Trailing Stop
        """
        logger.info("🛡️ Iniciando Monitoramento Ativo (Trailing/BE)...")
        
        target_price = self.alvo_dados['target']
        stop_price = self.alvo_dados['stop_loss']
        
        # Definições (Exemplo: BE ao atingir 50% do alvo)
        distancia_alvo = abs(target_price - entry_price)
        trigger_be = entry_price + (distancia_alvo * 0.5) if side == 'buy' else entry_price - (distancia_alvo * 0.5)
        
        be_acionado = False
        
        while True:
            try:
                time.sleep(15)
                
                # Verifica se posição ainda existe
                positions = self.exchange.fetch_positions([self.target_symbol_final])
                open_pos = [p for p in positions if float(p['contracts']) > 0]
                if not open_pos:
                    logger.info("✅ Posição encerrada pela corretora.")
                    break
                
                pos = open_pos[0]
                mark_price = float(pos['markPrice'] or pos['lastPrice']) # Bybit usa markPrice para liquidar
                
                # --- LOGICA BREAK-EVEN ---
                if not be_acionado:
                    acionar_be = False
                    if side == 'buy' and mark_price >= trigger_be: acionar_be = True
                    elif side == 'sell' and mark_price <= trigger_be: acionar_be = True
                    
                    if acionar_be:
                        logger.info(f"🛡️ PROTEÇÃO: Movendo Stop para Break-Even ({entry_price})")
                        
                        # Atualiza SL na Bybit
                        new_sl = entry_price * 1.002 if side == 'buy' else entry_price * 0.998 # Pequeno lucro para cobrir taxas
                        
                        try:
                            # Bybit V5: set_trading_stop
                            self.exchange.set_trading_stop(
                                symbol=self.target_symbol_final,
                                side=side,
                                stop_loss=new_sl,
                                params={'positionIdx': 0} # 0 para One-Way Mode
                            )
                            be_acionado = True
                            logger.info("✅ Break-Even Configurado!")
                        except Exception as e:
                            logger.error(f"Falha ao mover BE: {e}")

                # --- LOGICA TRAILING (Opcional Futuro: Mover SL a cada X%) ---
                # Por enquanto, BE é a prioridade da Fase 4.

            except Exception as e:
                logger.error(f"Erro no monitoramento: {e}")
                time.sleep(30)

    def run(self):
        self.setup_futures_mode()
        order, side, price = self.executar_trade()
        self.monitorar_trailing_stop(side, price)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', required=True)
    args = parser.parse_args()
    
    bot = ExecutorBybit(args.symbol)
    bot.run()

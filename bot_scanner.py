import json
import time
import os
import sys
import logging
import ccxt
from datetime import datetime
from lib_padroes import AnalistaTecnico
from lib_utils import JsonManager, check_btc_trend, get_market_analysis, should_trade_in_scenario

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scanner_bybit.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("ScannerBybit")

class ScannerBybit:
    def __init__(self):
        self.config = self.carregar_json('config_futures.json')
        self.watchlist_mgr = JsonManager('watchlist.json') # Phase 1: Lock Manager
        self.analista = AnalistaTecnico()

        # Conexão Bybit (Publica para Scan)
        self.exchange = ccxt.bybit({
            'enableRateLimit': True,
            'options': {'defaultType': 'linear'} # Futures Linear
        })
        self.running = True

    def carregar_json(self, arquivo):
        try:
            with open(arquivo, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Erro ao ler {arquivo}: {e}")
            return {}

    def verificar_slots_livres(self):
        wl = self.watchlist_mgr.read()
        if not wl or 'max_slots' not in wl:
            # Inicializa se vazio ou corrompido
            default_wl = {'max_slots': 10, 'slots_ocupados': 0, 'pares': []}
            return 10, default_wl

        # Limpeza de slots fantasmas (Phase 1 Fix)
        wl['slots_ocupados'] = len(wl['pares'])
        
        livres = wl['max_slots'] - wl['slots_ocupados']
        return livres, wl

    def validar_volume(self, candles):
        """Phase 2: Filtro de Volume"""
        try:
            volumes = [c[5] for c in candles]
            if len(volumes) < 21: return False
            
            vol_atual = volumes[-1]
            media_vol = sum(volumes[-21:-1]) / 20
            
            # Volume atual deve ser pelo menos 1.2x a media para confirmar interesse
            return vol_atual > (media_vol * 1.2)
        except:
            return False

    def scan(self):
        logger.info(">>> Iniciando Ciclo de Scan (30 Pares x Multi-TF) <<<")
        
        # SEVERINO: Análise Completa de Mercado (BTC + BTC.D + Cenário)
        market = get_market_analysis(self.exchange, timeframe='4h')
        logger.info(f"📊 Mercado: BTC={market['btc_trend']} | BTC.D={market['btcd_trend']} | Cenário #{market['scenario_number']}: {market['scenario_name']}")
        logger.info(f"   {market['scenario_description']}")

        livres, watchlist_data = self.verificar_slots_livres()
        if livres <= 0:
            logger.info("Watchlist cheia (5/5). Scanner em modo de espera.")
            time.sleep(60)
            return

        pares_ignorados = [item['symbol'] for item in watchlist_data['pares']]
        tfs = self.config.get('timeframes', ['30m'])

        for par in self.config['pairs']:
            if not self.running: break
            if par in pares_ignorados: continue

            for tf in tfs:
                # Re-verifica slots a cada iteração para evitar Race Condition lógica
                livres, wl_now = self.verificar_slots_livres()
                if livres <= 0: break

                try:
                    # Baixar Candles
                    candles = self.exchange.fetch_ohlcv(par, timeframe=tf, limit=200)
                    
                    # Phase 2: Filtro de Volume (Pré-análise)
                    if not self.validar_volume(candles):
                        # Se não tem volume, nem perde tempo processando padrão
                        continue

                    padrao = self.analista.analisar_par(par, candles)
                    
                    if padrao:
                        # SEVERINO: Filtro de Correlação BTC/BTC.D/Cenário
                        should_trade, reason = should_trade_in_scenario(
                            market['scenario_number'], 
                            padrao.direcao
                        )
                        
                        if not should_trade:
                            logger.info(f"❌ Ignorando {padrao.nome} {padrao.direcao} em {par}: {reason}")
                            continue

                        logger.info(f"🚨 PADRAO CONFIRMADO EM {par} [{tf}]: {padrao.nome} ({padrao.direcao})")
                        
                        novo_item = {
                            "symbol": par,
                            "timeframe": tf,
                            "padrao": padrao.nome,
                            "direcao": padrao.direcao,
                            "status": "EM_FORMACAO",
                            "confiabilidade": padrao.confiabilidade,
                            "neckline": padrao.neckline_price,
                            "target": padrao.target_price,
                            "stop_loss": padrao.stop_loss_price,
                            "timestamp_descoberta": int(time.time())
                        }
                        
                        # Adiciona com Lock Seguro (Phase 1)
                        livres_final, wl_final = self.verificar_slots_livres()
                        if livres_final > 0:
                            wl_final['pares'].append(novo_item)
                            wl_final['slots_ocupados'] = len(wl_final['pares'])
                            wl_final['updated_at'] = str(datetime.now())
                            self.watchlist_mgr.write(wl_final)
                            logger.info(f"Adicionado {par} a Watchlist.")
                            pares_ignorados.append(par)
                            break
                        
                    time.sleep(0.5) # Rate limit

                except Exception as e:
                    logger.error(f"Erro ao processar {par} {tf}: {e}")
                    time.sleep(2)

        logger.info("Ciclo de scan finalizado. Aguardando proximo.")
        time.sleep(30)

    def start(self):
        logger.info("Scanner Bybit Iniciado (v2.0 - Secure & Smart).")
        while self.running:
            try:
                self.scan()
            except KeyboardInterrupt:
                logger.info("Parando...")
                self.running = False
            except Exception as e:
                logger.error(f"Erro fatal no loop: {e}")
                time.sleep(10)

def start_scanner():
    bot = ScannerBybit()
    bot.start()

if __name__ == "__main__":
    start_scanner()

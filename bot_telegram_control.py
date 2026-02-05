import time
import json
import os
import sys
import logging
import requests
import subprocess
import ccxt
from datetime import datetime
from lib_utils import JsonManager

# --- CONFIGURAÇÃO ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "telegram_control.log")
WATCHLIST_FILE = os.path.join(BASE_DIR, 'watchlist.json')

# Tenta carregar token do bot_telegram original ou env
sys.path.insert(0, BASE_DIR)
TOKEN = None
CHAT_ID = None

try:
    from bot_telegram import TOKEN as T, CHAT_ID as C
    TOKEN = T
    CHAT_ID = str(C)
except:
    # Fallback para .env
    pass

if not TOKEN or not CHAT_ID:
    # Tenta ler do .env manual
    try:
        with open(os.path.join(BASE_DIR, '.env'), 'r') as f:
            for line in f:
                if 'TELEGRAM_TOKEN' in line: TOKEN = line.split('=')[1].strip()
                if 'TELEGRAM_CHAT_ID' in line: CHAT_ID = line.split('=')[1].strip()
    except: pass

if not TOKEN:
    print("ERRO: Token do Telegram não encontrado.")
    sys.exit(1)

# Configuração de Logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("TgmControl")
watchlist_mgr = JsonManager(WATCHLIST_FILE)

class TelegramBot:
    def __init__(self, token, admin_id):
        self.token = token
        self.admin_id = str(admin_id)
        self.base_url = f"https://api.telegram.org/bot{token}/"
        self.offset = 0
        self.config = self.carregar_json('config_futures.json')
        
    def carregar_json(self, arquivo):
        try:
            with open(os.path.join(BASE_DIR, arquivo), 'r') as f: return json.load(f)
        except: return {}

    def send_message(self, text):
        try:
            url = self.base_url + "sendMessage"
            data = {"chat_id": self.admin_id, "text": text, "parse_mode": "Markdown"}
            requests.post(url, data=data, timeout=10)
        except Exception as e:
            logger.error(f"Erro ao enviar msg: {e}")

    def get_updates(self):
        try:
            url = self.base_url + "getUpdates"
            params = {"offset": self.offset, "timeout": 30}
            resp = requests.get(url, params=params, timeout=40)
            if resp.status_code == 200:
                result = resp.json().get("result", [])
                if result:
                    self.offset = result[-1]["update_id"] + 1
                    return result
            return []
        except Exception as e:
            logger.error(f"Erro no polling: {e}")
            time.sleep(5)
            return []

    def cmd_status(self):
        try:
            # Roda o comando status do manager e captura output
            result = subprocess.run(
                [sys.executable, os.path.join(BASE_DIR, "bot_manager.py"), "status"],
                capture_output=True, text=True
            )
            # Limpa e formata
            output = result.stdout.replace("==================================================", "")
            output = output.strip()
            return f"📊 *STATUS DO SISTEMA*\n```\n{output}\n```"
        except Exception as e:
            return f"Erro ao obter status: {e}"

    def cmd_watchlist(self):
        try:
            wl = watchlist_mgr.read()
            if not wl or not wl.get('pares'):
                return "📭 *Watchlist Vazia*"
            
            msg = f"📋 *WATCHLIST ({wl['slots_ocupados']}/{wl['max_slots']})*\n\n"
            for p in wl['pares']:
                msg += f"🔹 *{p['symbol']}* ({p['direcao']})\n"
                msg += f"   Padrão: {p['padrao']} [{p['timeframe']}]\n"
                msg += f"   Status: {p.get('status', 'N/A')}\n"
                msg += f"   Gatilho: `{p['neckline']}`\n\n"
            return msg
        except Exception as e:
            return f"Erro ao ler watchlist: {e}"

    def cmd_saldo(self):
        try:
            # Carrega segredos (JSON ou ENV)
            secrets = {}
            try:
                # Tenta JSON primeiro
                path_json = os.path.join(BASE_DIR, 'segredos.json')
                if os.path.exists(path_json):
                    with open(path_json, 'r') as f: secrets = json.load(f)
                
                # Tenta ENV depois (complementa/sobrescreve)
                path_env = os.path.join(BASE_DIR, '.env')
                if os.path.exists(path_env):
                    with open(path_env, 'r') as f:
                        for line in f:
                            if '=' in line and not line.startswith('#'):
                                key, val = line.strip().split('=', 1)
                                secrets[key] = val
            except: pass
            
            if not secrets.get('BYBIT_API_KEY'):
                return "❌ Erro: API Key não encontrada no .env ou segredos.json"

            exchange = ccxt.bybit({
                'apiKey': secrets.get('BYBIT_API_KEY'), 
                'secret': secrets.get('BYBIT_SECRET'),
                'options': {'defaultType': 'linear'}
            })
            
            bal = exchange.fetch_balance()
            usdt = bal['USDT']
            
            msg = "💰 *SALDO BYBIT (Futures)*\n"
            msg += f"Total Equity: `${usdt['total']:.2f}`\n"
            msg += f"Livre: `${usdt['free']:.2f}`\n"
            msg += f"Em uso: `${usdt['used']:.2f}`"
            return msg
        except Exception as e:
            return f"Erro ao conectar Bybit: {e}"

    def cmd_restart(self):
        self.send_message("⚠️ *Reiniciando Sistema...*")
        subprocess.Popen([sys.executable, os.path.join(BASE_DIR, "bot_manager.py"), "restart"])
        return "Comando de restart enviado."

    def process_command(self, cmd):
        cmd = cmd.lower().strip()
        logger.info(f"Comando recebido: {cmd}")
        
        if cmd == "/start" or cmd == "/help":
            msg = "🦅 *COMANDOS SEVERINO*\n\n"
            msg += "/status - Saúde do sistema\n"
            msg += "/wl - Ver Watchlist\n"
            msg += "/saldo - Saldo Bybit\n"
            msg += "/restart - Reiniciar Bot"
            self.send_message(msg)
            
        elif cmd == "/status":
            self.send_message(self.cmd_status())
            
        elif cmd == "/wl":
            self.send_message(self.cmd_watchlist())
            
        elif cmd == "/saldo":
            self.send_message(self.cmd_saldo())
            
        elif cmd == "/restart":
            self.send_message(self.cmd_restart())
            
        else:
            self.send_message("Comando desconhecido. Use /help")

    def run(self):
        logger.info("Telegram Control Iniciado")
        self.send_message("🦅 *SEVERINO ONLINE*\nCentro de Comando Ativo.\nDigite /help para opções.")
        
        while True:
            updates = self.get_updates()
            for update in updates:
                if "message" in update:
                    msg = update["message"]
                    # Segurança: Só responde ao Admin ID configurado
                    if str(msg.get("chat", {}).get("id")) == self.admin_id:
                        text = msg.get("text", "")
                        if text.startswith("/"):
                            self.process_command(text)
            time.sleep(1)

if __name__ == "__main__":
    bot = TelegramBot(TOKEN, CHAT_ID)
    bot.run()

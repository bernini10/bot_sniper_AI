import telebot
from telebot import types
import json
import time
import os
import sys
import threading
import ccxt
from datetime import datetime

# --- CONFIGURAÇÃO ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_FILE = os.path.join(BASE_DIR, 'watchlist.json')
EXECUTOR_SCRIPT = os.path.join(BASE_DIR, 'bot_executor.py')
MODE_FILE = os.path.join(BASE_DIR, 'config_mode.json')

# Carregar Segredos
secrets = {}
try:
    env_path = os.path.join(BASE_DIR, '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, val = line.strip().split('=', 1)
                    secrets[key] = val
    
    if 'TELEGRAM_TOKEN' not in secrets:
        json_path = os.path.join(BASE_DIR, 'segredos.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f: secrets.update(json.load(f))

    TOKEN = secrets.get('TELEGRAM_TOKEN') or secrets.get('telegram_token')
    CHAT_ID = secrets.get('TELEGRAM_CHAT_ID') or secrets.get('chat_id')
    
    if not TOKEN:
        raise ValueError("Token do Telegram nao encontrado!")

except Exception as e:
    print(f"Erro critico na configuracao: {e}")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)

# --- FUNÇÕES DE MODO ---
def get_mode():
    try:
        if os.path.exists(MODE_FILE):
            with open(MODE_FILE, 'r') as f:
                return json.load(f).get('mode', 'AUTO')
    except: pass
    return 'AUTO'  # Default AUTO para testes

def set_mode(mode):
    try:
        with open(MODE_FILE, 'w') as f:
            json.dump({'mode': mode, 'updated_at': str(datetime.now())}, f)
        return True
    except: return False

def carregar_json(arquivo):
    try:
        with open(arquivo, 'r') as f: return json.load(f)
    except: return {}

def get_bybit_balance():
    try:
        exchange = ccxt.bybit({
            'apiKey': secrets.get('BYBIT_API_KEY'),
            'secret': secrets.get('BYBIT_SECRET'),
            'options': {'defaultType': 'linear'}
        })
        bal = exchange.fetch_balance()
        return bal['USDT']['free'], bal['USDT']['total']
    except Exception as e:
        return None, str(e)

def lancar_executor(symbol):
    """Lança o executor em background"""
    cmd = f"nohup python3 {EXECUTOR_SCRIPT} --symbol \"{symbol}\" > {BASE_DIR}/executor_{symbol.replace('/','')}.log 2>&1 &"
    os.system(cmd)
    print(f"Executor lançado para {symbol}")

# --- MONITOR DE SINAIS ---
def monitor_watchlist():
    last_processed = set()
    print(">>> Monitor de Sinais Iniciado <<<")
    
    while True:
        try:
            if os.path.exists(WATCHLIST_FILE):
                dados = carregar_json(WATCHLIST_FILE)
                current_mode = get_mode()
                
                for par in dados.get('pares', []):
                    key = f"{par['symbol']}_{par['timestamp_descoberta']}"
                    
                    if key not in last_processed and par['status'] == 'EM_FORMACAO':
                        direcao_emoji = "🔻 SHORT" if par['direcao'] == 'SHORT' else "🔼 LONG"
                        
                        if current_mode == 'AUTO':
                            # MODO AUTOMÁTICO: Executa direto!
                            msg = (
                                f"🤖 *AUTO MODE - EXECUTANDO*\n"
                                f"━━━━━━━━━━━━━━━━━━\n"
                                f"🎯 *{par['symbol']}* {direcao_emoji}\n"
                                f"📊 Padrão: {par['padrao']}\n"
                                f"⚡ Confiança: {par['confiabilidade']*100:.0f}%\n\n"
                                f"💵 Gatilho: `${par['neckline']}`\n"
                                f"🎯 Alvo: `${par['target']}`\n"
                                f"🛑 Stop: `${par['stop_loss']}`\n\n"
                                f"_Executor despachado automaticamente!_"
                            )
                            try:
                                bot.send_message(CHAT_ID, msg, parse_mode='Markdown')
                            except: pass
                            
                            # Lança executor imediatamente
                            lancar_executor(par['symbol'])
                            last_processed.add(key)
                            
                        else:
                            # MODO MANUAL: Pede aprovação
                            msg = (
                                f"🎯 *SNIPER ALERT: {par['symbol']}*\n"
                                f"━━━━━━━━━━━━━━━━━━\n"
                                f"📊 *Padrão:* {par['padrao']}\n"
                                f"🧭 *Direção:* {direcao_emoji}\n"
                                f"⚡ *Confiança:* {par['confiabilidade']*100:.0f}%\n\n"
                                f"💵 *Gatilho:* `${par['neckline']}`\n"
                                f"🎯 *Alvo:* `${par['target']}`\n"
                                f"🛑 *Stop:* `${par['stop_loss']}`\n\n"
                                f"_Aguardando autorização..._"
                            )
                            
                            markup = types.InlineKeyboardMarkup()
                            btn_approve = types.InlineKeyboardButton(f"✅ APROVAR", callback_data=f"aprov_{par['symbol']}")
                            btn_ignore = types.InlineKeyboardButton("❌ IGNORAR", callback_data=f"ignora_{par['symbol']}")
                            markup.row(btn_approve, btn_ignore)
                            
                            try:
                                bot.send_message(CHAT_ID, msg, parse_mode='Markdown', reply_markup=markup)
                                last_processed.add(key)
                            except Exception as e:
                                print(f"Erro ao enviar msg: {e}")

        except Exception as e:
            print(f"Erro no monitor: {e}")
        
        time.sleep(10)

# --- HANDLERS TELEGRAM ---

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if str(message.chat.id) != str(CHAT_ID): return
    mode = get_mode()
    msg = (
        f"🤖 *BYBIT SNIPER COMMANDER*\n\n"
        f"Modo atual: *{mode}*\n\n"
        f"Comandos:\n"
        f"/status - Saldo e sistema\n"
        f"/modo - Alternar AUTO/MANUAL\n"
        f"/auto - Ativar modo automático\n"
        f"/manual - Ativar modo manual\n"
        f"/limpar - Limpar watchlist\n"
    )
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def send_status(message):
    if str(message.chat.id) != str(CHAT_ID): return
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    scanner_on = os.system("pgrep -f bot_scanner.py > /dev/null 2>&1") == 0
    executor_on = os.system("pgrep -f bot_executor.py > /dev/null 2>&1") == 0
    mode = get_mode()
    
    status_msg = f"📡 *STATUS DO SISTEMA*\n━━━━━━━━━━━━━━━━━━\n"
    status_msg += f"🎛️ *Modo:* {mode}\n"
    status_msg += f"👁️ *Scanner:* {'🟢 Online' if scanner_on else '🔴 Offline'}\n"
    status_msg += f"⚔️ *Executor:* {'🟡 Operando' if executor_on else '⚪ Aguardando'}\n\n"
    
    free, total = get_bybit_balance()
    if free is not None:
        status_msg += f"💰 *Saldo Futures (USDT):*\n"
        status_msg += f"   Livre: `{free:.2f}`\n"
        status_msg += f"   Total: `{total:.2f}`\n"
    else:
        status_msg += f"⚠️ *Erro Bybit:* {total}\n"
    
    # Watchlist
    wl = carregar_json(WATCHLIST_FILE)
    slots = wl.get('slots_ocupados', 0)
    max_slots = wl.get('max_slots', 5)
    status_msg += f"\n📋 *Watchlist:* {slots}/{max_slots} slots"
        
    bot.reply_to(message, status_msg, parse_mode='Markdown')

@bot.message_handler(commands=['modo'])
def toggle_mode(message):
    if str(message.chat.id) != str(CHAT_ID): return
    
    current = get_mode()
    
    markup = types.InlineKeyboardMarkup()
    btn_auto = types.InlineKeyboardButton(
        f"{'✅' if current == 'AUTO' else '⚪'} AUTOMÁTICO", 
        callback_data="setmode_AUTO"
    )
    btn_manual = types.InlineKeyboardButton(
        f"{'✅' if current == 'MANUAL' else '⚪'} MANUAL", 
        callback_data="setmode_MANUAL"
    )
    markup.row(btn_auto, btn_manual)
    
    msg = (
        f"🎛️ *MODO DE OPERAÇÃO*\n\n"
        f"Atual: *{current}*\n\n"
        f"🤖 *AUTO* - Executa trades automaticamente\n"
        f"👤 *MANUAL* - Pede aprovação no Telegram"
    )
    bot.reply_to(message, msg, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(commands=['auto'])
def set_auto(message):
    if str(message.chat.id) != str(CHAT_ID): return
    set_mode('AUTO')
    bot.reply_to(message, "🤖 *Modo AUTOMÁTICO ativado!*\n\nTrades serão executados automaticamente.", parse_mode='Markdown')

@bot.message_handler(commands=['manual'])
def set_manual(message):
    if str(message.chat.id) != str(CHAT_ID): return
    set_mode('MANUAL')
    bot.reply_to(message, "👤 *Modo MANUAL ativado!*\n\nVocê precisará aprovar cada trade.", parse_mode='Markdown')

@bot.message_handler(commands=['limpar'])
def limpar_watchlist(message):
    if str(message.chat.id) != str(CHAT_ID): return
    try:
        with open(WATCHLIST_FILE, 'w') as f:
            json.dump({"slots_ocupados": 0, "max_slots": 10, "pares": []}, f)
        bot.reply_to(message, "🗑️ Watchlist limpa!", parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, f"Erro: {e}")

# --- MONITOR ---
import threading
import subprocess

monitor_process = None
monitor_thread = None

def start_monitor():
    global monitor_process
    if monitor_process is not None:
        return False
    cmd = f"cd {BASE_DIR} && nohup python3 bot_monitor.py > monitor_bybit.log 2>&1 &"
    os.system(cmd)
    monitor_process = True
    return True

def stop_monitor():
    global monitor_process
    if monitor_process is None:
        return False
    os.system("pkill -f bot_monitor.py")
    monitor_process = None
    return True

@bot.message_handler(commands=['monitor'])
def monitor_cmd(message):
    if str(message.chat.id) != str(CHAT_ID): return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "Uso: /monitor <start|stop>", parse_mode='Markdown')
        return
    cmd = args[1].lower()
    if cmd == 'start':
        if start_monitor():
            bot.reply_to(message, "✅ Monitor iniciado.", parse_mode='Markdown')
        else:
            bot.reply_to(message, "⚠️ Monitor já está rodando.", parse_mode='Markdown')
    elif cmd == 'stop':
        if stop_monitor():
            bot.reply_to(message, "🛑 Monitor parado.", parse_mode='Markdown')
        else:
            bot.reply_to(message, "⚠️ Monitor não estava rodando.", parse_mode='Markdown')
    else:
        bot.reply_to(message, "Uso: /monitor <start|stop>", parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('setmode_'))
def callback_setmode(call):
    mode = call.data.split('_')[1]
    set_mode(mode)
    bot.answer_callback_query(call.id, f"Modo {mode} ativado!")
    bot.edit_message_text(
        f"✅ *Modo alterado para {mode}*",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith('aprov_'))
def callback_aprovar(call):
    symbol = call.data.split('_')[1]
    bot.answer_callback_query(call.id, f"Iniciando {symbol}...")
    bot.edit_message_text(
        f"✅ *APROVADO: {symbol}*\nExecutor despachado!",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )
    lancar_executor(symbol)

@bot.callback_query_handler(func=lambda call: call.data.startswith('ignora_'))
def callback_ignorar(call):
    symbol = call.data.split('_')[1]
    bot.answer_callback_query(call.id, "Descartado.")
    bot.edit_message_text(
        f"❌ *IGNORADO: {symbol}*",
        call.message.chat.id,
        call.message.message_id,
        parse_mode='Markdown'
    )

# --- INICIALIZAÇÃO ---
if __name__ == "__main__":
    # Garante modo AUTO por default para testes
    if not os.path.exists(MODE_FILE):
        set_mode('AUTO')
    
    t = threading.Thread(target=monitor_watchlist)
    t.daemon = True
    t.start()
    
    print(f"🤖 Bot Telegram Iniciado (Modo: {get_mode()})")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Erro fatal: {e}")
        time.sleep(10)

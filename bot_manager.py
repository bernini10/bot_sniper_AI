#!/usr/bin/env python3
"""
Gerenciador Central do Bot Sniper Bybit
Controla scanner, monitor e executores em conjunto
"""

import subprocess
import sys
import time
import os
import signal
import psutil
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "manager.log")

def log(message):
    """Registra logs no arquivo manager.log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {message}"
    print(log_msg)
    with open(LOG_FILE, "a") as f:
        f.write(log_msg + "\n")

def get_process_by_name(name):
    """Encontra processos pelo nome"""
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if name in ' '.join(proc.info['cmdline'] or []):
                procs.append(proc.info['pid'])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return procs

def kill_process_by_name(name):
    """Mata processos pelo nome"""
    pids = get_process_by_name(name)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            log(f"Processo {pid} ({name}) terminado")
        except ProcessLookupError:
            pass
    time.sleep(1)
    # Force kill se ainda existir
    pids = get_process_by_name(name)
    for pid in pids:
        try:
            os.kill(pid, signal.SIGKILL)
            log(f"Processo {pid} ({name}) forçado a terminar")
        except ProcessLookupError:
            pass

def start_scanner():
    """Inicia o scanner em background"""
    log("Iniciando scanner...")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, "bot_scanner.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=BASE_DIR
    )
    log(f"Scanner iniciado (PID: {proc.pid})")
    return proc

def start_monitor():
    """Inicia o monitor em background"""
    log("Iniciando monitor...")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, "bot_monitor.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=BASE_DIR
    )
    log(f"Monitor iniciado (PID: {proc.pid})")
    return proc

def start_telegram_control():
    """Inicia o controle via Telegram"""
    log("Iniciando Telegram Control...")
    proc = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, "bot_telegram_control.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=BASE_DIR
    )
    log(f"Telegram Control iniciado (PID: {proc.pid})")
    return proc

def start_all():
    """Inicia todos os componentes"""
    log("=" * 50)
    log("INICIANDO BOT SNIPER BYBIT")
    log("=" * 50)
    
    # Mata processos existentes
    kill_process_by_name("bot_scanner.py")
    kill_process_by_name("bot_monitor.py")
    kill_process_by_name("bot_executor.py")
    kill_process_by_name("bot_telegram_control.py")
    time.sleep(2)
    
    # Inicia componentes
    scanner_proc = start_scanner()
    monitor_proc = start_monitor()
    telegram_proc = start_telegram_control()
    
    log("Todos os componentes iniciados")
    log("Scanner: Monitorando e populando watchlist")
    log("Monitor: Validando padrões e disparando executores")
    log("Telegram: Centro de Comando Online")
    log("=" * 50)
    
    return scanner_proc, monitor_proc, telegram_proc

def stop_all():
    """Para todos os componentes"""
    log("=" * 50)
    log("PARANDO BOT SNIPER BYBIT")
    log("=" * 50)
    
    kill_process_by_name("bot_scanner.py")
    kill_process_by_name("bot_monitor.py")
    kill_process_by_name("bot_executor.py")
    kill_process_by_name("bot_telegram_control.py")
    
    log("Todos os componentes parados")
    log("=" * 50)

def status():
    """Verifica status dos componentes"""
    scanner_pids = get_process_by_name("bot_scanner.py")
    monitor_pids = get_process_by_name("bot_monitor.py")
    executor_pids = get_process_by_name("bot_executor.py")
    telegram_pids = get_process_by_name("bot_telegram_control.py")
    
    log("=" * 50)
    log("STATUS DO BOT SNIPER BYBIT")
    log("=" * 50)
    log(f"Scanner: {'ATIVO' if scanner_pids else 'PARADO'} (PIDs: {scanner_pids})")
    log(f"Monitor: {'ATIVO' if monitor_pids else 'PARADO'} (PIDs: {monitor_pids})")
    log(f"Telegram: {'ATIVO' if telegram_pids else 'PARADO'} (PIDs: {telegram_pids})")
    log(f"Executores: {'ATIVOS' if executor_pids else 'PARADOS'} (Qtd: {len(executor_pids)})")
    
    # Verifica watchlist
    try:
        import json
        with open(os.path.join(BASE_DIR, "watchlist.json"), "r") as f:
            wl = json.load(f)
        log(f"Watchlist: {wl['slots_ocupados']}/{wl['max_slots']} slots ocupados")
    except:
        log("Watchlist: Não foi possível ler")
    
    log("=" * 50)

def main():
    if len(sys.argv) < 2:
        print("Uso: python bot_manager.py [start|stop|status|restart]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "start":
        start_all()
    elif command == "stop":
        stop_all()
    elif command == "restart":
        stop_all()
        time.sleep(2)
        start_all()
    elif command == "status":
        status()
    else:
        print(f"Comando desconhecido: {command}")
        print("Uso: python bot_manager.py [start|stop|status|restart]")
        sys.exit(1)

if __name__ == "__main__":
    main()

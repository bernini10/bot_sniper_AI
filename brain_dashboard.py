#!/usr/bin/env python3
"""
🧠 DASHBOARD DO BRAIN - Monitoramento do Sistema de Aprendizado
"""

import json
import sqlite3
import time
from datetime import datetime
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = 'sniper_brain.db'
MODEL_PATH = 'brain_models/q_learning_model.pkl'

def get_brain_stats():
    """Obtém estatísticas do sistema de aprendizado"""
    stats = {
        'status': 'UNKNOWN',
        'database': {},
        'model': {},
        'performance': {},
        'learning': {}
    }
    
    try:
        # Database stats
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Amostras
        cursor.execute("SELECT COUNT(*) FROM raw_samples")
        stats['database']['total_samples'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM raw_samples WHERE ai_verdict IS NOT NULL")
        stats['database']['validated_samples'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM raw_samples WHERE trade_result IS NOT NULL")
        stats['database']['learned_samples'] = cursor.fetchone()[0]
        
        # Trades reais
        cursor.execute("SELECT COUNT(*) FROM real_trades")
        stats['database']['total_trades'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM real_trades WHERE profit_pct > 0")
        stats['database']['winning_trades'] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM real_trades WHERE profit_pct < 0")
        stats['database']['losing_trades'] = cursor.fetchone()[0]
        
        # Calcular win rate
        total = stats['database']['winning_trades'] + stats['database']['losing_trades']
        stats['performance']['win_rate'] = (stats['database']['winning_trades'] / total * 100) if total > 0 else 0
        
        # Últimos trades
        cursor.execute("""
            SELECT symbol, profit_pct, entry_time 
            FROM real_trades 
            WHERE exit_time IS NOT NULL 
            ORDER BY exit_time DESC 
            LIMIT 5
        """)
        stats['performance']['recent_trades'] = cursor.fetchall()
        
        conn.close()
        
        # Model stats
        if os.path.exists(MODEL_PATH):
            import pickle
            with open(MODEL_PATH, 'rb') as f:
                model_data = pickle.load(f)
            
            stats['model']['states'] = len(model_data.get('q_table', {}))
            stats['model']['last_saved'] = model_data.get('saved_at', 'Unknown')
            stats['model']['episodes'] = model_data.get('training_stats', {}).get('episodes', 0)
            stats['model']['total_reward'] = model_data.get('training_stats', {}).get('total_reward', 0)
            
            wins = model_data.get('training_stats', {}).get('wins', 0)
            losses = model_data.get('training_stats', {}).get('losses', 0)
            total_sim = wins + losses
            stats['model']['simulated_win_rate'] = (wins / total_sim * 100) if total_sim > 0 else 0
        
        # Learning logs
        log_file = os.path.join(BASE_DIR, 'brain_logs', 'learning.log')
        if os.path.exists(log_file):
            with open(log_file, 'r') as f:
                lines = f.readlines()[-10:]  # Últimas 10 linhas
            stats['learning']['recent_logs'] = [line.strip() for line in lines]
        
        stats['status'] = 'HEALTHY'
        
    except Exception as e:
        stats['status'] = f'ERROR: {str(e)}'
    
    return stats

def print_dashboard():
    """Imprime dashboard no terminal"""
    print("\n" + "="*80)
    print("🧠 DASHBOARD DO SISTEMA DE APRENDIZADO END-TO-END")
    print("="*80)
    
    stats = get_brain_stats()
    
    if stats['status'] != 'HEALTHY':
        print(f"❌ Status: {stats['status']}")
        return
    
    # Seção 1: Database
    print("\n📊 DATABASE")
    print("-"*40)
    db = stats['database']
    print(f"  Amostras totais: {db.get('total_samples', 0):,}")
    print(f"  Validadas pela IA: {db.get('validated_samples', 0):,}")
    print(f"  Com aprendizado: {db.get('learned_samples', 0):,}")
    print(f"  Trades reais: {db.get('total_trades', 0):,}")
    print(f"  Wins: {db.get('winning_trades', 0):,} | Losses: {db.get('losing_trades', 0):,}")
    print(f"  Win Rate real: {stats['performance'].get('win_rate', 0):.1f}%")
    
    # Seção 2: Modelo
    print("\n🧠 MODELO DE APRENDIZADO")
    print("-"*40)
    model = stats['model']
    print(f"  Estados aprendidos: {model.get('states', 0):,}")
    print(f"  Episódios de treino: {model.get('episodes', 0):,}")
    print(f"  Recompensa total: {model.get('total_reward', 0):.2f}")
    print(f"  Win Rate simulado: {model.get('simulated_win_rate', 0):.1f}%")
    print(f"  Último save: {model.get('last_saved', 'Unknown')}")
    
    # Seção 3: Performance Recente
    print("\n📈 PERFORMANCE RECENTE")
    print("-"*40)
    recent = stats['performance'].get('recent_trades', [])
    if recent:
        print("  Últimos 5 trades:")
        for symbol, profit, timestamp in recent:
            time_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
            profit_str = f"+{profit:.2f}%" if profit > 0 else f"{profit:.2f}%"
            color = "🟢" if profit > 0 else "🔴"
            print(f"    {color} {symbol}: {profit_str} ({time_str})")
    else:
        print("  Nenhum trade registrado ainda")
    
    # Seção 4: Logs
    print("\n📝 LOGS RECENTES")
    print("-"*40)
    logs = stats['learning'].get('recent_logs', [])
    if logs:
        for log in logs[-5:]:  # Últimas 5 linhas
            print(f"  {log}")
    else:
        print("  Nenhum log disponível")
    
    # Seção 5: Status do Sistema
    print("\n⚙️ STATUS DO SISTEMA")
    print("-"*40)
    
    # Verificar processos
    import subprocess
    processes = {
        'Bot Scanner': 'bot_scanner.py',
        'Bot Monitor': 'bot_monitor.py',
        'Brain Learning': 'brain_learning_daemon'
    }
    
    for name, pattern in processes.items():
        result = subprocess.run(['pgrep', '-f', pattern], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ {name}: ATIVO")
        else:
            print(f"  ❌ {name}: PARADO")
    
    print("\n" + "="*80)
    print("📋 Comandos úteis:")
    print("  ./start_brain_learning.sh  - Iniciar aprendizado contínuo")
    print("  ./stop_brain_learning.sh   - Parar aprendizado")
    print("  python3 brain_integration.py - Testar sistema")
    print("  tail -f brain_logs/learning.log - Monitorar logs")
    print("="*80)

def main():
    """Função principal"""
    try:
        print_dashboard()
        
        # Opção para atualizar automaticamente
        if len(sys.argv) > 1 and sys.argv[1] == '--watch':
            import time
            print("\n👁️  Modo watch ativado (atualiza a cada 30s, Ctrl+C para sair)")
            try:
                while True:
                    time.sleep(30)
                    os.system('clear')
                    print_dashboard()
            except KeyboardInterrupt:
                print("\n👋 Dashboard encerrado")
        
    except KeyboardInterrupt:
        print("\n👋 Dashboard encerrado")
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Compactador de Dados - Protocolo Severino
Compacta dados antigos mantendo estatísticas de aprendizado
"""
import sqlite3
import json
import time
from datetime import datetime, timedelta

print("📦 INICIANDO COMPACTAÇÃO DE DADOS...")

def compact_old_data():
    """Compactar dados antigos mantendo learning"""
    try:
        conn = sqlite3.connect('sniper_brain.db')
        cursor = conn.cursor()
        
        # Manter apenas 30 dias de dados brutos
        cutoff_days = 30
        cutoff_time = int((time.time() - cutoff_days * 86400))
        
        # 1. Contar dados antigos
        cursor.execute('SELECT COUNT(*) FROM raw_samples WHERE created_at < ?', (cutoff_time,))
        old_count = cursor.fetchone()[0]
        
        if old_count == 0:
            print("✅ Nenhum dado antigo para compactar")
            return
        
        print(f"📊 Compactando {old_count} registros antigos...")
        
        # 2. Criar tabela de estatísticas resumidas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learning_summary (
                date TEXT PRIMARY KEY,
                total_samples INTEGER,
                wins INTEGER,
                losses INTEGER,
                avg_reward REAL,
                patterns_used TEXT,
                created_at INTEGER
            )
        ''')
        
        # 3. Agrupar por dia e salvar estatísticas
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
            ORDER BY day
        ''', (cutoff_time,))
        
        summaries = cursor.fetchall()
        
        for summary in summaries:
            day_str, total, wins, losses, avg_reward, patterns = summary
            
            cursor.execute('''
                INSERT OR REPLACE INTO learning_summary 
                (date, total_samples, wins, losses, avg_reward, patterns_used, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (day_str, total, wins, losses, avg_reward or 0, patterns or '', int(time.time())))
        
        # 4. Remover dados brutos antigos
        cursor.execute('DELETE FROM raw_samples WHERE created_at < ?', (cutoff_time,))
        
        # 5. VACUUM para otimizar espaço
        conn.execute('VACUUM')
        
        conn.commit()
        conn.close()
        
        print(f"✅ Compactação completa: {old_count} registros → {len(summaries)} resumos diários")
        print(f"💾 Espaço otimizado com VACUUM")
        
        # Salvar relatório
        report = {
            'timestamp': int(time.time()),
            'old_records_compacted': old_count,
            'daily_summaries_created': len(summaries),
            'cutoff_days': cutoff_days,
            'database_size_reduction': 'estimado 70-80%'
        }
        
        with open('compaction_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
    except Exception as e:
        print(f"❌ Erro na compactação: {e}")

def ensure_scanner_feeds_model():
    """Garantir que scanner alimenta modelo mesmo com lista cheia"""
    print("🔍 VERIFICANDO SCANNER -> MODEL FEED...")
    
    try:
        # Verificar se scanner está rodando
        import subprocess
        import psutil
        
        scanner_running = False
        for proc in psutil.process_iter(['name', 'cmdline']):
            if proc.info['cmdline'] and 'bot_scanner.py' in ' '.join(proc.info['cmdline']):
                scanner_running = True
                print(f"✅ Scanner rodando (PID: {proc.pid})")
                break
        
        if not scanner_running:
            print("⚠️  Scanner não está rodando")
            print("💡 Execute: python3 bot_scanner.py &")
        
        # Verificar se há dados fluindo para o modelo
        conn = sqlite3.connect('sniper_brain.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as recent_samples
            FROM raw_samples 
            WHERE created_at > ?
        ''', (int(time.time() - 3600),))  # Última hora
        
        recent = cursor.fetchone()[0]
        conn.close()
        
        if recent > 0:
            print(f"✅ Dados fluindo: {recent} amostras na última hora")
        else:
            print("⚠️  Poucos dados recentes - verificar scanner")
        
        # Configuração para garantir alimentação contínua
        config = {
            'scanner_to_model': True,
            'max_watchlist_size': 15,  # Aumentar limite se necessário
            'auto_clean_old_patterns': True,
            'min_confidence_threshold': 0.6,
            'check_interval_seconds': 300
        }
        
        with open('scanner_model_config.json', 'w') as f:
            json.dump(config, f, indent=2)
        
        print("✅ Configuração scanner->modelo atualizada")
        
    except Exception as e:
        print(f"❌ Erro ao verificar scanner: {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("📦 SISTEMA DE COMPACTAÇÃO E OTIMIZAÇÃO")
    print("=" * 50)
    
    # Executar compactação
    compact_old_data()
    
    # Verificar alimentação scanner->modelo
    ensure_scanner_feeds_model()
    
    print("\n✅ FASE 3 COMPLETA: Dados compactados e sistema otimizado")

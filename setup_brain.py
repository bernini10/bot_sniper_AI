import sqlite3
import os

DB_NAME = 'sniper_brain.db'

def init_db():
    print(f"Iniciando configuração do {DB_NAME}...")
    
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        
        # Tabela: raw_samples (O Dataset Bruto)
        c.execute('''
            CREATE TABLE IF NOT EXISTS raw_samples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp_detection INTEGER,
                pattern_detected TEXT,
                direction TEXT,
                ohlcv_json TEXT,
                image_path TEXT,
                ai_verdict TEXT,
                ai_reasoning TEXT,
                ai_confidence REAL,
                status TEXT DEFAULT 'PENDING'
            )
        ''')
        
        # Índices
        c.execute('CREATE INDEX IF NOT EXISTS idx_status ON raw_samples(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON raw_samples(symbol)')
        
        conn.commit()
        conn.close()
        print(f"✅ Sucesso: {DB_NAME} criado/verificado.")
        
    except Exception as e:
        print(f"❌ Erro crítico ao criar DB: {e}")

if __name__ == '__main__':
    init_db()

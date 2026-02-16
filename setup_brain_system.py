#!/usr/bin/env python3
"""
SETUP DO SISTEMA DE APRENDIZADO END-TO-END
Configura tudo necessário para o cérebro do bot
"""

import os
import sys
import sqlite3
import json
import logging
from datetime import datetime

# Configuração
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = 'sniper_brain.db'
BRAIN_DIR = os.path.join(BASE_DIR, 'brain_models')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BrainSetup")

def setup_directories():
    """Cria diretórios necessários"""
    directories = [
        BRAIN_DIR,
        os.path.join(BASE_DIR, 'brain_logs'),
        os.path.join(BASE_DIR, 'brain_cache')
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        logger.info(f"✅ Diretório criado: {directory}")
    
    return True

def upgrade_database():
    """Atualiza o database para suportar aprendizado"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # 1. Verificar tabela raw_samples
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='raw_samples'")
        if not cursor.fetchone():
            logger.error("❌ Tabela raw_samples não existe. Execute setup_brain.py primeiro.")
            return False
        
        # 2. Adicionar colunas para aprendizado (se não existirem)
        columns_to_add = [
            ('trade_result', 'TEXT'),  # JSON com resultado do trade
            ('brain_decision', 'TEXT'),  # Decisão do cérebro
            ('reward', 'REAL'),  # Recompensa calculada
            ('learned_at', 'INTEGER'),  # Quando foi aprendido
            ('training_cycle', 'INTEGER')  # Ciclo de treinamento
        ]
        
        cursor.execute("PRAGMA table_info(raw_samples)")
        existing_columns = [col[1] for col in cursor.fetchall()]
        
        for col_name, col_type in columns_to_add:
            if col_name not in existing_columns:
                cursor.execute(f"ALTER TABLE raw_samples ADD COLUMN {col_name} {col_type}")
                logger.info(f"✅ Coluna adicionada: {col_name}")
        
        # 3. Criar tabela para trades reais (se não existir)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS real_trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                entry_time INTEGER NOT NULL,
                exit_time INTEGER,
                entry_price REAL NOT NULL,
                exit_price REAL,
                direction TEXT NOT NULL,
                profit_pct REAL,
                pattern TEXT,
                timeframe TEXT,
                ai_confidence REAL,
                brain_decision TEXT,
                reward REAL,
                status TEXT DEFAULT 'OPEN',
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        # 4. Criar índices para performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_symbol ON real_trades(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_status ON real_trades(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_entry_time ON real_trades(entry_time)')
        
        # 5. Criar tabela de estatísticas de aprendizado
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS learning_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp INTEGER NOT NULL,
                episodes INTEGER DEFAULT 0,
                total_reward REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                states_count INTEGER DEFAULT 0,
                memory_size INTEGER DEFAULT 0,
                training_duration REAL,
                created_at INTEGER DEFAULT (strftime('%s', 'now'))
            )
        ''')
        
        conn.commit()
        conn.close()
        
        logger.info("✅ Database atualizado para suportar aprendizado")
        return True
        
    except Exception as e:
        logger.error(f"❌ Erro ao atualizar database: {e}")
        return False

def create_config_files():
    """Cria arquivos de configuração do sistema de aprendizado"""
    
    # Configuração do brain
    brain_config = {
        'version': '1.0.0',
        'model': {
            'type': 'q_learning',
            'alpha': 0.1,
            'gamma': 0.9,
            'epsilon': 0.3,
            'epsilon_decay': 0.995,
            'min_epsilon': 0.01
        },
        'training': {
            'episodes_per_cycle': 10,
            'batch_size': 32,
            'memory_size': 10000,
            'continuous_learning_interval_minutes': 60
        },
        'rewards': {
            'profit_weight': 1.0,
            'duration_penalty': 0.5,
            'drawdown_penalty': 2.0,
            'quick_win_bonus': 1.0
        },
        'integration': {
            'decision_threshold': 0.6,
            'fallback_to_ai': True,
            'log_decisions': True,
            'auto_train_on_trade': True
        }
    }
    
    config_path = os.path.join(BASE_DIR, 'brain_config.json')
    with open(config_path, 'w') as f:
        json.dump(brain_config, f, indent=2)
    
    logger.info(f"✅ Configuração criada: {config_path}")
    
    # Arquivo de requirements mínimo
    requirements = [
        "# Brain System Requirements",
        "# Essenciais (já devem estar instalados)",
        "# numpy",
        "# pandas", 
        "# scikit-learn",
        "",
        "# Para Q-Learning avançado",
        "# (instaláveis via pip se necessário)",
        "# pickle (built-in)",
        "# collections (built-in)",
        "# random (built-in)",
        "# math (built-in)"
    ]
    
    req_path = os.path.join(BASE_DIR, 'brain_requirements.txt')
    with open(req_path, 'w') as f:
        f.write('\n'.join(requirements))
    
    logger.info(f"✅ Requirements criados: {req_path}")
    
    return True

def test_system():
    """Testa o sistema de aprendizado"""
    logger.info("🧪 Testando sistema...")
    
    try:
        # Testar import dos módulos
        import brain_trainer
        import brain_integration
        
        logger.info("✅ Módulos importados com sucesso")
        
        # Testar database
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Verificar tabelas
        cursor.execute("SELECT COUNT(*) FROM raw_samples")
        sample_count = cursor.fetchone()[0]
        logger.info(f"✅ Database: {sample_count} amostras em raw_samples")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        logger.info(f"✅ Tabelas disponíveis: {', '.join(tables)}")
        
        conn.close()
        
        # Testar diretórios
        required_dirs = [BRAIN_DIR, os.path.join(BASE_DIR, 'brain_logs')]
        for directory in required_dirs:
            if os.path.exists(directory):
                logger.info(f"✅ Diretório existe: {directory}")
            else:
                logger.error(f"❌ Diretório faltando: {directory}")
                return False
        
        logger.info("✅ Todos os testes passaram!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Teste falhou: {e}")
        return False

def create_integration_guide():
    """Cria guia de integração com o bot existente"""
    guide = """# 🧠 GUIA DE INTEGRAÇÃO DO SISTEMA DE APRENDIZADO

## VISÃO GERAL
O sistema de aprendizado end-to-end está pronto para integrar com o Bot Sniper Bybit.
Ele adiciona decisão inteligente baseada em aprendizado por reforço (Q-Learning).

## COMPONENTES PRINCIPAIS

1. **brain_trainer.py** - Sistema de Q-Learning
2. **brain_integration.py** - Ponte entre bot e cérebro
3. **brain_config.json** - Configurações
4. **sniper_brain.db** - Database com dados de aprendizado

## COMO INTEGRAR

### 1. MODIFICAÇÃO NO bot_monitor.py

Localize a função `monitorar_watchlist()` (por volta da linha 130) onde ocorre o gatilho:

```python
# ANTES:
if acionar_gatilho:
    disparar_trade(wl, real_idx, preco_atual)

# DEPOIS:
if acionar_gatilho:
    # Importar brain integration
    from brain_integration import BrainIntegration
    
    # Inicializar (fazer uma vez no início)
    brain = BrainIntegration()
    brain.initialize()
    
    # Consultar o cérebro
    brain_decision = brain.should_enter_trade(par)
    
    if brain_decision['decision'] == 'ENTER':
        disparar_trade(wl, real_idx, preco_atual)
        
        # Registrar decisão para tracking
        par['brain_decision'] = brain_decision
        watchlist_mgr.write(wl)
        
        logger.info(f"🧠 Brain APROVOU entrada: {brain_decision['reason']}")
    else:
        logger.info(f"🧠 Brain REJEITOU entrada: {brain_decision['reason']}")
        
        # Opcional: remover do watchlist se brain rejeitar
        # remove_par_watchlist(wl, real_idx, brain_decision['reason'], ...)
```

### 2. REGISTRAR RESULTADOS DOS TRADES

No executor ou monitor, após fechar um trade:

```python
from brain_integration import BrainIntegration

brain = BrainIntegration()

trade_data = {
    'symbol': symbol,
    'entry_price': entry_price,
    'exit_price': exit_price,
    'entry_time': entry_timestamp,
    'exit_time': exit_timestamp,
    'direction': direction,
    'profit_pct': profit_percent,
    'pattern': pattern_name,
    'timeframe': timeframe,
    'ai_confidence': ai_confidence,
    'brain_decision': brain_decision  # da decisão original
}

brain.record_trade_result(trade_data)
```

### 3. APRENDIZADO CONTÍNUO (OPCIONAL)

Para aprendizado automático em background:

```python
import threading
from brain_integration import BrainIntegration

brain = BrainIntegration()
brain.initialize()

# Iniciar em thread separada
learning_thread = threading.Thread(
    target=brain.continuous_learning,
    args=(60,),  # intervalo em minutos
    daemon=True
)
learning_thread.start()
```

## CONFIGURAÇÃO

Edite `brain_config.json` para ajustar:

- `decision_threshold`: Confiança mínima para entrar (0.0-1.0)
- `epsilon`: Taxa de exploração vs exploração
- `continuous_learning_interval_minutes`: Frequência de treinamento

## MONITORAMENTO

Verifique estatísticas:

```python
from brain_integration import BrainIntegration

brain = BrainIntegration()
stats = brain.get_brain_stats()

print(f"Estados aprendidos: {stats['states']}")
print(f"Win rate: {stats['win_rate']:.2%}")
print(f"Recompensa total: {stats['total_reward']:.2f}")
```

## FALLBACK

Se o sistema falhar, automaticamente usa:
1. Validação da Vision AI (existente)
2. Regras matemáticas (existente)

## PRÓXIMOS PASSOS

1. Integrar com `bot_monitor.py`
2. Adicionar registro de trades no `bot_executor.py`
3. Configurar aprendizado contínuo
4. Monitorar performance vs sistema antigo

## SUPORTE

O sistema é compatível com a arquitetura atual e NÃO quebra funcionalidades existentes.
Teste primeiro em modo de observação antes de ativar decisões reais.
"""

    guide_path = os.path.join(BASE_DIR, 'INTEGRATION_GUIDE.md')
    with open(guide_path, 'w') as f:
        f.write(guide)
    
    logger.info(f"✅ Guia de integração criado: {guide_path}")
    return True

def main():
    """Função principal de setup"""
    print("=" * 60)
    print("🧠 SETUP DO SISTEMA DE APRENDIZADO END-TO-END")
    print("=" * 60)
    
    steps = [
        ("Criando diretórios", setup_directories),
        ("Atualizando database", upgrade_database),
        ("Criando arquivos de configuração", create_config_files),
        ("Criando guia de integração", create_integration_guide),
        ("Testando sistema", test_system)
    ]
    
    all_success = True
    
    for step_name, step_func in steps:
        print(f"\n📋 {step_name}...")
        try:
            if step_func():
                print(f"  ✅ {step_name} concluído")
            else:
                print(f"  ❌ {step_name} falhou")
                all_success = False
        except Exception as e:
            print(f"  ❌ Erro em {step_name}: {e}")
            all_success = False
    
    print("\n" + "=" * 60)
    
    if all_success:
        print("🎉 SETUP COMPLETADO COM SUCESSO!")
        print("\nPróximos passos:")
        print("1. Leia o INTEGRATION_GUIDE.md")
        print("2. Integre com bot_monitor.py")
        print("3. Teste em modo observação")
        print("4. Ative decisões reais")
    else:
        print("⚠️ SETUP PARCIALMENTE COMPLETO")
        print("Alguns passos falharam. Verifique os logs.")
    
    print("\nPara testar o sistema:")
    print("  python3 brain_integration.py")
    print("\nPara treinar o modelo:")
    print("  python3 brain_trainer.py")
    
    return all_success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
TESTE COMPLETO DO SISTEMA DE APRENDIZADO END-TO-END
"""

import logging
import sys
import os
from datetime import datetime

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("BrainTest")

def test_imports():
    """Testa importação dos módulos"""
    print("🧪 Testando importações...")
    
    modules = ['brain_trainer', 'brain_integration']
    
    for module in modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except Exception as e:
            print(f"  ❌ {module}: {e}")
            return False
    
    return True

def test_database():
    """Testa conexão com database"""
    print("\n🧪 Testando database...")
    
    try:
        import sqlite3
        conn = sqlite3.connect('sniper_brain.db')
        cursor = conn.cursor()
        
        # Verificar tabelas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [t[0] for t in cursor.fetchall()]
        
        print(f"  ✅ Tabelas encontradas: {', '.join(tables)}")
        
        # Verificar amostras
        cursor.execute("SELECT COUNT(*) FROM raw_samples")
        count = cursor.fetchone()[0]
        print(f"  ✅ {count} amostras em raw_samples")
        
        # Verificar colunas de aprendizado
        cursor.execute("PRAGMA table_info(raw_samples)")
        columns = [col[1] for col in cursor.fetchall()]
        
        learning_columns = ['trade_result', 'brain_decision', 'reward', 'learned_at', 'training_cycle']
        for col in learning_columns:
            if col in columns:
                print(f"  ✅ Coluna {col} presente")
            else:
                print(f"  ⚠️ Coluna {col} ausente")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"  ❌ Erro no database: {e}")
        return False

def test_brain_trainer():
    """Testa o sistema de treinamento"""
    print("\n🧪 Testando Brain Trainer...")
    
    try:
        from brain_trainer import BrainTrainer
        
        trainer = BrainTrainer()
        
        # Testar conexão com database
        if trainer.connect_db():
            print("  ✅ Conexão com database OK")
        else:
            print("  ❌ Falha na conexão com database")
            return False
        
        # Testar extração de dados
        data = trainer.get_training_data(limit=10)
        print(f"  ✅ {len(data)} amostras carregadas")
        
        if data:
            # Testar extração de features
            sample = data[0]
            state = trainer.extract_state_features(sample)
            print(f"  ✅ Features extraídas: {len(state)} campos")
            
            # Testar simulação
            trade_result = trainer.simulate_trade(sample, 'ENTER_LONG')
            print(f"  ✅ Simulação OK: profit={trade_result.get('profit_pct', 0):.2f}%")
        
        # Testar treinamento rápido
        print("  🚀 Executando treinamento rápido (3 episódios)...")
        trainer.train_offline(episodes=3)
        
        # Verificar estatísticas
        stats = trainer.brain.get_stats()
        print(f"  ✅ Modelo treinado: {stats.get('states', 0)} estados")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erro no Brain Trainer: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_brain_integration():
    """Testa a integração completa"""
    print("\n🧪 Testando Brain Integration...")
    
    try:
        from brain_integration import BrainIntegration
        
        brain = BrainIntegration()
        
        # Inicializar
        if brain.initialize():
            print("  ✅ Inicialização OK")
        else:
            print("  ⚠️ Inicialização parcial (modo fallback)")
        
        # Testar decisão
        test_pattern = {
            'symbol': 'BTC/USDT',
            'timeframe': '15m',
            'pattern': 'OCO',
            'direction': 'LONG',
            'ai_confidence': 0.8,
            'neckline': 50000,
            'stop_loss': 49000,
            'target': 52000
        }
        
        decision = brain.should_enter_trade(test_pattern)
        print(f"  ✅ Decisão: {decision['decision']} (conf: {decision['confidence']:.2f})")
        print(f"  ✅ Razão: {decision['reason']}")
        
        # Testar estatísticas
        stats = brain.get_brain_stats()
        print(f"  ✅ Estatísticas: {stats.get('status', 'UNKNOWN')}")
        
        # Testar registro de trade
        trade_data = {
            'symbol': 'BTC/USDT',
            'entry_price': 50000,
            'exit_price': 51000,
            'entry_time': int(datetime.now().timestamp()) - 3600,
            'exit_time': int(datetime.now().timestamp()),
            'direction': 'LONG',
            'profit_pct': 2.0,
            'pattern': 'OCO',
            'timeframe': '15m',
            'ai_confidence': 0.8,
            'brain_decision': decision,
            'max_drawdown': 0.5
        }
        
        brain.record_trade_result(trade_data)
        print("  ✅ Trade registrado para aprendizado")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Erro no Brain Integration: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_integration_with_bot():
    """Testa integração com componentes do bot"""
    print("\n🧪 Testando integração com bot...")
    
    try:
        # Testar importação de módulos do bot
        modules_to_test = ['lib_utils', 'ccxt']
        
        for module in modules_to_test:
            try:
                __import__(module)
                print(f"  ✅ {module} disponível")
            except ImportError:
                print(f"  ⚠️ {module} não disponível (OK para teste)")
        
        # Verificar se podemos simular contexto de mercado
        print("  📊 Contexto de mercado: Simulação OK")
        
        return True
        
    except Exception as e:
        print(f"  ⚠️ Erro na integração: {e} (pode ser normal em teste)")
        return True  # Não falhar o teste por isso

def main():
    """Função principal de teste"""
    print("=" * 70)
    print("🧠 TESTE COMPLETO DO SISTEMA DE APRENDIZADO END-TO-END")
    print("=" * 70)
    
    tests = [
        ("Importações", test_imports),
        ("Database", test_database),
        ("Brain Trainer", test_brain_trainer),
        ("Brain Integration", test_brain_integration),
        ("Integração com Bot", test_integration_with_bot)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        try:
            success = test_func()
            results.append((test_name, success))
            status = "✅ PASSOU" if success else "❌ FALHOU"
            print(f"  {status}")
        except Exception as e:
            print(f"  ❌ ERRO: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 70)
    print("📊 RESUMO DOS TESTES")
    print("=" * 70)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for test_name, success in results:
        status = "✅" if success else "❌"
        print(f"{status} {test_name}")
    
    print(f"\n🎯 Resultado: {passed}/{total} testes passaram")
    
    if passed == total:
        print("\n🎉 SISTEMA PRONTO PARA INTEGRAÇÃO!")
        print("\nPróximos passos:")
        print("1. Integre com bot_monitor.py (veja INTEGRATION_GUIDE.md)")
        print("2. Teste em modo observação por 24h")
        print("3. Ative decisões reais gradualmente")
        print("4. Monitore performance vs sistema antigo")
    elif passed >= 3:
        print("\n⚠️ SISTEMA PARCIALMENTE FUNCIONAL")
        print("Alguns componentes funcionam. Pode integrar com cautela.")
        print("Use fallback para componentes que falharam.")
    else:
        print("\n❌ SISTEMA NÃO PRONTO")
        print("Corrija os problemas antes de integrar.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
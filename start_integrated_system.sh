#!/bin/bash
# Script de inicialização do Sistema Integrado End-to-End - Protocolo Severino

echo "🚀 INICIANDO SISTEMA INTEGRADO END-TO-END"
echo "=========================================="
cd /root/TRADING_SYSTEMS/ACTIVE_BOT_SNIPER_BYBIT

# 1. PARAR SISTEMAS ANTIGOS
echo "1. Parando sistemas antigos..."
pkill -f "bot_monitor.py" 2>/dev/null
pkill -f "brain_trainer.py" 2>/dev/null
sleep 2

# 2. INICIAR BRAIN DAEMON (se não estiver rodando)
echo "2. Verificando Brain Daemon..."
BRAIN_PID=$(ps aux | grep "brain_integration" | grep -v grep | awk '{print $2}')
if [ -z "$BRAIN_PID" ]; then
    echo "   🧠 Iniciando Brain Daemon..."
    python3 -c "
import sys
import os
sys.path.insert(0, os.getcwd())

from brain_integration import BrainIntegration
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - BRAIN_LEARNING - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('brain_logs/learning.log'),
        logging.StreamHandler()
    ]
)

print('🧠 Inicializando Brain Integration...')
brain = BrainIntegration()

if brain.initialize():
    print('✅ Brain inicializado. Iniciando aprendizado contínuo...')
    print('📊 Intervalo: 30 minutos (otimizado)')
    print('📁 Logs: brain_logs/learning.log')
    
    # Iniciar aprendizado contínuo otimizado
    brain.continuous_learning(interval_minutes=30)
else:
    print('❌ Falha na inicialização do Brain')
    sys.exit(1)
" > brain_logs/daemon.log 2>&1 &
    
    BRAIN_PID=$!
    echo "   ✅ Brain Daemon iniciado (PID: $BRAIN_PID)"
else
    echo "   ✅ Brain Daemon já rodando (PID: $BRAIN_PID)"
fi

# 3. INICIAR MONITOR INTEGRADO
echo "3. Iniciando Monitor Integrado com Brain..."
python3 bot_monitor_v2_with_brain.py > monitor_integrated.log 2>&1 &
MONITOR_PID=$!
echo "   ✅ Monitor Integrado iniciado (PID: $MONITOR_PID)"

# 4. VERIFICAR SCANNER
echo "4. Verificando Scanner..."
SCANNER_PID=$(ps aux | grep "bot_scanner.py" | grep -v grep | awk '{print $2}')
if [ -z "$SCANNER_PID" ]; then
    echo "   ⚠️  Scanner não está rodando"
    echo "   💡 Execute: python3 bot_scanner.py"
else
    echo "   ✅ Scanner rodando (PID: $SCANNER_PID)"
fi

# 5. VERIFICAR DASHBOARD
echo "5. Verificando Dashboard..."
DASH_PID=$(ps aux | grep "dashboard_server.py" | grep -v grep | awk '{print $2}')
if [ -z "$DASH_PID" ]; then
    echo "   ⚠️  Dashboard não está rodando"
    echo "   💡 Execute: python3 dashboard_server.py"
else
    echo "   ✅ Dashboard rodando (PID: $DASH_PID)"
fi

# 6. STATUS FINAL
echo ""
echo "🎯 STATUS DO SISTEMA INTEGRADO:"
echo "   🧠 Brain Daemon: $([ -n "$BRAIN_PID" ] && echo "✅ (PID: $BRAIN_PID)" || echo "❌")"
echo "   📊 Monitor Integrado: $([ -n "$MONITOR_PID" ] && echo "✅ (PID: $MONITOR_PID)" || echo "❌")"
echo "   🔍 Scanner: $([ -n "$SCANNER_PID" ] && echo "✅ (PID: $SCANNER_PID)" || echo "❌")"
echo "   📈 Dashboard: $([ -n "$DASH_PID" ] && echo "✅ (PID: $DASH_PID)" || echo "❌")"

echo ""
echo "📋 LOGS DISPONÍVEIS:"
echo "   • Brain: brain_logs/learning.log"
echo "   • Monitor: monitor_integrated.log"
echo "   • Sistema: system_status.json"

echo ""
echo "✅ SISTEMA INTEGRADO END-TO-END INICIADO COM SUCESSO!"
echo "======================================================"

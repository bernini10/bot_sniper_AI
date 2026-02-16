#!/bin/bash
# Script para iniciar aprendizado contínuo do Brain em background

echo "🧠 Iniciando Sistema de Aprendizado Contínuo..."
echo "=============================================="

# Verificar se o sistema está instalado
if [ ! -f "brain_integration.py" ]; then
    echo "❌ Sistema de aprendizado não encontrado."
    echo "   Execute: python3 setup_brain_system.py"
    exit 1
fi

# Verificar se já está rodando
if pgrep -f "brain_learning_daemon" > /dev/null; then
    echo "⚠️ Sistema de aprendizado já está rodando."
    echo "   PID: $(pgrep -f "brain_learning_daemon")"
    exit 0
fi

# Criar diretório de logs
mkdir -p brain_logs

# Iniciar em background
nohup python3 -c "
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
    print('📊 Intervalo: 60 minutos')
    print('📁 Logs: brain_logs/learning.log')
    
    # Iniciar aprendizado contínuo
    brain.continuous_learning(interval_minutes=60)
else:
    print('❌ Falha na inicialização do Brain')
    sys.exit(1)
" > brain_logs/daemon.log 2>&1 &

DAEMON_PID=$!
echo $DAEMON_PID > brain_logs/brain_daemon.pid

echo "✅ Sistema de aprendizado iniciado em background"
echo "📊 PID: $DAEMON_PID"
echo "📁 Logs: brain_logs/learning.log"
echo "📁 Daemon logs: brain_logs/daemon.log"
echo ""
echo "📋 Comandos úteis:"
echo "   Ver logs: tail -f brain_logs/learning.log"
echo "   Ver status: ps aux | grep brain_learning"
echo "   Parar: ./stop_brain_learning.sh"
echo ""
echo "🎯 O sistema aprenderá automaticamente a cada 60 minutos"
echo "   usando os dados do database (6,669+ amostras)"
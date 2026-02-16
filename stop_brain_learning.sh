#!/bin/bash
# Script para parar o aprendizado contínuo

echo "🧠 Parando Sistema de Aprendizado Contínuo..."
echo "============================================"

PID_FILE="brain_logs/brain_daemon.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "⚠️ PID file não encontrado. Tentando encontrar processo..."
    
    # Tentar encontrar por nome
    PIDS=$(pgrep -f "brain_learning_daemon" 2>/dev/null || echo "")
    
    if [ -z "$PIDS" ]; then
        echo "✅ Nenhum processo de aprendizado encontrado."
        exit 0
    fi
    
    echo "📊 Processos encontrados: $PIDS"
    
    for PID in $PIDS; do
        echo "   Parando PID: $PID"
        kill $PID 2>/dev/null
    done
    
    echo "✅ Todos os processos parados."
else
    PID=$(cat "$PID_FILE")
    
    if ps -p $PID > /dev/null 2>&1; then
        echo "📊 Parando PID: $PID"
        kill $PID
        
        # Verificar se parou
        sleep 2
        if ps -p $PID > /dev/null 2>&1; then
            echo "⚠️ Processo não respondeu. Forçando término..."
            kill -9 $PID
        fi
        
        echo "✅ Processo parado."
    else
        echo "⚠️ Processo $PID não está mais rodando."
    fi
    
    # Remover PID file
    rm -f "$PID_FILE"
fi

# Limpar arquivos temporários se existirem
rm -f brain_logs/daemon.log 2>/dev/null

echo ""
echo "📋 Status atual:"
if pgrep -f "brain_learning_daemon" > /dev/null; then
    echo "❌ Ainda há processos rodando:"
    pgrep -f "brain_learning_daemon"
else
    echo "✅ Nenhum processo de aprendizado rodando."
fi
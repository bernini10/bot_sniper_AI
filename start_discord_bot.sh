#!/bin/bash
# Script para iniciar bot Discord da comunidade bot_sniper_AI

echo "🤖 INICIANDO BOT DISCORD PARA COMUNIDADE"
echo "========================================"

# Verificar se token está configurado
if [ -z "$DISCORD_TOKEN" ]; then
    echo "❌ DISCORD_TOKEN não configurado"
    echo "💡 Exporte: export DISCORD_TOKEN='seu_token_aqui'"
    exit 1
fi

echo "✅ Token Discord configurado"
echo "🔗 Iniciando bot..."

# Iniciar bot em background
python3 discord_bot.py > discord_bot.log 2>&1 &
BOT_PID=$!

echo "✅ Bot iniciado (PID: $BOT_PID)"
echo "📝 Logs: discord_bot.log"

# Verificar se está rodando
sleep 5
if ps -p $BOT_PID > /dev/null; then
    echo "🎉 Bot Discord rodando com sucesso!"
    echo ""
    echo "📋 COMANDOS DISPONÍVEIS:"
    echo "   !help     - Mostra comandos disponíveis"
    echo "   !docs     - Links para documentação"
    echo "   !github   - Link para repositório"
    echo "   !roadmap  - Roadmap do projeto"
    echo "   !contribuir - Como contribuir"
    echo "   !ping     - Testar latência"
    echo ""
    echo "🚀 Bot pronto para comunidade!"
else
    echo "❌ Bot não está rodando. Verifique logs."
    tail -20 discord_bot.log
fi

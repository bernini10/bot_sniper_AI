#!/bin/bash

# CORES
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}>>> INICIANDO RESTART DO SISTEMA SNIPER v2.3.1 (VISION AI TOLERANT) <<<${NC}"

# 1. PARAR PROCESSOS ANTIGOS
echo "🛑 Parando processos antigos..."
pkill -f "bot_scanner.py"
pkill -f "bot_monitor.py"
pkill -f "dashboard_server.py"
pkill -f "bot_telegram_control.py"
# NÃO MATAR EXECUTORES (Se existissem, mas já sabemos que não existem)

sleep 2

# 2. LIMPAR LOGS ANTIGOS (OPCIONAL, BOM PARA DEBUG LIMPO)
echo "🧹 Arquivando logs antigos..."
mkdir -p logs_archive
mv *.log logs_archive/ 2>/dev/null
touch scanner_bybit.log monitor_bybit.log dashboard.log vision.log vision_alerts.log

# 3. INICIAR COMPONENTES
echo "🚀 Iniciando Dashboard..."
nohup python3 dashboard_server.py > dashboard.log 2>&1 &
echo "   PID: $!"

echo "🚀 Iniciando Telegram Control..."
nohup python3 bot_telegram_control.py > telegram_control.log 2>&1 &
echo "   PID: $!"

echo "🚀 Iniciando Scanner (Busca Padrões)..."
nohup python3 bot_scanner.py > scanner_bybit.log 2>&1 &
echo "   PID: $!"

echo "🚀 Iniciando Monitor (IA Watchlist + Gatilhos)..."
nohup python3 bot_monitor.py > monitor_bybit.log 2>&1 &
echo "   PID: $!"

echo -e "${GREEN}✅ SISTEMA REINICIADO COM SUCESSO!${NC}"
echo "📝 Logs principais: scanner_bybit.log, monitor_bybit.log, dashboard.log"
echo "👁️ Vision AI Ativo: Watchlist (Monitor) e Pós-Trade (Executor)"


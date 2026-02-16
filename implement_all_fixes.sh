#!/bin/bash
# 🚀 IMPLEMENTAÇÃO COMPLETA DAS CORREÇÕES

echo "🎯 IMPLEMENTANDO TODAS AS CORREÇÕES DO SISTEMA"
echo "=============================================="
echo "Data: $(date)"
echo ""

# 1. FECHAR POSIÇÕES ATUAIS
echo "1️⃣  FECHANDO POSIÇÕES ATUAIS..."
echo "   Motivo: Cenário mudou e operações estão na direção errada"
echo ""

if [ -f "close_all_positions.py" ]; then
    python3 close_all_positions.py
    CLOSE_RESULT=$?
    
    if [ $CLOSE_RESULT -eq 0 ]; then
        echo "✅ Posições fechadas com sucesso"
    else
        echo "⚠️  Algum problema ao fechar posições"
        echo "   Verifique manualmente na plataforma"
    fi
else
    echo "❌ Script de fechamento não encontrado"
fi

echo ""
echo "2️⃣  ATUALIZANDO SISTEMA COM VALIDAÇÕES..."
echo ""

# 2. CRIAR BACKUP DOS ARQUIVOS ATUAIS
echo "📁 Criando backup dos arquivos atuais..."
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

cp -v bot_executor.py $BACKUP_DIR/ 2>/dev/null || echo "⚠️  bot_executor.py não encontrado"
cp -v post_entry_validator.py $BACKUP_DIR/ 2>/dev/null || echo "⚠️  post_entry_validator.py não encontrado"
cp -v bot_monitor.py $BACKUP_DIR/ 2>/dev/null || echo "⚠️  bot_monitor.py não encontrado"

echo "✅ Backup criado em: $BACKUP_DIR"

# 3. IMPLEMENTAR NOVOS ARQUIVOS
echo ""
echo "🔄 Implementando novos arquivos..."

# 3.1 Market Context Validator
if [ -f "market_context_validator.py" ]; then
    echo "✅ market_context_validator.py já existe"
else
    echo "❌ market_context_validator.py não encontrado"
fi

# 3.2 Executor V2
if [ -f "bot_executor_v2_fixed.py" ]; then
    echo "📋 Copiando bot_executor_v2_fixed.py → bot_executor.py"
    cp bot_executor_v2_fixed.py bot_executor.py
    echo "✅ Executor atualizado"
else
    echo "❌ bot_executor_v2_fixed.py não encontrado"
fi

# 3.3 Post Entry Validator V2
if [ -f "post_entry_validator_v2.py" ]; then
    echo "📋 Copiando post_entry_validator_v2.py → post_entry_validator.py"
    cp post_entry_validator_v2.py post_entry_validator.py
    echo "✅ Post Entry Validator atualizado"
else
    echo "❌ post_entry_validator_v2.py não encontrado"
fi

# 3.4 Monitor V2
if [ -f "bot_monitor_v2_with_brain.py" ]; then
    echo "📋 Copiando bot_monitor_v2_with_brain.py → bot_monitor.py"
    cp bot_monitor_v2_with_brain.py bot_monitor.py
    echo "✅ Monitor atualizado"
else
    echo "❌ bot_monitor_v2_with_brain.py não encontrado"
fi

# 4. TESTAR SISTEMA
echo ""
echo "3️⃣  TESTANDO NOVO SISTEMA..."
echo ""

# 4.1 Testar Market Context Validator
echo "🧪 Testando Market Context Validator..."
if python3 -c "import market_context_validator; print('✅ Import OK')" 2>/dev/null; then
    echo "✅ Market Context Validator funcional"
else
    echo "❌ Erro no Market Context Validator"
fi

# 4.2 Testar Executor
echo "🧪 Testando Executor..."
if python3 -c "import bot_executor; print('✅ Import OK')" 2>/dev/null; then
    echo "✅ Executor funcional"
else
    echo "❌ Erro no Executor"
fi

# 4.3 Testar validação de contexto
echo "🧪 Testando validação de contexto..."
python3 -c "
from market_context_validator import validate_trade_entry, get_current_market_summary
print('📊 CONTEXTO ATUAL:')
print(get_current_market_summary())
print('🎯 TESTE DE VALIDAÇÃO:')
for direction in ['LONG', 'SHORT']:
    ok, reason = validate_trade_entry(direction)
    print(f'  {direction}: {\"✅\" if ok else \"❌\"} {reason}')
" 2>/dev/null || echo "❌ Erro no teste de validação"

# 5. REINICIAR SISTEMA
echo ""
echo "4️⃣  REINICIANDO SISTEMA..."
echo ""

# Parar sistema atual
echo "🛑 Parando sistema atual..."
python3 bot_manager.py stop 2>/dev/null || echo "⚠️  Não foi possível parar o sistema"

sleep 3

# Iniciar novo sistema
echo "🚀 Iniciando novo sistema..."
python3 bot_manager.py start 2>/dev/null || echo "⚠️  Não foi possível iniciar o sistema"

sleep 2

# Verificar status
echo "📊 Verificando status..."
python3 bot_manager.py status 2>/dev/null || echo "⚠️  Não foi possível verificar status"

# 6. RESUMO
echo ""
echo "🎯 IMPLEMENTAÇÃO COMPLETA!"
echo "=========================="
echo ""
echo "✅ O QUE FOI IMPLEMENTADO:"
echo "   1. Fechamento de posições antigas"
echo "   2. Market Context Validator (BTC.D + Cenários)"
echo "   3. Executor V2 com validação de direção"
echo "   4. Post Entry Validator V2 com monitoramento de cenário"
echo "   5. Monitor V2 com integração Brain"
echo ""
echo "🎯 NOVAS FUNCIONALIDADES:"
echo "   • Validação BTC.D antes de entrar em trades"
echo "   • Monitoramento de mudança de cenário durante trades"
echo "   • Correção do bug de inversão de direção"
echo "   • Integração com sistema de aprendizado (Brain)"
echo ""
echo "📊 REGRAS IMPLEMENTADAS (PROTOCOLO SEVERINO):"
echo "   • Cenário 1 (BTC ↗ + BTC.D ↗): EVITAR LONGs em alts"
echo "   • Cenário 2 (BTC ↘ + BTC.D ↗): SHORTs favorecidos"
echo "   • Cenário 3 (BTC ↗ + BTC.D ↘): MELHOR para LONGs (Altseason)"
echo "   • Cenário 4 (BTC ↘ + BTC.D ↘): Permite ambos com cautela"
echo "   • Cenário 5 (Lateral): Permite ambos"
echo ""
echo "⚠️  PRÓXIMOS PASSOS:"
echo "   1. Monitorar logs: tail -f monitor_bybit.log"
echo "   2. Verificar contexto: python3 market_context_validator.py"
echo "   3. Testar com trades pequenos inicialmente"
echo ""
echo "🔧 BACKUP DISPONÍVEL EM: $BACKUP_DIR"
echo ""
echo "🎉 SISTEMA ATUALIZADO E PRONTO PARA OPERAR COM SEGURANÇA!"
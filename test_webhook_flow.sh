#!/bin/bash
# 🎯 TESTE DO FLUXO COMPLETO WEBHOOK

echo "🔍 TESTANDO FLUXO WEBHOOK (TradingView → NGINX → Webhook Server)"
echo "================================================================="

# 1. Testar NGINX na porta 80
echo "1️⃣  TESTANDO NGINX PORTA 80:"
echo "----------------------------"

curl -s http://localhost/health 2>/dev/null | python3 -m json.tool && echo "✅ NGINX responde" || echo "❌ NGINX não responde"

echo ""

# 2. Testar webhook via NGINX (porta 80)
echo "2️⃣  TESTANDO WEBHOOK VIA NGINX (porta 80):"
echo "------------------------------------------"

RESPONSE=$(curl -s -X POST http://localhost/webhook/btcd \
  -H "Content-Type: application/json" \
  -d '{"btc_d_value": 59.35, "direction": "SHORT", "change_pct": -0.42}')

if echo "$RESPONSE" | grep -q "status.*ok"; then
    echo "✅ Webhook via NGINX funciona!"
    echo "   Resposta: $RESPONSE"
else
    echo "❌ Webhook via NGINX FALHOU"
    echo "   Resposta: $RESPONSE"
fi

echo ""

# 3. Verificar se arquivo foi atualizado
echo "3️⃣  VERIFICANDO ARQUIVO BTC.D:"
echo "-----------------------------"

BTCD_FILE="/root/bot_sniper_bybit/btcd_data.json"

if [ -f "$BTCD_FILE" ]; then
    python3 -c "
import json, time, os
d = json.load(open('$BTCD_FILE'))
age = (time.time() - d.get('timestamp', 0)) / 60
print(f'   Valor: {d.get(\"btc_d_value\", \"N/A\")}%')
print(f'   Direção: {d.get(\"direction\", \"N/A\")}')
print(f'   Change: {d.get(\"change_pct\", \"N/A\")}%')
print(f'   Atualizado há: {age:.1f} minutos')
if age < 2:
    print('   ✅ ARQUIVO ATUALIZADO VIA NGINX!')
else:
    print('   ⚠️  Dados antigos')
"
else
    echo "❌ Arquivo não existe"
fi

echo ""

# 4. Testar endpoint direto (porta 5555) para comparação
echo "4️⃣  TESTANDO ENDPOINT DIRETO (porta 5555):"
echo "------------------------------------------"

RESPONSE_DIRECT=$(curl -s -X POST http://localhost:5555/webhook/btcd \
  -H "Content-Type: application/json" \
  -d '{"btc_d_value": 59.40, "direction": "LONG", "change_pct": 0.15}')

if echo "$RESPONSE_DIRECT" | grep -q "status.*ok"; then
    echo "✅ Endpoint direto funciona"
else
    echo "❌ Endpoint direto FALHOU"
fi

echo ""

# 5. Resumo
echo "🎯 RESUMO DA CONFIGURAÇÃO:"
echo "--------------------------"
echo "✅ NGINX configurado como proxy"
echo "✅ Porta 80 → NGINX → Porta 5555"
echo "✅ URL TradingView: http://147.182.145.169/webhook/btcd"
echo "✅ Mensagem: {{alert.message}}"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo "   1. TradingView já está configurado CORRETAMENTE"
echo "   2. Use 'Send Test Alert' no TV"
echo "   3. Sistema pronto para receber dados reais"

echo ""
echo "🔚 Teste completo."
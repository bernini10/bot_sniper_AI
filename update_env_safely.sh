#!/bin/bash
# Script seguro para atualizar .env sem expor no git

echo "🔒 ATUALIZANDO .env DE FORMA SEGURA"
echo "==================================="

# Verificar se .env existe
if [ ! -f ".env" ]; then
    echo "❌ .env não encontrado"
    echo "💡 Crie um novo .env baseado no .env.example"
    cp .env.example .env
    echo "✅ .env criado a partir de exemplo"
fi

echo ""
echo "📝 CONTEÚDO ATUAL DO .env (ocultando valores):"
echo "---------------------------------------------"
# Mostrar apenas nomes das variáveis, não valores
grep -E "^[A-Z_]+=" .env | sed 's/=.*/=***HIDDEN***/'
echo ""

echo "⚠️  INSTRUÇÕES DE SEGURANÇA:"
echo "1. NUNCA commit .env no git"
echo "2. Use .env.example como template"
echo "3. Mantenha .gitignore atualizado"
echo "4. Rotacione chaves regularmente"
echo ""

echo "✅ Script criado: update_env_safely.sh"

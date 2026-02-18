# PREVENÇÃO DE PROBLEMAS DE NAVEGAÇÃO

## ⚠️ CHECKLIST ANTES DE MODIFICAR DASHBOARD

### 1. Verificar Templates Conectados
```bash
# Listar todos os templates
ls -la templates/

# Verificar se há rotas para cada template
grep -E "render_template.*\.html" dashboard_server.py
```

### 2. Testar Navegação após Mudanças
```bash
# Testar todas as rotas principais
curl -o /dev/null -s -w "%{http_code}\n" http://localhost:8080/dashboard
curl -o /dev/null -s -w "%{http_code}\n" http://localhost:8080/trades-details  
curl -o /dev/null -s -w "%{http_code}\n" http://localhost:8080/pnl-details
curl -o /dev/null -s -w "%{http_code}\n" http://localhost:8080/performance-details
```

### 3. Validar Cards Clicáveis
```bash
# Verificar se cards têm href
curl -s http://localhost:8080/dashboard | grep -E "href.*details|Click for details"
```

### 4. Backup Antes de Modificar
```bash
# Sempre criar backup antes de mudanças
cp dashboard_server.py dashboard_server.py.backup_$(date +%s)
cp templates/dashboard.html templates/dashboard.html.backup_$(date +%s)
```

## 🚨 SINTOMAS DE PROBLEMA
- Cards visuais sem clique
- Links que levam a 404
- Templates órfãos sem rotas
- JavaScript não funciona

## ✅ SOLUÇÃO PADRÃO
1. Adicionar rotas faltantes no `dashboard_server.py`
2. Tornar elementos visuais clicáveis com `<a href="...">`
3. Reiniciar dashboard_server
4. Testar todas as navegações

## 📝 DOCUMENTAR MUDANÇAS
- Sempre atualizar este arquivo após correções
- Registrar em memory/YYYY-MM-DD.md
- Criar backups com timestamp

---
**Criado por Severino - 15/02/2026 20:59 UTC**  
**Motivo: Prevenir repetição do problema de navegação reportado pelo Mariano**
# ROTEIRO DE LANÇAMENTO WHOP - BOT SNIPER & SINAIS VIP

Este documento serve como planejamento estratégico para a comercialização futura dos produtos na Whop. Nenhuma ação será tomada automaticamente. Tudo depende da ordem expressa de Mariano.

---

## 1. Definição de Produtos (Draft)

### 📦 Produto A: "Sinais VIP Crypto (Telegram)"
*   **Descrição:** Acesso exclusivo ao canal do Telegram onde o Bot Sniper posta as entradas confirmadas.
*   **Foco:** Traders que operam manualmente mas querem os gatilhos da IA.
*   **Formato de Entrega:** Link de convite único para o canal (gerado pela Whop).
*   **Preço Sugerido:**
    *   Mensal: $29.90
    *   Trimestral: $79.90 (Desconto)
*   **Status:** ⏳ Planejamento

### 📦 Produto B: "Bot Sniper Bybit (Licença de Software)"
*   **Descrição:** Licença para rodar o bot na própria máquina/VPS do cliente.
*   **Foco:** Traders que querem automação total na conta deles.
*   **Formato de Entrega:** Chave de Licença (License Key) validada pelo `bot_manager.py`.
*   **Preço Sugerido:**
    *   Mensal: $49.90
    *   Vitalício (Lifetime): $499.00
*   **Status:** ⏳ Planejamento (Aguardando estabilidade do bot)

---

## 2. Tarefas Técnicas (Severino)

- [ ] **Criar Script de Gestão (`whop_manager.py`):**
    - Funções para criar/editar produtos via API.
    - Funções para criar planos de preço.
    - Funções para gerar cupons de desconto.

- [ ] **Integração com Telegram (`bot_telegram_control.py`):**
    - Adicionar comando `/validar <chave_whop>` no bot.
    - O bot verifica na API da Whop se a chave é válida.
    - Se válida -> Libera acesso ao grupo VIP ou ativa o bot.
    - Se inválida/expirada -> Remove usuário ou bloqueia o bot.

- [ ] **Landing Page (Opcional):**
    - Criar página simples no Dashboard Web (`/comprar`) com os links de checkout da Whop.

---

## 3. Log de Decisões

*   **14/02/2026:** Acesso à API Whop restabelecido (Chave Admin V2).
*   **14/02/2026:** Decisão de NÃO comercializar o bot agora (foco em estabilidade).
*   **14/02/2026:** Início do planejamento estratégico.

---

**Próximos Passos:**
Aguardar instruções de Mariano para avançar na criação dos rascunhos.

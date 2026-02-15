# PLANO DE AÇÃO ESTRATÉGICO - v2.3.1 - RESGATE & REFINE
# Status: EM ELABORAÇÃO

## 1. DIAGNÓSTICO & RESGATE (CRÍTICO)
- [ ] **Criar `check_real_positions.py`**
    - [ ] Consultar API da Bybit (Endpoint `/v5/position/list`) para listar posições ABERTAS.
    - [ ] Consultar processos do sistema (`ps aux | grep bot_executor`) para ver o que está sendo MONITORADO.
    - [ ] Cruzar dados: Identificar "Posições Órfãs" (Abertas na Bybit, sem processo Python).
    - [ ] Exibir relatório claro com PIDs e PnL não realizado.

## 2. REFINAMENTO VISION AI (REDUÇÃO DE FALSOS POSITIVOS)
- [ ] **Ajustar Sensibilidade de Invalidação (`post_entry_validator.py`)**
    - [ ] Aumentar `INVALID_CONFIDENCE_THRESHOLD` de **0.70** para **0.85**.
    - [ ] Implementar Lógica de Confirmação Dupla:
        - Exigir **2 candles consecutivos** com veredito "INVALID" para fechar a posição.
        - Se 1º candle for INVALID, apenas alertar (Warning).
        - Se 2º candle for INVALID, executar fechamento.
    - [ ] Melhorar Prompt do Gemini: Adicionar instrução explícita para tolerar correções naturais (pullbacks) dentro da tendência.

## 3. MECANISMO DE "REANIMAR" ÓRFÃOS
- [ ] **Script de Reataque (`revive_orphans.py`)**
    - [ ] Para cada posição órfã identificada no item 1:
        - [ ] Lançar novo processo `bot_executor.py --symbol MOEDA/USDT`.
        - [ ] O executor deve detectar que JÁ existe posição aberta e entrar direto no modo "Monitoramento" (pular a etapa de compra).

## 4. MELHORIAS DE LOG & OBSERVABILIDADE
- [ ] **Log Centralizado de Invalidações**
    - [ ] Criar `invalidations.log` específico para registrar por que o bot decidiu sair (IA, Stop Loss, Erro).
    - [ ] Incluir URL da imagem analisada (se possível salvar localmente por X tempo).

## 5. VALIDAÇÃO PRÉ-TRADE (WATCHLIST AI)
- [ ] **Implementar IA na Watchlist (`bot_monitor.py` / `vision_validator.py`)**
    - [ ] Antes de entrar no trade, o `bot_monitor.py` deve consultar a IA.
    - [ ] Gerar imagem do padrão detectado.
    - [ ] Enviar para Vision AI validar ("Este padrão é válido e promissor?").
    - [ ] Se IA rejeitar, **REMOVER** da Watchlist (evita trade ruim).
    - [ ] Se IA aprovar, manter e prosseguir para `bot_executor.py`.
    - [ ] **IMPORTANTE:** Manter coleta de dados (`brain_collector`) ativa para treino futuro.

---
*Última atualização: 2026-02-14 03:07 UTC*
*Aguardando validação final.*

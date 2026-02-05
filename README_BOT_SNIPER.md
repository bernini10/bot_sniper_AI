# BOT SNIPER BYBIT v2.0 (Secure & Smart Edition)

Sistema autônomo de trading para futuros na Bybit, focado em padrões gráficos clássicos (OCO, Triângulos, Bandeiras).

## Arquitetura (v2.0)

O sistema opera em 3 módulos independentes orquestrados pelo `bot_manager.py`:

1.  **Scanner (`bot_scanner.py`):**
    *   Varre 30 pares de criptomoedas.
    *   **Inteligência (Fase 2):** Verifica tendência do BTC (EMA 200) e Volume.
    *   Identifica padrões gráficos usando `lib_padroes.py`.
    *   Escreve oportunidades em `watchlist.json`.
    *   *Upgrade v2:* Usa `lib_utils.py` para bloqueio de arquivo (evita crash).

2.  **Monitor (`bot_monitor.py`):**
    *   Lê a `watchlist.json`.
    *   Aguarda o fechamento exato do candle (ex: 15m).
    *   Revalida o padrão. Se confirmado, aciona o Executor.

3.  **Executor (`bot_executor.py`):**
    *   Processo isolado por moeda.
    *   Espera o preço romper o gatilho (Neckline).
    *   Entra a mercado com SL/TP configurados na corretora.
    *   Remove a moeda da watchlist após a entrada para liberar o slot.

## Segurança (Critical Fixes)

*   **File Locking:** Todas as operações de I/O no `watchlist.json` agora usam `fcntl` via `lib_utils.JsonManager`. Isso impede corrupção de dados quando múltiplos processos escrevem simultaneamente.
*   **Gestão de Estado:** O executor remove a si mesmo da watchlist ao entrar no trade ou ao invalidar o padrão.

## Como Rodar

```bash
# Iniciar o sistema completo
cd /root/bot_sniper_bybit
python3 bot_manager.py start

# Ver status
python3 bot_manager.py status

# Parar tudo
python3 bot_manager.py stop
```

## Logs e Debug

*   `manager.log`: Status geral dos processos.
*   `scanner_bybit.log`: Atividade do scanner e detecção de padrões.
*   `monitor_bybit.log`: Validação de candle e disparos.
*   `executor_bybit.log`: Execução de ordens e gestão de posição.

## Manutenção

Ao editar, respeite:
1.  **NUNCA** use `open('watchlist.json', 'w')` diretamente. Use `JsonManager`.
2.  Mantenha a lógica de reinicialização no `bot_manager.py`.

---
*Assinado: Severino (v2.0 Refactor)*

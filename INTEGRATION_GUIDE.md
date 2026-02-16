# 🧠 GUIA DE INTEGRAÇÃO DO SISTEMA DE APRENDIZADO

## VISÃO GERAL
O sistema de aprendizado end-to-end está pronto para integrar com o Bot Sniper Bybit.
Ele adiciona decisão inteligente baseada em aprendizado por reforço (Q-Learning).

## COMPONENTES PRINCIPAIS

1. **brain_trainer.py** - Sistema de Q-Learning
2. **brain_integration.py** - Ponte entre bot e cérebro
3. **brain_config.json** - Configurações
4. **sniper_brain.db** - Database com dados de aprendizado

## COMO INTEGRAR

### 1. MODIFICAÇÃO NO bot_monitor.py

Localize a função `monitorar_watchlist()` (por volta da linha 130) onde ocorre o gatilho:

```python
# ANTES:
if acionar_gatilho:
    disparar_trade(wl, real_idx, preco_atual)

# DEPOIS:
if acionar_gatilho:
    # Importar brain integration
    from brain_integration import BrainIntegration
    
    # Inicializar (fazer uma vez no início)
    brain = BrainIntegration()
    brain.initialize()
    
    # Consultar o cérebro
    brain_decision = brain.should_enter_trade(par)
    
    if brain_decision['decision'] == 'ENTER':
        disparar_trade(wl, real_idx, preco_atual)
        
        # Registrar decisão para tracking
        par['brain_decision'] = brain_decision
        watchlist_mgr.write(wl)
        
        logger.info(f"🧠 Brain APROVOU entrada: {brain_decision['reason']}")
    else:
        logger.info(f"🧠 Brain REJEITOU entrada: {brain_decision['reason']}")
        
        # Opcional: remover do watchlist se brain rejeitar
        # remove_par_watchlist(wl, real_idx, brain_decision['reason'], ...)
```

### 2. REGISTRAR RESULTADOS DOS TRADES

No executor ou monitor, após fechar um trade:

```python
from brain_integration import BrainIntegration

brain = BrainIntegration()

trade_data = {
    'symbol': symbol,
    'entry_price': entry_price,
    'exit_price': exit_price,
    'entry_time': entry_timestamp,
    'exit_time': exit_timestamp,
    'direction': direction,
    'profit_pct': profit_percent,
    'pattern': pattern_name,
    'timeframe': timeframe,
    'ai_confidence': ai_confidence,
    'brain_decision': brain_decision  # da decisão original
}

brain.record_trade_result(trade_data)
```

### 3. APRENDIZADO CONTÍNUO (OPCIONAL)

Para aprendizado automático em background:

```python
import threading
from brain_integration import BrainIntegration

brain = BrainIntegration()
brain.initialize()

# Iniciar em thread separada
learning_thread = threading.Thread(
    target=brain.continuous_learning,
    args=(60,),  # intervalo em minutos
    daemon=True
)
learning_thread.start()
```

## CONFIGURAÇÃO

Edite `brain_config.json` para ajustar:

- `decision_threshold`: Confiança mínima para entrar (0.0-1.0)
- `epsilon`: Taxa de exploração vs exploração
- `continuous_learning_interval_minutes`: Frequência de treinamento

## MONITORAMENTO

Verifique estatísticas:

```python
from brain_integration import BrainIntegration

brain = BrainIntegration()
stats = brain.get_brain_stats()

print(f"Estados aprendidos: {stats['states']}")
print(f"Win rate: {stats['win_rate']:.2%}")
print(f"Recompensa total: {stats['total_reward']:.2f}")
```

## FALLBACK

Se o sistema falhar, automaticamente usa:
1. Validação da Vision AI (existente)
2. Regras matemáticas (existente)

## PRÓXIMOS PASSOS

1. Integrar com `bot_monitor.py`
2. Adicionar registro de trades no `bot_executor.py`
3. Configurar aprendizado contínuo
4. Monitorar performance vs sistema antigo

## SUPORTE

O sistema é compatível com a arquitetura atual e NÃO quebra funcionalidades existentes.
Teste primeiro em modo de observação antes de ativar decisões reais.

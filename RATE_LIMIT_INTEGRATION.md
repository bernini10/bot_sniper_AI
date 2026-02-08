# 🔌 INTEGRAÇÃO DO RATE LIMITER

**Como integrar o rate limiter nos bots existentes**  
**Severino - 2026-02-08**

---

## 📦 ARQUIVO CRIADO

```
/root/bot_sniper_bybit/rate_limiter.py
```

✅ **Testado e funcional**

---

## 🛠️ INTEGRAÇÃO NOS BOTS

### 1. bot_executor.py

**Localização da mudança:** Linha ~130 (antes de `fetch_balance` e `fetch_ticker`)

```python
# === ADICIONAR NO TOPO DO ARQUIVO ===
from rate_limiter import get_rate_limiter

# === ADICIONAR NO __init__ da classe ExecutorBybit ===
class ExecutorBybit:
    def __init__(self, target_symbol, order_data):
        # ... código existente ...
        
        # Rate limiter compartilhado
        self.rate_limiter = get_rate_limiter(max_calls_per_minute=100)

    # === MODIFICAR MÉTODO execute_trade (linha ~125) ===
    def execute_trade(self):
        try:
            # Rate limiting ANTES de qualquer API call
            self.rate_limiter.wait_if_needed(bot_name=f"executor-{self.target_symbol}")
            
            bal = self.exchange.fetch_balance()
            
            self.rate_limiter.wait_if_needed(bot_name=f"executor-{self.target_symbol}")
            ticker = self.exchange.fetch_ticker(self.target_symbol_final)
            
            # ... resto do código ...
```

### 2. bot_monitor.py

**Localização:** Linha ~170 (loop principal)

```python
# === ADICIONAR NO TOPO ===
from rate_limiter import get_rate_limiter

# === ADICIONAR NO __init__ ===
class MonitorBybit:
    def __init__(self):
        # ... código existente ...
        self.rate_limiter = get_rate_limiter(max_calls_per_minute=100)

    # === MODIFICAR run() - linha ~170 ===
    def run(self):
        while True:
            try:
                # Rate limiting antes de fetch
                self.rate_limiter.wait_if_needed(bot_name="monitor")
                
                # ... fetch de dados ...
                time.sleep(20)  # Já ajustado para 20s
```

### 3. bot_scanner.py

**Localização:** Similar ao monitor

```python
# === ADICIONAR NO TOPO ===
from rate_limiter import get_rate_limiter

# === NO __init__ ===
self.rate_limiter = get_rate_limiter(max_calls_per_minute=100)

# === ANTES DE CADA exchange.fetch_* ===
self.rate_limiter.wait_if_needed(bot_name="scanner")
```

---

## 🎯 APLICAÇÃO RÁPIDA (AUTOMÁTICA)

**⚠️ ATENÇÃO:** Não vou aplicar automaticamente para não quebrar código em produção.  
**Recomendação:** Aplicar durante próxima janela de manutenção.

Se quiser aplicar agora, posso gerar os patches com `sed` cirúrgico.

---

## 📊 MONITORAMENTO DO RATE LIMITER

### Comando de Verificação

```bash
# Ver estatísticas em tempo real
cd /root/bot_sniper_bybit && python3 -c "
from rate_limiter import get_rate_limiter
import json
limiter = get_rate_limiter()
print(json.dumps(limiter.get_stats(), indent=2))
"
```

**Saída esperada:**
```json
{
  "calls_last_minute": 8,
  "max_calls": 100,
  "usage_percent": 8.0,
  "available_calls": 92,
  "timestamp": "2026-02-08T13:50:00"
}
```

### Alertas a Monitorar

- **usage_percent > 80%** → Considerar aumentar intervalos
- **usage_percent > 95%** → CRÍTICO, rate limit iminente

---

## 🚀 BENEFÍCIOS

1. **Proteção Global:** Todos os bots compartilham o mesmo limiter
2. **Persistência:** Estado mantido em `/tmp/bybit_rate_limiter.json`
3. **Thread-Safe:** Lock garante sincronização entre processos
4. **Auto-Regulação:** Bots aguardam automaticamente quando próximo do limite
5. **Transparente:** Logs informativos quando aguarda

---

## 🔄 ROLLBACK (Se necessário)

```bash
# Restaurar versões antigas
cp /root/bot_sniper_bybit/bot_executor.py.backup_ratelimit_* /root/bot_sniper_bybit/bot_executor.py
cp /root/bot_sniper_bybit/bot_monitor.py.backup_ratelimit_* /root/bot_sniper_bybit/bot_monitor.py

# Reiniciar
systemctl restart bot-sniper-bybit.service
```

---

## ✅ STATUS ATUAL (SEM INTEGRAÇÃO)

**Proteções já aplicadas:**
- ✅ Bots duplicados eliminados
- ✅ Intervalos aumentados (15s → 30s, 10s → 20s)
- ✅ Rate total reduzido de 32 → 11 req/min (-66%)

**Próximo passo (opcional):**
- ⏳ Integrar rate_limiter.py para proteção adicional

---

**Última Atualização:** 2026-02-08 13:50 UTC

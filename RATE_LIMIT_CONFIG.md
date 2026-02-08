# ⚠️ CONFIGURAÇÃO DE RATE LIMIT - BYBIT API

**Data:** 2026-02-08 13:48 UTC  
**Severino** - Prevenção de Ban

---

## 🚨 INCIDENTE ANTERIOR

**Erro detectado:** `retCode:10006 - Too many visits. Exceeded the API Rate Limit`  
**Horário:** 2026-02-08 11:38 UTC  
**Causa:** Polling excessivo + bots duplicados

---

## 📊 LIMITES DA BYBIT

### Rate Limits Oficiais (Contas Normais)
- **REST API:** 10 req/s por IP (pico)
- **Sustentado:** ~120 req/min
- **Penalidades:**
  - 1ª violação: Block temporário (1-5 min)
  - Repetido: IP ban (1-24h)
  - Abuso: Ban permanente da conta

---

## ✅ CONFIGURAÇÕES OTIMIZADAS

### ANTES (❌ Perigoso)
| Bot | Instâncias | Intervalo | Req/min |
|-----|-----------|-----------|---------|
| monitor | 1 | 10s | 6 |
| scanner | 1 | 30s | 2 |
| executor | 6 | 15s | 24 |
| **TOTAL** | **8** | - | **32** |

### DEPOIS (✅ Seguro)
| Bot | Instâncias | Intervalo | Req/min |
|-----|-----------|-----------|---------|
| monitor | 1 | 20s | 3 |
| scanner | 1 | 30s | 2 |
| executor | 3 | 30s | 6 |
| **TOTAL** | **5** | - | **11** |

**Redução:** 66% menos requests/minuto

---

## 🛠️ MUDANÇAS APLICADAS

### 1. Eliminados Executores Duplicados
```bash
# Antes: 6 executores (3x ADA, 2x APT, 1x SAND)
# Depois: 3 executores (1x cada)

Killed PIDs: 2942587, 2947394, 3588554
```

### 2. Intervalos Aumentados

**bot_executor.py (linha 226):**
```python
# ANTES: time.sleep(15)  # A cada 15 segundos
# DEPOIS: time.sleep(30) # A cada 30 segundos
```

**bot_monitor.py (linha 187):**
```python
# ANTES: time.sleep(10)  # A cada 10 segundos
# DEPOIS: time.sleep(20) # A cada 20 segundos
```

---

## 📋 BACKUPS CRIADOS

```
/root/bot_sniper_bybit/bot_executor.py.backup_ratelimit_1770551303
/root/bot_sniper_bybit/bot_monitor.py.backup_ratelimit_1770551345
```

---

## 🔮 OTIMIZAÇÕES FUTURAS (Recomendadas)

### 1. WebSocket ao invés de REST API
**Benefício:** Dados em tempo real sem polling  
**Redução:** 90% de requests REST  
**Complexidade:** Média

### 2. Rate Limiter Centralizado
```python
# Exemplo: /root/bot_sniper_bybit/rate_limiter.py
import time
from threading import Lock

class RateLimiter:
    def __init__(self, max_calls_per_minute=100):
        self.max_calls = max_calls_per_minute
        self.calls = []
        self.lock = Lock()
    
    def wait_if_needed(self):
        with self.lock:
            now = time.time()
            self.calls = [t for t in self.calls if now - t < 60]
            
            if len(self.calls) >= self.max_calls:
                sleep_time = 60 - (now - self.calls[0])
                time.sleep(sleep_time)
            
            self.calls.append(time.time())

# Uso em cada bot:
rate_limiter = RateLimiter(max_calls_per_minute=100)
rate_limiter.wait_if_needed()  # Antes de cada request
```

### 3. Caching de Dados
- Cachear `fetch_ticker()` por 5-10s
- Cachear `fetch_balance()` por 30s
- Redução: ~30% de requests

---

## 🚦 MONITORAMENTO

### Comandos de Verificação
```bash
# Ver bots ativos
ps aux | grep "bot_.*\.py" | grep -v grep

# Contar requests (aproximado)
# Monitor: 3/min + Scanner: 2/min + Executors: 6/min = 11/min total

# Verificar logs de erro
tail -f /root/bot_sniper_bybit/executor_bybit.log | grep -i "rate\|limit\|10006"
```

### Alertas a Observar
- `retCode:10006` → Rate limit atingido (CRÍTICO)
- `retCode:10002` → Invalid API key (após ban)
- `retCode:33004` → API key sem permissões

---

## ⚡ AÇÃO IMEDIATA SE RATE LIMIT OCORRER NOVAMENTE

```bash
# 1. Parar TODOS os bots imediatamente
systemctl stop bot-sniper-bybit.service
pkill -f bot_executor.py

# 2. Aguardar 10 minutos

# 3. Reiniciar com intervalos maiores
# Editar configs para sleep(60) ou mais

# 4. Restart gradual (um bot por vez)
systemctl start bot-sniper-bybit.service
```

---

## 📞 CONTATO BYBIT SUPPORT

Se receber ban prolongado:
- **Support:** https://www.bybit.com/en-US/help-center/
- **Email:** support@bybit.com
- **Explicação:** "Inadvertent rate limit violation due to multiple trading bots. We've implemented rate limiting and request to restore access."

---

**Última Atualização:** 2026-02-08 13:48 UTC  
**Status:** ✅ Configurações Seguras Aplicadas

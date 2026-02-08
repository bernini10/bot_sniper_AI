"""
Rate Limiter Centralizado para Bybit API
Severino - 2026-02-08

Previne violações de rate limit distribuindo requests entre múltiplos bots.
"""

import time
import json
import os
from threading import Lock
from datetime import datetime

class RateLimiter:
    """
    Rate limiter thread-safe para uso compartilhado entre bots.
    Mantém histórico em arquivo JSON para persistência entre restarts.
    """
    
    def __init__(self, max_calls_per_minute=100, state_file="/tmp/bybit_rate_limiter.json"):
        self.max_calls = max_calls_per_minute
        self.state_file = state_file
        self.lock = Lock()
        self.calls = self._load_state()
    
    def _load_state(self):
        """Carrega histórico de chamadas do arquivo"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    # Remove chamadas antigas (>60s)
                    now = time.time()
                    return [t for t in data.get('calls', []) if now - t < 60]
        except:
            pass
        return []
    
    def _save_state(self):
        """Salva histórico em arquivo"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({'calls': self.calls, 'last_update': time.time()}, f)
        except:
            pass
    
    def wait_if_needed(self, bot_name="unknown"):
        """
        Aguarda se necessário antes de fazer request.
        Retorna True se teve que esperar, False caso contrário.
        """
        with self.lock:
            now = time.time()
            
            # Remove chamadas antigas (>60s)
            self.calls = [t for t in self.calls if now - t < 60]
            
            # Verifica se atingiu limite
            if len(self.calls) >= self.max_calls:
                oldest_call = self.calls[0]
                sleep_time = 60 - (now - oldest_call) + 0.1  # +100ms de margem
                
                print(f"⚠️ [{bot_name}] Rate limit atingido ({len(self.calls)}/{self.max_calls}). "
                      f"Aguardando {sleep_time:.1f}s...")
                
                time.sleep(sleep_time)
                
                # Limpa calls antigas após aguardar
                now = time.time()
                self.calls = [t for t in self.calls if now - t < 60]
            
            # Registra nova chamada
            self.calls.append(time.time())
            self._save_state()
            
            return len(self.calls) >= self.max_calls * 0.9  # Warning se >90%
    
    def get_stats(self):
        """Retorna estatísticas de uso"""
        with self.lock:
            now = time.time()
            self.calls = [t for t in self.calls if now - t < 60]
            
            return {
                'calls_last_minute': len(self.calls),
                'max_calls': self.max_calls,
                'usage_percent': (len(self.calls) / self.max_calls) * 100,
                'available_calls': self.max_calls - len(self.calls),
                'timestamp': datetime.now().isoformat()
            }
    
    def reset(self):
        """Reset manual do rate limiter (emergência)"""
        with self.lock:
            self.calls = []
            self._save_state()


# Singleton global para uso compartilhado
_global_limiter = None

def get_rate_limiter(max_calls_per_minute=100):
    """
    Retorna instância singleton do rate limiter.
    Todos os bots compartilham o mesmo limiter.
    """
    global _global_limiter
    if _global_limiter is None:
        _global_limiter = RateLimiter(max_calls_per_minute=max_calls_per_minute)
    return _global_limiter


# === EXEMPLO DE USO ===
if __name__ == "__main__":
    # Teste básico
    limiter = get_rate_limiter(max_calls_per_minute=10)
    
    print("Testando rate limiter (10 req/min)...")
    for i in range(15):
        warned = limiter.wait_if_needed(bot_name="test")
        stats = limiter.get_stats()
        
        print(f"Request #{i+1}: {stats['calls_last_minute']}/{stats['max_calls']} "
              f"({stats['usage_percent']:.1f}% uso)")
        
        if warned:
            print("  ⚠️ Próximo do limite!")
        
        time.sleep(0.5)
    
    print("\nEstatísticas finais:")
    print(json.dumps(limiter.get_stats(), indent=2))

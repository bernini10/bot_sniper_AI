"""
Módulo de Fallback para API Gemini
Tenta API primária, se falhar, usa backup automaticamente
"""
import os
import json
import logging
import google.generativeai as genai
from typing import Optional, Tuple

logger = logging.getLogger("GeminiFallback")

CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'api_keys_config.json')

class GeminiFallback:
    def __init__(self):
        self.config = self._load_config()
        self.current_key = self.config['gemini_api_keys']['last_used'] or 'primary'
        self.failure_count = 0
        
    def _load_config(self):
        """Carregar configuração de API keys"""
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            # Configuração padrão se arquivo não existir
            return {
                "gemini_api_keys": {
                    "primary": os.getenv('GOOGLE_API_KEY', ''),
                    "backup": None,
                    "rotation_enabled": False,
                    "max_failures_before_switch": 3,
                    "last_used": "primary",
                    "last_switch_time": None
                }
            }
    
    def _save_config(self):
        """Salvar configuração atualizada"""
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Erro ao salvar config: {e}")
    
    def get_current_key(self) -> Optional[str]:
        """Obter API key atual"""
        keys = self.config['gemini_api_keys']
        
        if self.current_key == 'primary':
            return keys['primary']
        elif self.current_key == 'backup' and keys['backup']:
            return keys['backup']
        
        # Fallback para .env se nada funcionar
        return os.getenv('GOOGLE_API_KEY', '')
    
    def switch_to_backup(self):
        """Mudar para API key de backup"""
        if self.config['gemini_api_keys']['backup']:
            logger.warning(f"🔀 Alternando API key: {self.current_key} -> backup")
            self.current_key = 'backup'
            self.config['gemini_api_keys']['last_used'] = 'backup'
            self.config['gemini_api_keys']['last_switch_time'] = '2026-02-17T22:40:00Z'
            self._save_config()
            return True
        return False
    
    def switch_to_primary(self):
        """Voltar para API key primária"""
        logger.info(f"🔀 Retornando para API key primária")
        self.current_key = 'primary'
        self.config['gemini_api_keys']['last_used'] = 'primary'
        self._save_config()
        return True
    
    def record_failure(self, error_msg: str):
        """Registrar falha na API atual"""
        self.failure_count += 1
        logger.warning(f"📉 Falha #{self.failure_count} na API {self.current_key}: {error_msg[:100]}")
        
        # Verificar se deve alternar
        if (self.config['gemini_api_keys']['rotation_enabled'] and 
            self.failure_count >= self.config['gemini_api_keys']['max_failures_before_switch']):
            
            if self.current_key == 'primary':
                return self.switch_to_backup()
        
        return False
    
    def record_success(self):
        """Registrar sucesso - resetar contador de falhas"""
        if self.failure_count > 0:
            logger.info(f"✅ Sucesso na API {self.current_key} - resetando contador de falhas")
            self.failure_count = 0
    
    def configure_genai(self):
        """Configurar genai com a key atual"""
        api_key = self.get_current_key()
        if not api_key:
            raise ValueError("Nenhuma API key disponível")
        
        genai.configure(api_key=api_key)
        return api_key
    
    def test_connection(self) -> Tuple[bool, str]:
        """Testar conexão com a API atual"""
        try:
            api_key = self.configure_genai()
            
            # Listar modelos para testar conexão
            models = list(genai.list_models())
            gemini_count = sum(1 for m in models if 'gemini' in m.name.lower())
            
            self.record_success()
            return True, f"✅ API {self.current_key} funcionando ({gemini_count} modelos Gemini)"
            
        except Exception as e:
            error_msg = str(e)
            should_switch = self.record_failure(error_msg)
            
            if should_switch:
                return False, f"❌ API {self.current_key} falhou - alternado para backup"
            else:
                return False, f"❌ API {self.current_key} falhou: {error_msg[:100]}"

# Instância global
fallback = GeminiFallback()

def get_gemini_fallback():
    """Obter instância do fallback"""
    return fallback

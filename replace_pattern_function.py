#!/usr/bin/env python3
"""
Substitui a função get_pattern_info_for_symbol no dashboard_server.py
"""
import re

# Ler a função corrigida
with open('/root/bot_sniper_bybit/get_pattern_info_fixed.py', 'r') as f:
    new_function = f.read()

# Ler o arquivo original
with open('/root/bot_sniper_bybit/dashboard_server.py', 'r') as f:
    content = f.read()

# Encontrar e substituir a função
# Padrão: da linha "def get_pattern_info_for_symbol(symbol):" até "def get_vision_ai_status"
pattern = r'(def get_pattern_info_for_symbol\(symbol\):.*?)(?=\n\s*def get_vision_ai_status|\n\s*def get_)'

# Usar DOTALL para capturar múltiplas linhas
new_content = re.sub(pattern, new_function + '\n\n', content, flags=re.DOTALL)

# Escrever de volta
with open('/root/bot_sniper_bybit/dashboard_server.py', 'w') as f:
    f.write(new_content)

print("✅ Função substituída com sucesso!")
print(f"Tamanho original: {len(content)} caracteres")
print(f"Tamanho novo: {len(new_content)} caracteres")
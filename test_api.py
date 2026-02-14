#!/usr/bin/env python3
import sys
sys.path.insert(0, '/root/bot_sniper_bybit')

from dashboard_server import stats
import json

print("🧪 TESTE DA FUNÇÃO stats() DO FLASK")
print("═══════════════════════════════════════════════════")

result = stats()
data = json.loads(result.get_data(as_text=True))

print("\n📊 RESULTADO:")
print(json.dumps(data, indent=2))

print("\n═══════════════════════════════════════════════════")

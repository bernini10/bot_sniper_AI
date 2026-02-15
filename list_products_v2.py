import requests

# Configurações
API_KEY = None
try:
    with open('/root/bot_sniper_bybit/whop_config.env', 'r') as f:
        content = f.read().strip()
        if '=' in content:
            API_KEY = content.split('=')[1].strip()
except: pass

if not API_KEY:
    print("ERRO: API Key não encontrada")
    exit(1)

# Endpoint: V2 (que funcionou)
url = "https://api.whop.com/api/v2/products"
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "Accept": "application/json"
}

print(f"📦 WHOP V2 PRODUCTS (Key: {API_KEY[:10]}...)\n")

try:
    resp = requests.get(url, headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        items = data.get('data', [])
        
        print(f"✅ Encontrados {len(items)} produtos:\n")
        
        for p in items:
            print(f"🔹 [{p['id']}] {p.get('name', 'Sem Nome')}")
            print(f"   Visibilidade: {p.get('visibility', 'N/A')}")
            
            # Detalhes extras se houver
            if p.get('experiences'):
                print(f"   Experiências: {len(p['experiences'])}")
                
            # Listar Planos deste Produto (V2)
            try:
                url_plans = f"https://api.whop.com/api/v2/plans?product_id={p['id']}"
                resp_plans = requests.get(url_plans, headers=headers)
                
                if resp_plans.status_code == 200:
                    plans = resp_plans.json().get('data', [])
                    if plans:
                        print(f"   💰 Planos ({len(plans)}):")
                        for plan in plans:
                            nome = plan.get('internal_notes') or plan.get('id')
                            tipo = plan.get('plan_type', 'N/A')
                            
                            # Preço Inicial (se houver)
                            preco = "Grátis"
                            if plan.get('initial_price'):
                                preco = f"${plan['initial_price']}"
                            elif plan.get('renewal_price'):
                                preco = f"${plan['renewal_price']}/mês"
                                
                            print(f"      - {nome} ({tipo}) -> {preco}")
                    else:
                        print("   💰 Sem planos.")
                else:
                    print(f"   ⚠️ Erro ao listar planos: {resp_plans.status_code}")
            except Exception as ep:
                print(f"   (Erro planos: {ep})")
            
            print("-" * 30)
            
    else:
        print(f"❌ Erro ao listar produtos: {resp.status_code} - {resp.text}")

except Exception as e:
    print(f"❌ Erro Geral: {e}")

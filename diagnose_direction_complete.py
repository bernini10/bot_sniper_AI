#!/usr/bin/env python3
"""
Diagnóstico completo do problema de direção
"""
import json
import os
import re

print("🎯 DIAGNÓSTICO COMPLETO - PROBLEMA DE DIREÇÃO")
print("=" * 60)

def check_watchlist():
    """Verificar watchlist"""
    print("\n1. 📊 VERIFICANDO WATCHLIST:")
    print("-" * 40)
    
    try:
        with open('watchlist.json', 'r') as f:
            watchlist = json.load(f)
        
        pares = watchlist.get('pares', [])
        
        if pares:
            print(f"✅ {len(pares)} pares no watchlist")
            
            # Mapeamento esperado
            mapping = {
                'TOPO_DUPLO': 'SHORT',
                'FUNDO_DUPLO': 'LONG',
                'TOPO_TRIPLO': 'SHORT',
                'FUNDO_TRIPLO': 'LONG',
                'CABEÇA_OMBROS': 'SHORT',
                'CABEÇA_OMBROS_INVERTIDO': 'LONG',
                'TRIANGULO_ASCENDENTE': 'LONG',
                'TRIANGULO_DESCENDENTE': 'SHORT',
                'BANDEIRA_ALTA': 'LONG',
                'BANDEIRA_BAIXA': 'SHORT',
                'CUNHA_ASCENDENTE': 'SHORT',
                'CUNHA_DESCENDENTE': 'LONG',
                'OCO': 'SHORT',
                'OCO_INVERTIDO': 'LONG'
            }
            
            errors = []
            for par in pares:
                symbol = par.get('symbol', 'N/A')
                padrao = par.get('padrao', 'N/A')
                direcao = par.get('direcao', 'N/A')
                
                expected = mapping.get(padrao)
                if expected:
                    if expected != direcao:
                        errors.append(f"   ❌ {symbol}: {padrao} → Esperado: {expected}, Atual: {direcao}")
                    else:
                        print(f"   ✅ {symbol}: {padrao} → {direcao} (correto)")
                else:
                    print(f"   ⚠️  {symbol}: {padrao} → {direcao} (padrão não mapeado)")
            
            if errors:
                print("\n⚠️  PROBLEMAS NO WATCHLIST:")
                for error in errors:
                    print(error)
            else:
                print("\n✅ Watchlist correto")
                
        else:
            print("ℹ️  Watchlist vazio")
            
    except Exception as e:
        print(f"❌ Erro ao verificar watchlist: {e}")

def check_dashboard_code():
    """Verificar código do dashboard"""
    print("\n2. 🖥️ VERIFICANDO CÓDIGO DO DASHBOARD:")
    print("-" * 40)
    
    try:
        with open('dashboard_server.py', 'r') as f:
            content = f.read()
        
        # Buscar onde side é definida
        print("🔍 Buscando definição de 'side' no código...")
        
        # Padrão: 'side': ... 
        side_pattern = r"'side'\s*:\s*([^,}\n]+)"
        matches = re.findall(side_pattern, content)
        
        if matches:
            print(f"📍 {len(matches)} definições de 'side' encontradas:")
            for i, match in enumerate(matches[:3]):  # Mostrar apenas 3
                print(f"   {i+1}. 'side': {match.strip()}")
                
                # Verificar se retorna maiúsculo ou minúsculo
                if 'LONG' in match and 'SHORT' in match:
                    print(f"     → Retorna 'LONG'/'SHORT' (maiúsculo)")
                elif 'long' in match.lower() and 'short' in match.lower():
                    print(f"     → Retorna 'long'/'short' (minúsculo)")
        
        # Verificar linha 394 específica
        lines = content.split('\n')
        if len(lines) > 393:
            line_394 = lines[393]
            print(f"\n📍 LINHA 394 ESPECÍFICA:")
            print(f"   {line_394.strip()}")
            
            # Analisar
            if "'LONG'" in line_394 and "'SHORT'" in line_394:
                print(f"   ✅ Retorna 'LONG'/'SHORT' (maiúsculo)")
            elif "'long'" in line_394 and "'short'" in line_394:
                print(f"   ⚠️  Retorna 'long'/'short' (minúsculo)")
            else:
                print(f"   ❌ Não identificado")
                
    except Exception as e:
        print(f"❌ Erro ao verificar código: {e}")

def check_template():
    """Verificar template"""
    print("\n3. 🎨 VERIFICANDO TEMPLATE DASHBOARD:")
    print("-" * 40)
    
    try:
        with open('templates/dashboard.html', 'r') as f:
            content = f.read()
        
        # Verificar como side é usado
        print("🔍 Como 'side' é usado no template:")
        
        # Buscar ocorrências
        side_occurrences = re.findall(r'\{\{.*?[Ss]ide.*?\}\}', content)
        
        if side_occurrences:
            print(f"📍 {len(side_occurrences)} usos de side no template:")
            for i, occ in enumerate(side_occurrences[:5]):
                print(f"   {i+1}. {occ}")
                
                # Verificar se converte case
                if '.toUpperCase()' in occ:
                    print(f"     → Converte para MAIÚSCULO")
                elif '.toLowerCase()' in occ:
                    print(f"     → Converte para minúsculo")
                elif '.toLowerCase' in occ:
                    print(f"     → Converte para minúsculo")
                elif '.toUpperCase' in occ:
                    print(f"     → Converte para MAIÚSCULO")
        
        # Verificar JavaScript que processa side
        print("\n🔍 JavaScript que processa side:")
        js_pattern = r'[Ss]ide.*?=.*?[\'"]'
        js_matches = re.findall(js_pattern, content)
        
        for match in js_matches[:3]:
            print(f"   • {match[:50]}...")
            
    except Exception as e:
        print(f"❌ Erro ao verificar template: {e}")

def check_actual_data():
    """Verificar dados reais"""
    print("\n4. 📈 VERIFICANDO DADOS REAIS DO DASHBOARD:")
    print("-" * 40)
    
    import requests
    
    try:
        # Tentar acessar API
        response = requests.get('http://localhost:8080/api/stats', timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            print("✅ Dados obtidos do dashboard")
            
            if 'open_positions' in data:
                positions = data['open_positions']
                
                print(f"\n📊 {len(positions)} posições abertas:")
                for pos in positions:
                    symbol = pos.get('symbol', 'N/A')
                    side = pos.get('side', 'N/A')
                    
                    print(f"   • {symbol}: side='{side}'")
                    
                    # Verificar case
                    if side == 'SHORT':
                        print(f"     ✅ 'SHORT' (maiúsculo)")
                    elif side == 'short':
                        print(f"     ⚠️  'short' (minúsculo)")
                    elif side == 'LONG':
                        print(f"     ✅ 'LONG' (maiúsculo)")
                    elif side == 'long':
                        print(f"     ⚠️  'long' (minúsculo)")
                    else:
                        print(f"     ❌ '{side}' (formato desconhecido)")
            else:
                print("ℹ️  Nenhuma posição aberta")
        else:
            print(f"❌ API retornou status {response.status_code}")
            
    except Exception as e:
        print(f"❌ Erro ao acessar dashboard: {e}")

def main():
    """Função principal"""
    print("🔍 INICIANDO DIAGNÓSTICO COMPLETO...")
    
    check_watchlist()
    check_dashboard_code()
    check_template()
    check_actual_data()
    
    print("\n🎯 CONCLUSÃO DO DIAGNÓSTICO:")
    print("=" * 60)
    print("1. Watchlist: Verificar mapeamento padrão→direção")
    print("2. Dashboard: Verificar se retorna 'LONG'/'SHORT' ou 'long'/'short'")
    print("3. Template: Verificar se converte case")
    print("4. Dados reais: Verificar formato atual")
    print("")
    print("🚀 PRÓXIMOS PASSOS:")
    print("   • Corrigir case no dashboard_server.py")
    print("   • Verificar template")
    print("   • Testar com dados reais")

if __name__ == "__main__":
    main()

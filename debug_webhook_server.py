#!/usr/bin/env python3
"""
Debug server para ver como o TradingView envia dados
"""

from flask import Flask, request, jsonify
import json
import time
from datetime import datetime

app = Flask(__name__)

@app.route('/debug/webhook', methods=['POST', 'GET'])
def debug_webhook():
    """Endpoint de debug para ver headers e dados"""
    print("\n" + "="*60)
    print(f"📨 REQUISIÇÃO RECEBIDA - {datetime.now().isoformat()}")
    print("="*60)
    
    # Headers
    print("📋 HEADERS:")
    for key, value in request.headers:
        print(f"  {key}: {value}")
    
    # Método e URL
    print(f"\n🔧 MÉTODO: {request.method}")
    print(f"📎 URL: {request.url}")
    
    # Dados
    print("\n📦 DADOS (raw):")
    raw_data = request.get_data(as_text=True)
    print(f"  {raw_data[:500]}..." if len(raw_data) > 500 else f"  {raw_data}")
    
    # Tentar parsear JSON
    print("\n🔍 TENTANDO PARSEAR JSON:")
    try:
        if request.is_json:
            json_data = request.get_json()
            print(f"  ✅ JSON válido: {json.dumps(json_data, indent=2)}")
        else:
            # Tentar parsear de qualquer forma
            try:
                json_data = json.loads(raw_data)
                print(f"  ✅ JSON parseado do raw: {json.dumps(json_data, indent=2)}")
            except:
                print("  ❌ Não é JSON válido")
    except Exception as e:
        print(f"  ❌ Erro ao parsear: {e}")
    
    # Form data
    print("\n📝 FORM DATA:")
    print(f"  {dict(request.form)}")
    
    print("\n" + "="*60)
    
    # Responder
    return jsonify({
        "status": "debug_received",
        "timestamp": datetime.now().isoformat(),
        "headers": dict(request.headers),
        "method": request.method,
        "has_json": request.is_json,
        "raw_data_length": len(raw_data),
        "your_ip": request.remote_addr
    })

@app.route('/debug/test', methods=['GET'])
def debug_test():
    """Página de teste simples"""
    return """
    <html>
    <body>
        <h1>Debug Webhook Server</h1>
        <p>Use este endpoint para testar como o TradingView envia dados:</p>
        <ul>
            <li><strong>POST /debug/webhook</strong> - Para ver headers e dados</li>
            <li><strong>GET /debug/test</strong> - Esta página</li>
        </ul>
        <p>Teste com curl:</p>
        <pre>
curl -X POST http://147.182.145.169:5556/debug/webhook \\
  -H "Content-Type: application/json" \\
  -d '{"test": "data"}'
        </pre>
    </body>
    </html>
    """

if __name__ == '__main__':
    print("🚀 Debug Webhook Server iniciando na porta 5556...")
    print("📡 Use para testar como o TradingView envia dados")
    print("🔗 URL: http://147.182.145.169:5556/debug/webhook")
    app.run(host='0.0.0.0', port=5556, debug=True)
#!/usr/bin/env python3
"""
Webhook Server para TradingView
Recebe dados de BTC.D e outros alertas
Severino - 2026-02-08
"""

from flask import Flask, request, jsonify
import json
import os
import time
import logging
from datetime import datetime

# Configuração de logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/bot_sniper_bybit/webhook.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("WebhookServer")

app = Flask(__name__)

# Arquivo onde salva dados do BTC.D
BTCD_FILE = '/root/bot_sniper_bybit/btcd_data.json'

@app.route('/webhook/btcd', methods=['POST'])
def webhook_btcd():
    """
    Recebe dados do BTC.D do TradingView
    
    Formato esperado:
    {
        "btc_d_value": 56.3,
        "direction": "LONG",
        "change_pct": 0.8
    }
    """
    try:
        # TradingView pode mandar de várias formas, vamos tentar todas
        data = None
        
        # Tentar 1: JSON direto
        try:
            data = request.get_json(force=True)
        except:
            pass
        
        # Tentar 2: Corpo como texto (TradingView às vezes manda assim)
        if not data:
            try:
                body = request.get_data(as_text=True)
                if body:
                    data = json.loads(body)
            except:
                pass
        
        # Tentar 3: Form data
        if not data:
            try:
                data = dict(request.form)
                if data:
                    # Se veio como form, pode ter valores em string
                    if 'btc_d_value' in data:
                        data['btc_d_value'] = float(data['btc_d_value'])
                    if 'change_pct' in data:
                        data['change_pct'] = float(data['change_pct'])
            except:
                pass
        
        # Tentar 4: Parsear texto simples do TradingView
        if not data:
            try:
                import re
                raw_data = request.get_data(as_text=True).strip()
                
                # DEBUG: Logar o que chegou
                logger.info(f"🔍 Tentando parsear texto: '{raw_data[:100]}'")
                
                # Padrão 1: "BTC.D: 59.37%, Direction: LONG, Change: 0.50%"
                match1 = re.search(r'BTC\.?D:\s*(\d+[.,]\d+)%?\s*,\s*Direction:\s*(\w+)\s*,\s*Change:\s*([+-]?\d+[.,]\d+)%', raw_data, re.IGNORECASE)
                
                # Padrão 2: "BTC.D 59.37 LONG 0.50%"
                match2 = re.search(r'BTC\.?D\s*(\d+[.,]\d+)%?\s+(\w+)\s+([+-]?\d+[.,]\d+)%', raw_data, re.IGNORECASE)
                
                # Padrão 3: Apenas número (fallback)
                match3 = re.search(r'(\d+[.,]\d+)%', raw_data)
                
                if match1:
                    btcd_val = float(match1.group(1).replace(',', '.'))
                    direction = match1.group(2).upper()
                    change = float(match1.group(3).replace(',', '.'))
                    data = {
                        'btc_d_value': btcd_val,
                        'direction': direction,
                        'change_pct': change,
                        '_parsed_from_text': True
                    }
                    logger.info(f"✅ Webhook parseado de texto (padrão 1): BTC.D={btcd_val}% ({direction}) change={change}%")
                    
                elif match2:
                    btcd_val = float(match2.group(1).replace(',', '.'))
                    direction = match2.group(2).upper()
                    change = float(match2.group(3).replace(',', '.'))
                    data = {
                        'btc_d_value': btcd_val,
                        'direction': direction,
                        'change_pct': change,
                        '_parsed_from_text': True
                    }
                    logger.info(f"✅ Webhook parseado de texto (padrão 2): BTC.D={btcd_val}% ({direction}) change={change}%")
                    
                elif match3:
                    btcd_val = float(match3.group(1).replace(',', '.'))
                    data = {
                        'btc_d_value': btcd_val,
                        'direction': 'NEUTRAL',
                        'change_pct': 0,
                        '_parsed_from_text': True
                    }
                    logger.warning(f"⚠️ Webhook parseado apenas valor: BTC.D={btcd_val}% (direção desconhecida)")
                    
                else:
                    # Logar o que veio para debug
                    logger.warning(f"⚠️ Texto não reconhecido: '{raw_data[:100]}'")
                    # Tentar como fallback: se parece JSON mas com problemas
                    if '{' in raw_data and '}' in raw_data:
                        try:
                            # Tentar corrigir JSON quebrado
                            fixed = raw_data.replace("'", '"')
                            data = json.loads(fixed)
                            logger.info(f"✅ JSON corrigido: {data}")
                        except:
                            pass
                    
            except Exception as e:
                logger.error(f"Erro ao parsear texto: {e}")

        # Se ainda não tem dados, logar o que veio
        if not data:
            raw_data = request.get_data(as_text=True)
            logger.error(f"Não consegui decodificar webhook. Content-Type: {request.content_type}, Body: {raw_data}")
            return jsonify({"error": "Could not decode data", "received": raw_data}), 400
        
        # Validar dados
        if 'btc_d_value' not in data:
            logger.error(f"Dados inválidos recebidos: {data}")
            return jsonify({"error": "Missing btc_d_value"}), 400
        
        # Converter strings para números se necessário
        try:
            if isinstance(data['btc_d_value'], str):
                data['btc_d_value'] = float(data['btc_d_value'].replace(',', '.'))
            if isinstance(data.get('change_pct', 0), str):
                data['change_pct'] = float(data['change_pct'].replace(',', '.'))
        except ValueError as e:
            logger.error(f"Erro ao converter valores: {e}")
            return jsonify({"error": f"Invalid number format: {e}"}), 400
        
        # Adicionar timestamp
        data['timestamp'] = time.time()
        data['datetime'] = datetime.now().isoformat()
        
        # Salvar em arquivo
        with open(BTCD_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"✅ BTC.D atualizado: {data['btc_d_value']}% ({data.get('direction', 'N/A')}) change: {data.get('change_pct', 0):.2f}%")
        
        return jsonify({
            "status": "ok",
            "received": data
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao processar webhook: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de health check"""
    try:
        # Verificar se arquivo existe e tem dados recentes
        if os.path.exists(BTCD_FILE):
            with open(BTCD_FILE, 'r') as f:
                data = json.load(f)
            
            age_seconds = time.time() - data.get('timestamp', 0)
            age_minutes = age_seconds / 60
            
            return jsonify({
                "status": "healthy",
                "btcd_file_exists": True,
                "last_update_minutes_ago": round(age_minutes, 1),
                "last_value": data.get('btc_d_value'),
                "last_direction": data.get('direction')
            }), 200
        else:
            return jsonify({
                "status": "waiting",
                "btcd_file_exists": False,
                "message": "Aguardando primeiro webhook do TradingView"
            }), 200
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

@app.route('/test', methods=['GET', 'POST'])
def test():
    """Endpoint de teste (pode usar para debug)"""
    return jsonify({
        "status": "ok",
        "message": "Webhook server está rodando!",
        "timestamp": datetime.now().isoformat()
    }), 200

if __name__ == '__main__':
    logger.info("🚀 Webhook Server iniciando na porta 5555...")
    app.run(host='0.0.0.0', port=5555, debug=False)

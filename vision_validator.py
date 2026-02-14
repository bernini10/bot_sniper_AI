import sqlite3
import json
import os
import sys
import time
import logging
import google.generativeai as genai
import pandas as pd
import mplfinance as mpf
from dotenv import load_dotenv
from lib_utils import JsonManager 

# Configuração
load_dotenv()
DB_NAME = 'sniper_brain.db'
WATCHLIST_FILE = 'watchlist.json'
IMG_DIR = 'brain_images'
API_KEY = os.getenv('GOOGLE_API_KEY') 

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - VISION - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("vision.log"), logging.StreamHandler(sys.stdout)] 
)
logger = logging.getLogger("VisionValidator")
watchlist_mgr = JsonManager(WATCHLIST_FILE)

if not os.path.exists(IMG_DIR):
    os.makedirs(IMG_DIR)

if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    logger.warning("GOOGLE_API_KEY não configurada")

def get_pending_samples():
    try:
        conn = sqlite3.connect(DB_NAME)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM raw_samples WHERE status = 'PENDING' ORDER BY id ASC LIMIT 5")
        rows = c.fetchall()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Erro DB: {e}")
        return []

def generate_chart_image(sample):
    try:
        data = json.loads(sample['ohlcv_json'])
        df = pd.DataFrame(data, columns=['Date', 'Open', 'High', 'Low', 'Close', 'Volume'])
        df['Date'] = pd.to_datetime(df['Date'], unit='ms')
        df.set_index('Date', inplace=True)
        
        safe_symbol = sample['symbol'].replace('/', '')
        filename = f"{IMG_DIR}/{sample['id']}_{safe_symbol}_{sample['pattern_detected']}.png"
        
        mc = mpf.make_marketcolors(up='#00ff00', down='#ff0000', edge='inherit', wick='inherit', volume='in')
        s  = mpf.make_mpf_style(marketcolors=mc, base_mpf_style='nightclouds')
        
        mpf.plot(df, type='candle', volume=False, style=s, 
                 savefig=dict(fname=filename, dpi=100, bbox_inches='tight'),
                 title=f"{sample['symbol']} - {sample['pattern_detected']}",
                 axisoff=True)
        return filename
    except Exception as e:
        logger.error(f"Erro ao gerar imagem: {e}")
        return None

def consult_oracle(image_path, pattern_name, direction):
    if not API_KEY: 
        logger.warning("API KEY ausente. Pulando consulta.")
        return None
    try:
        from PIL import Image
        
        prompt = f"""
        Atue como um Trader Institucional Sênior.
        Analise a imagem deste gráfico. O sistema detectou um {pattern_name} ({direction}).
        
        Sua missão é validar se esse padrão é tecnicamente válido e se o contexto favorece o trade.
        Seja RIGOROSO. Na dúvida, rejeite.
        
        Responda ESTRITAMENTE neste formato JSON:
        {{
            "verdict": "VALID" ou "INVALID",
            "confidence": 0.0 a 1.0,
            "reasoning": "Explicação técnica breve (max 1 frase)"
        }}
        """
        
        img = Image.open(image_path)
        model = genai.GenerativeModel('gemini-2.0-flash')
        result = model.generate_content([prompt, img])
        
        response_text = result.text.replace('```json', '').replace('```', '').strip()
        return json.loads(response_text)
        
    except Exception as e:
        logger.error(f"Erro na API Vision: {e}")
        return None

def remove_from_watchlist(symbol, reason):
    try:
        wl = watchlist_mgr.read()
        if not wl or 'pares' not in wl: return
        
        initial_len = len(wl['pares'])
        wl['pares'] = [p for p in wl['pares'] if p['symbol'] != symbol]
        
        if len(wl['pares']) < initial_len:
            wl['slots_ocupados'] = len(wl['pares'])
            watchlist_mgr.write(wl)
            logger.info(f"🚫 PAR REMOVIDO DA WATCHLIST: {symbol}. Motivo: {reason}")
    except Exception as e:
        logger.error(f"Erro ao remover da watchlist: {e}")

def update_db(sample_id, ai_result, image_path):
    try:
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute('''
            UPDATE raw_samples 
            SET ai_verdict = ?, ai_confidence = ?, ai_reasoning = ?, image_path = ?, status = 'PROCESSED'
            WHERE id = ?
        ''', (
            ai_result['verdict'], 
            ai_result['confidence'], 
            ai_result['reasoning'], 
            image_path,
            sample_id
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Erro ao atualizar DB: {e}")

def run_loop():
    logger.info("👁️ Vision Validator (Active Mode) Iniciado.")
    while True:
        samples = get_pending_samples()
        
        if not samples:
            time.sleep(5)
            continue
            
        for sample in samples:
            logger.info(f"Analisando ID {sample['id']}: {sample['symbol']}...")
            
            img_path = generate_chart_image(sample)
            if not img_path:
                continue 
                
            ai_result = consult_oracle(img_path, sample['pattern_detected'], sample['direction'])
            
            if ai_result:
                update_db(sample['id'], ai_result, img_path)
                
                if ai_result['verdict'] == 'INVALID':
                    logger.warning(f"❌ REJEITADO PELA IA: {sample['symbol']} (conf: {ai_result['confidence']:.2f}) - {ai_result['reasoning']}")
                    remove_from_watchlist(sample['symbol'], f"Vision AI Reject: {ai_result['reasoning']}")
                else:
                    logger.info(f"✅ APROVADO PELA IA: {sample['symbol']} (conf: {ai_result['confidence']:.2f})")
            
            time.sleep(3) 

if __name__ == "__main__":
    run_loop()

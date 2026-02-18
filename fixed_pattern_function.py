#!/usr/bin/env python3
"""
Função corrigida para buscar padrão em contexto maior
"""
import re
import json
from datetime import datetime

def get_pattern_info_for_symbol_fixed(symbol):
    """Versão FIXADA que busca em contexto maior"""
    try:
        symbol_clean = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
        
        # 1. Buscar em logs com contexto
        log_files = [
            f'/root/TRADING_SYSTEMS/ACTIVE_BOT_SNIPER_BYBIT/executor_{symbol_clean}USDT.log',
            '/root/TRADING_SYSTEMS/ACTIVE_BOT_SNIPER_BYBIT/scanner_bybit.log',
        ]
        
        for log_file in log_files:
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-50:]  # Últimas 50 linhas
                
                # Buscar em todas as linhas que contêm o símbolo
                for i, line in enumerate(lines):
                    if symbol_clean in line.upper():
                        # Verificar esta linha e as próximas 3 linhas para contexto
                        context_lines = lines[i:i+4]
                        context_text = ' '.join(context_lines)
                        
                        # Buscar padrão no contexto
                        pattern_match = None
                        
                        # Tentar diferentes padrões de busca
                        patterns = [
                            r'padr[ao][:\s]+([A-Z_]+)',
                            r'padr[ao]\s+([A-Z_]+)',
                            r'pattern[:\s]+([A-Z_]+)',
                            r'padrão\s+([A-Z_]+)',
                            r'do\s+padrão\s+([A-Z_]+)',
                            r'padrão\s+([A-Z_]+)\s+permanece',
                            r'padrão\s+([A-Z_]+)\s+intacta'
                        ]
                        
                        for pattern_regex in patterns:
                            match = re.search(pattern_regex, context_text, re.IGNORECASE)
                            if match:
                                pattern_match = match
                                break
                        
                        if pattern_match:
                            pattern = pattern_match.group(1)
                            print(f"Found pattern '{pattern}' in {log_file}")
                            
                            # Buscar direção no contexto
                            direction = 'UNKNOWN'
                            direction_match = re.search(r'(SHORT|LONG|BUY|SELL)', context_text, re.IGNORECASE)
                            if direction_match:
                                dir_val = direction_match.group(1).upper()
                                direction = 'SHORT' if dir_val in ['SHORT', 'SELL'] else 'LONG' if dir_val in ['LONG', 'BUY'] else 'UNKNOWN'
                            else:
                                # Inferir direção do padrão
                                if pattern in ['OCO_INVERTIDO', 'FUNDO_DUPLO', 'TRIANGULO_ASCENDENTE', 'CUNHA_ASCENDENTE']:
                                    direction = 'LONG'
                                elif pattern in ['OCO', 'TOPO_DUPLO', 'TRIANGULO_DESCENDENTE', 'CUNHA_DESCENDENTE']:
                                    direction = 'SHORT'
                            
                            # Buscar confiança
                            confidence = 0.0
                            conf_match = re.search(r'conf[:\s]*([0-9.]+)', context_text, re.IGNORECASE)
                            if not conf_match:
                                conf_match = re.search(r'confidence[:\s]*([0-9.]+)', context_text, re.IGNORECASE)
                            if conf_match:
                                confidence = float(conf_match.group(1))
                            
                            # Buscar timeframe
                            timeframe = '15m'
                            tf_match = re.search(r'TF[:\s]*([0-9]+[mh])', context_text, re.IGNORECASE)
                            if not tf_match:
                                tf_match = re.search(r'timeframe[:\s]*([0-9]+[mh])', context_text, re.IGNORECASE)
                            if tf_match:
                                timeframe = tf_match.group(1)
                            
                            return {
                                'pattern': pattern,
                                'direction': direction,
                                'confidence': confidence,
                                'timeframe': timeframe,
                                'source': 'log_execution'
                            }
            except FileNotFoundError:
                continue
            except Exception as e:
                print(f"Error reading {log_file}: {e}")
                continue
        
        # 2. Watchlist (fallback - mas com aviso)
        try:
            with open('/root/bot_sniper_bybit/watchlist.json', 'r') as f:
                watchlist = json.load(f)
            
            for item in watchlist.get('pares', []):
                if item.get('symbol', '').replace('/USDT', '') == symbol_clean:
                    print(f"⚠️  WARNING: Using watchlist data for {symbol_clean} - may be outdated!")
                    return {
                        'pattern': item.get('padrao', 'UNKNOWN'),
                        'direction': item.get('direcao', 'UNKNOWN'),
                        'confidence': item.get('confiabilidade', 0),
                        'timeframe': item.get('timeframe', '15m'),
                        'source': 'watchlist_active_WARNING'
                    }
        except:
            pass
        
        return None
        
    except Exception as e:
        print(f"Error: {e}")
        return None

# Testar
print("🔍 TESTANDO FUNÇÃO CORRIGIDA")
print("=" * 50)

result_xrp = get_pattern_info_for_symbol_fixed('XRP/USDT:USDT')
print(f"\nXRP Result: {json.dumps(result_xrp, indent=2)}")

result_egld = get_pattern_info_for_symbol_fixed('EGLD/USDT:USDT')
print(f"\nEGLD Result: {json.dumps(result_egld, indent=2)}")
def get_pattern_info_for_symbol(symbol):
    """Busca informações de pattern para um símbolo específico - VERSÃO CORRIGIDA"""
    try:
        symbol_clean = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
        
        # 1. PRIMEIRO: Buscar em logs com contexto (MAIS CONFIÁVEL)
        try:
            import re
            from datetime import datetime
            
            log_files = [
                f'/root/TRADING_SYSTEMS/ACTIVE_BOT_SNIPER_BYBIT/executor_{symbol_clean}USDT.log',
                '/root/TRADING_SYSTEMS/ACTIVE_BOT_SNIPER_BYBIT/scanner_bybit.log',
                '/root/bot_sniper_bybit/executor_bybit.log',
                f'/root/bot_sniper_bybit/executor_{symbol_clean}USDT.log'
            ]
            
            for log_file in log_files:
                try:
                    with open(log_file, 'r') as f:
                        lines = f.readlines()[-100:]  # Últimas 100 linhas
                    
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
                                
                                # Buscar direção no contexto
                                direction = 'UNKNOWN'
                                direction_match = re.search(r'(SHORT|LONG|BUY|SELL)', context_text, re.IGNORECASE)
                                if direction_match:
                                    dir_val = direction_match.group(1).upper()
                                    direction = 'SHORT' if dir_val in ['SHORT', 'SELL'] else 'LONG' if dir_val in ['LONG', 'BUY'] else 'UNKNOWN'
                                else:
                                    # Inferir direção do padrão (fallback)
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
                                    'neckline': 0,
                                    'target': 0,
                                    'stop_loss': 0,
                                    'status': 'EXECUTED',
                                    'discovered_at': int(datetime.now().timestamp()),
                                    'source': 'log_execution'
                                }
                except FileNotFoundError:
                    continue
                except:
                    continue
        except:
            pass
        
        # 2. SEGUNDO: Buscar no histórico de trades
        try:
            with open('/root/TRADING_SYSTEMS/ACTIVE_BOT_SNIPER_BYBIT/trades_history.json', 'r') as f:
                trades = json.load(f)
            
            for trade in reversed(trades):
                if trade.get('symbol', '').replace('/USDT', '') == symbol_clean and trade.get('status') == 'OPEN':
                    # Para trades abertos no histórico
                    pattern = 'TOPO_DUPLO' if trade.get('side') == 'SHORT' else 'FUNDO_DUPLO'
                    return {
                        'pattern': pattern,
                        'direction': trade.get('side', 'UNKNOWN'),
                        'confidence': 0.85,
                        'timeframe': '1h',
                        'neckline': 0,
                        'target': 0,
                        'stop_loss': 0,
                        'status': 'OPEN',
                        'discovered_at': int(datetime.now().timestamp()),
                        'source': 'trades_history'
                    }
        except:
            pass
        
        # 3. TERCEIRO: Buscar na watchlist ativa (MENOS CONFIÁVEL - pode estar desatualizada)
        try:
            with open('/root/bot_sniper_bybit/watchlist.json', 'r') as f:
                watchlist = json.load(f)
            
            for item in watchlist.get('pares', []):
                if item.get('symbol', '').replace('/USDT', '') == symbol_clean:
                    return {
                        'pattern': item.get('padrao', 'UNKNOWN'),
                        'direction': item.get('direcao', 'UNKNOWN'),
                        'confidence': item.get('confiabilidade', 0),
                        'timeframe': item.get('timeframe', '15m'),
                        'neckline': item.get('neckline', 0),
                        'target': item.get('target', 0),
                        'stop_loss': item.get('stop_loss', 0),
                        'status': item.get('status', 'UNKNOWN'),
                        'discovered_at': item.get('timestamp_descoberta'),
                        'source': 'watchlist_active_WARNING'
                    }
        except:
            pass
        
        # 4. Fallback
        return {
            'pattern': 'UNKNOWN_PATTERN',
            'direction': 'UNKNOWN',
            'confidence': 0.0,
            'timeframe': 'UNKNOWN',
            'neckline': 0,
            'target': 0,
            'stop_loss': 0,
            'status': 'UNKNOWN',
            'discovered_at': 0,
            'source': 'fallback'
        }
        
    except Exception as e:
        print(f"Error getting pattern info for {symbol}: {e}")
        return None
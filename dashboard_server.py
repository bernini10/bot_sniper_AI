from flask import Flask, render_template, jsonify, send_from_directory
import json
import os
import ccxt
import time
import sqlite3
from datetime import datetime, timedelta
from lib_utils import JsonManager

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Helper function for safe float conversion
def safe_float(value, default=0):
    """Safely convert value to float, returning default if None or invalid"""
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default

# Configs
WATCHLIST_FILE = os.path.join(BASE_DIR, 'watchlist.json')
HISTORY_FILE = os.path.join(BASE_DIR, 'trades_history.json')
CLOSED_PNL_CACHE = os.path.join(BASE_DIR, 'closed_pnl_cache.json')
CACHE_MAX_AGE = 24 * 3600  # 24 horas
watchlist_mgr = JsonManager(WATCHLIST_FILE)


def fetch_closed_pnl_from_bybit():
    """Busca todos os trades fechados dos últimos 30 dias via Bybit API"""
    secrets = get_secrets()
    if not secrets.get('BYBIT_API_KEY'):
        return None
    
    try:
        exchange = ccxt.bybit({
            'apiKey': secrets['BYBIT_API_KEY'],
            'secret': secrets['BYBIT_SECRET'],
            'options': {'defaultType': 'linear'}
        })
        
        all_trades = []
        cursor = ''
        
        for _ in range(50):  # max 50 pages (5000 trades)
            params = {'category': 'linear', 'limit': 100}
            if cursor:
                params['cursor'] = cursor
            
            result = exchange.private_get_v5_position_closed_pnl(params)
            trades = result['result']['list']
            if not trades:
                break
            
            # Filtrar últimos 30 dias
            cutoff_ms = (time.time() - 30 * 86400) * 1000
            for t in trades:
                if int(t['updatedTime']) >= cutoff_ms:
                    all_trades.append({
                        'symbol': t['symbol'],
                        'side': t['side'],
                        'pnl': float(t['closedPnl']),
                        'qty': float(t.get('qty', 0)),
                        'entry_price': float(t.get('avgEntryPrice', 0)),
                        'exit_price': float(t.get('avgExitPrice', 0)),
                        'leverage': t.get('leverage', '1'),
                        'closed_at': int(t['updatedTime']),
                        'order_type': t.get('orderType', ''),
                    })
                else:
                    # Trades mais antigos que 30 dias, parar
                    cursor = ''
                    break
            
            cursor = result['result'].get('nextPageCursor', '')
            if not cursor:
                break
            time.sleep(0.15)
        
        # Ordenar por data (mais recente primeiro)
        all_trades.sort(key=lambda x: x['closed_at'], reverse=True)
        
        # Salvar cache
        cache = {
            'updated_at': time.time(),
            'trades': all_trades
        }
        with open(CLOSED_PNL_CACHE, 'w') as f:
            json.dump(cache, f)
        
        print(f"[CACHE] Bybit closed PnL atualizado: {len(all_trades)} trades (30d)")
        return all_trades
        
    except Exception as e:
        print(f"Erro fetch closed PnL: {e}")
        return None


def get_closed_trades():
    """Retorna trades fechados do cache (atualiza se > 24h)"""
    # Tentar ler cache
    if os.path.exists(CLOSED_PNL_CACHE):
        try:
            with open(CLOSED_PNL_CACHE, 'r') as f:
                cache = json.load(f)
            age = time.time() - cache.get('updated_at', 0)
            if age < CACHE_MAX_AGE:
                return cache.get('trades', [])
            print(f"[CACHE] Expirado ({age/3600:.1f}h). Atualizando...")
        except Exception as e:
            print(f"Erro lendo cache: {e}")
    
    # Cache inexistente ou expirado — buscar da Bybit
    trades = fetch_closed_pnl_from_bybit()
    return trades if trades is not None else []

def get_secrets():
    secrets = {}
    try:
        path_env = os.path.join(BASE_DIR, '.env')
        if os.path.exists(path_env):
            with open(path_env, 'r') as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, val = line.strip().split('=', 1)
                        secrets[key] = val
    except: pass
    return secrets

# LANDING PAGE (rota principal)
@app.route('/')
def index():
    return render_template('index.html')

# DASHBOARD (aba secundária)
@app.route('/dashboard')
def dashboard():
    # Fetch data for dashboard
    secrets = get_secrets()
    stats_data = {
        'equity': 0,
        'available': 0, 
        'active_count': 0,
        'pnl_today': 0,
        'pnl_unrealized': 0
    }
    
    winrate_data = {
        'winrate': 0,
        'wins': 0,
        'losses': 0,
        'total_pnl': 0
    }
    
    if secrets.get('BYBIT_API_KEY'):
        try:
            exchange = ccxt.bybit({
                'apiKey': secrets['BYBIT_API_KEY'],
                'secret': secrets['BYBIT_SECRET'],
                'options': {'defaultType': 'linear'}
            })
            
            # Get balance
            balance = exchange.fetch_balance()
            total = balance.get('USDT', {})
            stats_data['equity'] = total.get('total', 0)
            stats_data['available'] = total.get('free', 0)
            
            # Get positions
            positions = exchange.fetch_positions()
            open_positions = [pos for pos in positions if safe_float(pos.get('contracts')) != 0]
            stats_data['active_count'] = len(open_positions)
            stats_data['pnl_unrealized'] = sum(safe_float(pos.get('unrealizedPnl')) for pos in open_positions)
            stats_data['pnl_today'] = stats_data['pnl_unrealized']  # Simplified
            
        except Exception as e:
            print(f"Error fetching dashboard data: {e}")
    
    # Get winrate data
    try:
        trades = get_closed_trades() or []
        if trades:
            wins = [t for t in trades if safe_float(t.get('pnl')) > 0]
            losses = [t for t in trades if safe_float(t.get('pnl')) <= 0]
            
            winrate_data = {
                'winrate': (len(wins) / len(trades)) * 100 if trades else 0,
                'wins': len(wins),
                'losses': len(losses),
                'total_pnl': sum(safe_float(t.get('pnl')) for t in trades)
            }
    except Exception as e:
        print(f"Error calculating winrate: {e}")
    
    return render_template('dashboard.html', stats=stats_data, winrate=winrate_data)

# DETAILS PAGES
@app.route('/trades-details')  
def trades_details():
    return render_template('trades_details.html')

@app.route('/pnl-details')
def pnl_details():
    return render_template('pnl_details.html')

@app.route('/performance-details')
def performance_details():
    return render_template('performance_details.html')

@app.route('/test')
def test_dashboard():
    with open('/root/bot_sniper_bybit/test_dashboard.html', 'r') as f:
        return f.read()

def get_pattern_info_for_symbol(symbol):
    """Busca informações de pattern para um símbolo específico"""
    try:
        # Buscar na watchlist ativa
        with open('/root/bot_sniper_bybit/watchlist.json', 'r') as f:
            watchlist = json.load(f)
        
        symbol_clean = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
        
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
                    'source': 'watchlist_active'
                }
        return None
    except Exception as e:
        print(f"Error getting pattern info for {symbol}: {e}")
        return None

def get_vision_ai_status(symbol):
    """Busca status do Vision AI para um símbolo"""
    try:
        symbol_clean = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
        
        with open('/root/bot_sniper_bybit/vision.log', 'r') as f:
            lines = f.readlines()
        
        # Buscar última análise para este símbolo nas últimas 100 linhas
        for line in reversed(lines[-100:]):
            if symbol_clean in line and ('VALID' in line or 'INVALID' in line):
                if 'VALID' in line:
                    return {
                        'status': 'VALID',
                        'latest_verdict': 'VALID',
                        'latest_confidence': 0.85,
                        'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                else:
                    return {
                        'status': 'INVALID',
                        'latest_verdict': 'INVALID', 
                        'latest_confidence': 0.45,
                        'last_check': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
        return None
    except Exception as e:
        print(f"Error getting vision AI status for {symbol}: {e}")
        return None

def get_post_entry_status(symbol):
    """Busca status real do Post-Entry Validator dos logs"""
    try:
        symbol_clean = symbol.replace('/USDT:USDT', '').replace('/USDT', '')
        
        # Buscar no log de validações
        if os.path.exists('/root/bot_sniper_bybit/vision_alerts.log'):
            with open('/root/bot_sniper_bybit/vision_alerts.log', 'r') as f:
                lines = f.readlines()
            
            # Buscar última validação para este símbolo nas últimas 50 linhas
            latest_validation = None
            validation_count = 0
            
            for line in reversed(lines[-50:]):
                if f'{symbol_clean}/USDT' in line and 'VALIDATION #' in line:
                    validation_count += 1
                    if latest_validation is None:  # Primeira (mais recente)
                        parts = line.strip().split(' | ')
                        if len(parts) >= 3:
                            # Extrair dados: "2026-02-15 22:30:18 - VALIDATION #2 | HBAR/USDT:USDT | VALID (0.80) | ..."
                            timestamp_str = parts[0].split(' - VALIDATION')[0]
                            status_part = parts[2]  # "VALID (0.80)"
                            
                            if '(' in status_part and ')' in status_part:
                                status = status_part.split('(')[0].strip()  # "VALID"
                                confidence_str = status_part.split('(')[1].split(')')[0]  # "0.80"
                                confidence = float(confidence_str)
                                
                                latest_validation = {
                                    'timestamp': timestamp_str,
                                    'status': status,
                                    'confidence': confidence,
                                    'validation_number': parts[0].split('VALIDATION #')[1].split(' |')[0] if 'VALIDATION #' in parts[0] else 'N/A'
                                }
            
            if latest_validation:
                # Calcular tempo desde última validação
                try:
                    last_time = datetime.strptime(latest_validation['timestamp'], '%Y-%m-%d %H:%M:%S')
                    now = datetime.now()
                    minutes_ago = int((now - last_time).total_seconds() / 60)
                    
                    # Determinar se está ativo (validação recente)
                    is_active = minutes_ago <= 30  # Ativo se validação foi nos últimos 30 min
                    
                    return {
                        'status': 'ACTIVE' if is_active else 'INACTIVE',
                        'is_active': is_active,
                        'latest_status': latest_validation['status'],
                        'latest_validation': latest_validation['status'],
                        'confidence': latest_validation['confidence'],
                        'last_check': f"{minutes_ago}m ago" if minutes_ago < 60 else f"{int(minutes_ago/60)}h ago",
                        'latest_log': f"Last validation: {latest_validation['status']} ({latest_validation['confidence']:.2f}) - {minutes_ago}m ago",
                        'validation_count': validation_count,
                        'total_validations': validation_count,
                        'last_validation_time': latest_validation['timestamp']
                    }
                except Exception as e:
                    print(f"Error parsing validation timestamp: {e}")
        
        # Se não encontrou dados nos logs, retornar status inativo
        return {
            'status': 'INACTIVE',
            'is_active': False,
            'latest_status': 'NONE',
            'latest_validation': 'NONE',
            'confidence': 0,
            'last_check': 'No recent logs',
            'latest_log': 'No recent validation logs found',
            'validation_count': 0,
            'total_validations': 0,
            'last_validation_time': None
        }
        
    except Exception as e:
        print(f"Error getting post-entry status for {symbol}: {e}")
        return {
            'status': 'ERROR',
            'is_active': False,
            'latest_status': 'ERROR',
            'latest_validation': 'ERROR',
            'confidence': 0,
            'last_check': f'Error: {str(e)}',
            'latest_log': f'Error: {str(e)}',
            'validation_count': 0,
            'total_validations': 0,
            'last_validation_time': None
        }

@app.route('/api/trades-detailed')
def get_detailed_trades():
    """Endpoint para dados detalhados de trades para a página de detalhes"""
    try:
        secrets = get_secrets()
        
        # Buscar posições abertas
        open_positions = []
        if secrets.get('BYBIT_API_KEY'):
            try:
                exchange = ccxt.bybit({
                    'apiKey': secrets['BYBIT_API_KEY'],
                    'secret': secrets['BYBIT_SECRET'],
                    'options': {'defaultType': 'linear'}
                })
                positions = exchange.fetch_positions()
                open_positions = [pos for pos in positions if safe_float(pos.get('contracts')) != 0]
            except Exception as e:
                print(f"Error fetching positions: {e}")
        
        # Buscar trades fechados
        closed_trades = get_closed_trades() or []
        
        # Formatar dados para o formato esperado pela página
        response_data = {
            'open_count': len(open_positions),
            'closed_count': len(closed_trades),
            'open_positions': [
                {
                    'symbol': pos.get('symbol', ''),
                    'symbol_clean': pos.get('symbol', '').replace('/USDT:USDT', '').replace('/USDT', ''),
                    'side': 'LONG' if pos.get('side', '').lower() == 'buy' else 'SHORT',
                    'size': abs(safe_float(pos.get('contracts'))),
                    'entry_price': safe_float(pos.get('entryPrice')),
                    'current_price': safe_float(pos.get('markPrice')),
                    'pnl': safe_float(pos.get('unrealizedPnl')),
                    'pnl_pct': safe_float(pos.get('percentage')),
                    'liquidation_price': safe_float(pos.get('liquidationPrice')),
                    'leverage': pos.get('leverage', '1'),
                    'pattern_info': get_pattern_info_for_symbol(pos.get('symbol', '')),
                    'vision_ai_status': get_vision_ai_status(pos.get('symbol', '')),
                    'post_entry_status': get_post_entry_status(pos.get('symbol', ''))
                } for pos in open_positions
            ],
            'closed_trades': [
                {
                    'symbol': trade.get('symbol', ''),
                    'symbol_clean': trade.get('symbol', '').replace('USDT', '').replace(':', ''),
                    'side': trade.get('side', '').upper(),
                    'entry_price': safe_float(trade.get('entry_price')),
                    'exit_price': safe_float(trade.get('exit_price')),
                    'pnl': safe_float(trade.get('pnl')),
                    'closed_at': trade.get('closed_at', 0),
                    'pattern_info': None,  # Placeholder
                    'vision_analysis': None  # Placeholder
                } for trade in closed_trades[:100]  # Limit to last 100 trades
            ]
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in get_detailed_trades: {e}")
        return jsonify({
            'error': str(e),
            'open_count': 0,
            'closed_count': 0, 
            'open_positions': [],
            'closed_trades': []
        })

@app.route('/api/pnl-detailed')
def get_detailed_pnl():
    """Endpoint para dados detalhados de PnL para a página de detalhes"""
    try:
        from datetime import timedelta
        
        secrets = get_secrets()
        
        # Initialize data
        equity_data = {'equity': 0, 'available': 0, 'pnl_unrealized': 0}
        open_positions = []
        
        if secrets.get('BYBIT_API_KEY'):
            try:
                exchange = ccxt.bybit({
                    'apiKey': secrets['BYBIT_API_KEY'],
                    'secret': secrets['BYBIT_SECRET'],
                    'options': {'defaultType': 'linear'}
                })
                
                # Get balance
                balance = exchange.fetch_balance()
                total = balance.get('USDT', {})
                equity_data = {
                    'equity': total.get('total', 0),
                    'available': total.get('free', 0),
                    'pnl_unrealized': sum(safe_float(pos.get('unrealizedPnl')) for pos in exchange.fetch_positions() if safe_float(pos.get('contracts')) != 0)
                }
                
                # Get open positions
                positions = exchange.fetch_positions()
                open_positions = [pos for pos in positions if safe_float(pos.get('contracts')) != 0]
                
            except Exception as e:
                print(f"Error fetching PnL data: {e}")
        
        # Get closed trades for PnL calculations
        closed_trades = get_closed_trades() or []
        
        # Calculate time periods
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)
        
        # Calculate PnL by periods
        today_pnl = 0
        week_pnl = 0
        month_pnl = 0
        today_trades = 0
        week_trades = 0
        month_trades = 0
        
        for trade in closed_trades:
            if trade.get('closed_at'):
                trade_time = datetime.fromtimestamp(trade['closed_at'] / 1000)
                pnl = safe_float(trade.get('pnl'))
                
                # Count trades and PnL by period
                if trade_time >= month_start:
                    month_pnl += pnl
                    month_trades += 1
                    
                    if trade_time >= week_start:
                        week_pnl += pnl
                        week_trades += 1
                        
                        if trade_time >= today_start:
                            today_pnl += pnl
                            today_trades += 1
        
        # Total realized PnL
        total_realized_pnl = sum(safe_float(trade.get('pnl')) for trade in closed_trades)
        
        # Format response in the structure expected by JavaScript  
        response_data = {
            'unrealized_pnl': equity_data['pnl_unrealized'],
            'today_pnl': today_pnl,
            'week_pnl': week_pnl,  
            'month_pnl': month_pnl,
            'total_pnl': equity_data['pnl_unrealized'] + total_realized_pnl,
            'today_trades': today_trades,
            'week_trades': week_trades,
            'month_trades': month_trades,
            'current_equity': equity_data['equity'],
            'available_balance': equity_data['available'],
            'realized_pnl_total': total_realized_pnl,
            'open_positions_pnl': [
                {
                    'symbol': pos.get('symbol', '').replace('/USDT:USDT', '').replace('/USDT', ''),
                    'pnl': safe_float(pos.get('unrealizedPnl')),
                    'pnl_pct': safe_float(pos.get('percentage')),
                    'side': 'LONG' if safe_float(pos.get('contracts')) > 0 else 'SHORT'
                } for pos in open_positions
            ]
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in get_detailed_pnl: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/performance-detailed')
def get_detailed_performance():
    """Endpoint para dados detalhados de performance para a página de detalhes"""
    try:
        # Buscar trades fechados
        closed_trades = get_closed_trades() or []
        
        if not closed_trades:
            return jsonify({
                'winrate': 0,
                'total_trades': 0,
                'wins': 0,
                'losses': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'best_trade': 0,
                'worst_trade': 0,
                'trading_pairs': [],
                'monthly_performance': []
            })
        
        # Calcular estatísticas básicas
        wins = [t for t in closed_trades if safe_float(t.get('pnl')) > 0]
        losses = [t for t in closed_trades if safe_float(t.get('pnl')) <= 0]
        
        total_profit = sum(safe_float(t.get('pnl')) for t in wins)
        total_loss = abs(sum(safe_float(t.get('pnl')) for t in losses))
        
        # Performance por par
        pair_stats = {}
        for trade in closed_trades:
            symbol = trade.get('symbol', '').replace('USDT', '')
            if symbol not in pair_stats:
                pair_stats[symbol] = {'trades': 0, 'wins': 0, 'pnl': 0}
            pair_stats[symbol]['trades'] += 1
            if safe_float(trade.get('pnl')) > 0:
                pair_stats[symbol]['wins'] += 1
            pair_stats[symbol]['pnl'] += safe_float(trade.get('pnl'))
        
        # Performance mensal
        monthly_stats = {}
        for trade in closed_trades:
            if trade.get('closed_at'):
                month_key = datetime.fromtimestamp(trade['closed_at'] / 1000).strftime('%Y-%m')
                if month_key not in monthly_stats:
                    monthly_stats[month_key] = {'trades': 0, 'wins': 0, 'pnl': 0}
                monthly_stats[month_key]['trades'] += 1
                if safe_float(trade.get('pnl')) > 0:
                    monthly_stats[month_key]['wins'] += 1
                monthly_stats[month_key]['pnl'] += safe_float(trade.get('pnl'))
        
        # Calculate period stats for JavaScript compatibility
        now = datetime.now()
        week_start = now - timedelta(days=7)
        month_start = now - timedelta(days=30)
        
        # Separate trades by periods
        week_trades = []
        month_trades = []
        
        for trade in closed_trades:
            if trade.get('closed_at'):
                trade_time = datetime.fromtimestamp(trade['closed_at'] / 1000)
                
                if trade_time >= month_start:
                    month_trades.append(trade)
                    if trade_time >= week_start:
                        week_trades.append(trade)
        
        # Calculate 7d stats
        week_wins = [t for t in week_trades if safe_float(t.get('pnl')) > 0]
        week_winrate = (len(week_wins) / len(week_trades) * 100) if week_trades else 0
        week_total_pnl = sum(safe_float(t.get('pnl')) for t in week_trades)
        
        # Calculate 30d stats  
        month_wins = [t for t in month_trades if safe_float(t.get('pnl')) > 0]
        month_winrate = (len(month_wins) / len(month_trades) * 100) if month_trades else 0
        month_total_pnl = sum(safe_float(t.get('pnl')) for t in month_trades)
        
        response_data = {
            'winrate': round((len(wins) / len(closed_trades)) * 100, 1) if closed_trades else 0,
            'total_trades': len(closed_trades),
            'wins': len(wins),
            'losses': len(losses),
            'avg_win': round(total_profit / len(wins), 4) if wins else 0,
            'avg_loss': round(total_loss / len(losses), 4) if losses else 0,
            'profit_factor': round(total_profit / total_loss, 2) if total_loss > 0 else 0,
            'best_trade': max((safe_float(t.get('pnl')) for t in closed_trades), default=0),
            'worst_trade': min((safe_float(t.get('pnl')) for t in closed_trades), default=0),
            'trading_pairs': [
                {
                    'symbol': symbol,
                    'trades': data['trades'],
                    'winrate': round((data['wins'] / data['trades']) * 100, 1),
                    'pnl': round(data['pnl'], 4)
                } for symbol, data in sorted(pair_stats.items(), key=lambda x: x[1]['trades'], reverse=True)
            ],
            'monthly_performance': [
                {
                    'month': month,
                    'trades': data['trades'],
                    'winrate': round((data['wins'] / data['trades']) * 100, 1),
                    'pnl': round(data['pnl'], 4)
                } for month, data in sorted(monthly_stats.items())
            ],
            'period_stats': {
                '7d': {
                    'win_rate': round(week_winrate, 1),
                    'wins': len(week_wins),
                    'losses': len(week_trades) - len(week_wins),
                    'trades': len(week_trades),
                    'total_pnl': round(week_total_pnl, 2)
                },
                '30d': {
                    'win_rate': round(month_winrate, 1),
                    'wins': len(month_wins),
                    'losses': len(month_trades) - len(month_wins),
                    'trades': len(month_trades),
                    'total_pnl': round(month_total_pnl, 2)
                }
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        print(f"Error in get_detailed_performance: {e}")
        return jsonify({'error': str(e)})

@app.route('/api/stats')
def stats():
    secrets = get_secrets()
    data = {
        'equity': 0, 
        'available': 0, 
        'pnl_today': 0,
        'pnl_unrealized': 0,
        'open_positions': [],
        'active_count': 0
    }
    
    if secrets.get('BYBIT_API_KEY'):
        try:
            exchange = ccxt.bybit({
                'apiKey': secrets['BYBIT_API_KEY'],
                'secret': secrets['BYBIT_SECRET'],
                'options': {'defaultType': 'linear'}
            })
            
            # Balance
            bal = exchange.fetch_balance()
            data['equity'] = bal['USDT']['total']
            data['available'] = bal['USDT']['free']
            
            # Posições Abertas + PnL Unrealized
            positions = exchange.fetch_positions()
            pnl_total = 0
            
            for p in positions:
                contracts = float(p.get('contracts') or 0)
                if contracts > 0:
                    pnl_unreal = float(p.get('unrealizedPnl') or 0)
                    pnl_total += pnl_unreal
                    
                    data['open_positions'].append({
                        'symbol': p['symbol'],
                        'side': p['side'],
                        'size': contracts,
                        'entry': float(p.get('entryPrice') or 0),
                        'pnl': pnl_unreal,
                        'pnl_pct': float(p.get('percentage') or 0),
                        'leverage': p.get('leverage', 1)
                    })
            
            data['pnl_unrealized'] = pnl_total
            data['active_count'] = len(data['open_positions'])
            data['pnl_today'] = pnl_total  # Simplificação: PnL Today = Unrealized
                
        except Exception as e:
            print(f"Erro API Bybit: {e}")
            
    return jsonify(data)

@app.route('/api/watchlist')
def get_watchlist():
    wl = watchlist_mgr.read()
    if not wl: return jsonify([])
    
    # Adicionar preço atual para calcular distancia
    secrets = get_secrets()
    if secrets.get('BYBIT_API_KEY'):
        try:
            exchange = ccxt.bybit({
                'apiKey': secrets['BYBIT_API_KEY'], 
                'secret': secrets['BYBIT_SECRET']
            })
            
            if wl.get('pares'):
                symbols = [p['symbol'] for p in wl['pares']]
                try:
                    tickers = exchange.fetch_tickers(symbols)
                    for p in wl['pares']:
                        sym = p['symbol']
                        if sym in tickers:
                            p['current_price'] = tickers[sym]['last']
                            # Calc % distance
                            neckline = float(p.get('neckline', 0))
                            if neckline > 0:
                                dist = abs(p['current_price'] - neckline) / p['current_price'] * 100
                                p['dist_pct'] = round(dist, 2)
                except Exception as e:
                    print(f"Erro fetch tickers: {e}")
        except: pass
            
    return jsonify(wl.get('pares', []))

@app.route('/api/history')
def get_history():
    """
    Retorna trades fechados dos últimos 30 dias (Bybit closed PnL, cache 24h).
    """
    trades = get_closed_trades()
    
    if trades:
        # Calcular cumulative_pnl para o gráfico (do mais antigo pro mais recente)
        sorted_trades = sorted(trades, key=lambda x: x['closed_at'])
        cumulative = 0
        for t in sorted_trades:
            cumulative += t['pnl']
            t['cumulative_pnl'] = round(cumulative, 4)
            # Formatar data
            t['closed_at_str'] = datetime.fromtimestamp(t['closed_at'] / 1000).strftime('%d/%m %H:%M')
            t['status'] = 'WIN' if t['pnl'] > 0 else 'LOSS'
        
        # Retornar na ordem cronológica (mais antigo primeiro) para o gráfico
        return jsonify(sorted_trades)
    
    return jsonify([])

@app.route('/api/winrate')
def get_winrate():
    """Calcula win rate a partir dos trades fechados na Bybit (últimos 30 dias)"""
    try:
        trades = get_closed_trades()
        
        if not trades:
            return jsonify({'winrate': 0, 'wins': 0, 'losses': 0, 'total': 0, 'total_pnl': 0})
        
        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        total = len(trades)
        losses = total - wins
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        winrate = (wins / total * 100) if total > 0 else 0
        
        return jsonify({
            'winrate': round(winrate, 1),
            'wins': wins,
            'losses': losses,
            'total': total,
            'total_pnl': round(total_pnl, 4)
        })
    except Exception as e:
        print(f"Erro calc winrate: {e}")
        return jsonify({'winrate': 0, 'wins': 0, 'losses': 0, 'total': 0, 'total_pnl': 0})

@app.route('/api/logs')
def get_logs():
    log_data = []
    files = ['scanner_bybit.log', 'monitor_bybit.log', 'executor_bybit.log', 'vision_alerts.log']
    
    for log_file in files:
        path = os.path.join(BASE_DIR, log_file)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()[-20:]
                    for line in lines:
                        log_data.append(f"[{log_file.split('_')[0].upper()}] {line.strip()}")
            except: pass
    
    return jsonify(log_data[-50:])

@app.route('/api/market')
def get_market():
    """
    Retorna análise de mercado (BTC.D + Cenário)
    Dados vêm do webhook do TradingView
    """
    BTCD_FILE = os.path.join(BASE_DIR, 'btcd_data.json')
    
    try:
        # Ler dados do BTC.D (webhook)
        if os.path.exists(BTCD_FILE):
            with open(BTCD_FILE, 'r') as f:
                btcd_data = json.load(f)
            
            # Calcular idade dos dados
            age_seconds = time.time() - btcd_data.get('timestamp', 0)
            age_minutes = age_seconds / 60
            
            # Determinar cenário (simplificado, sem BTC trend aqui)
            # Idealmente usaria get_market_analysis da lib_utils, mas evitando dependência de exchange
            btcd_direction = btcd_data.get('direction', 'NEUTRAL')
            btcd_value = btcd_data.get('btc_d_value', 0)
            change_pct = btcd_data.get('change_pct', 0)
            
            # Cenário simplificado (só baseado em BTC.D)
            if btcd_direction == 'LONG':
                scenario_text = "BTC.D Subindo"
                scenario_color = "text-red-400"
                longs_status = "❌ Desfavorável"
                shorts_status = "✅ Favorável"
                scenario_advice = "Dinheiro indo para BTC. Evite LONGs em alts."
            elif btcd_direction == 'SHORT':
                scenario_text = "BTC.D Caindo"
                scenario_color = "text-green-400"
                longs_status = "✅ Favorável"
                shorts_status = "⚠️ Neutro"
                scenario_advice = "Dinheiro saindo do BTC. LONGs em alts favorecidos."
            else:
                scenario_text = "BTC.D Lateral"
                scenario_color = "text-yellow-400"
                longs_status = "⚠️ Neutro"
                shorts_status = "⚠️ Neutro"
                scenario_advice = "Mercado lateral. Alts seguem BTC."
            
            return jsonify({
                'btcd_value': btcd_value,
                'btcd_direction': btcd_direction,
                'change_pct': change_pct,
                'age_minutes': round(age_minutes, 1),
                'scenario_text': scenario_text,
                'scenario_color': scenario_color,
                'longs_status': longs_status,
                'shorts_status': shorts_status,
                'scenario_advice': scenario_advice,
                'source': 'TradingView Premium',
                'last_update': btcd_data.get('datetime', 'N/A')
            })
        else:
            # Arquivo não existe ainda
            return jsonify({
                'btcd_value': 0,
                'btcd_direction': 'WAITING',
                'change_pct': 0,
                'age_minutes': 0,
                'scenario_text': 'Aguardando dados...',
                'scenario_color': 'text-gray-400',
                'longs_status': '⏳ Aguardando',
                'shorts_status': '⏳ Aguardando',
                'scenario_advice': 'Configurando webhook do TradingView...',
                'source': 'TradingView Premium',
                'last_update': 'N/A'
            })
    except Exception as e:
        print(f"Erro ao ler market data: {e}")
        return jsonify({
            'btcd_value': 0,
            'btcd_direction': 'ERROR',
            'change_pct': 0,
            'age_minutes': 0,
            'scenario_text': 'Erro ao carregar',
            'scenario_color': 'text-red-400',
            'longs_status': '❌ Erro',
            'shorts_status': '❌ Erro',
            'scenario_advice': str(e),
            'source': 'Error',
            'last_update': 'N/A'
        })


@app.route('/api/vision/logs')
def get_vision_logs():
    try:
        log_path = os.path.join(BASE_DIR, 'vision.log')
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                lines = f.readlines()[-20:]  # Last 20 lines
            return jsonify({'logs': [l.strip() for l in lines]})
        return jsonify({'logs': ['Waiting for vision logs...']})
    except Exception as e:
        return jsonify({'logs': [f'Error reading logs: {str(e)}']})

@app.route('/api/vision/stats')
def get_vision_stats():
    from datetime import datetime
    try:
        import sqlite3
        db_path = os.path.join(BASE_DIR, 'sniper_brain.db')
        if not os.path.exists(db_path):
            return jsonify({'recent': [], 'stats': {'total': 0, 'valid': 0, 'invalid': 0}})
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        # Recent Validations
        c.execute("SELECT symbol, pattern_detected, ai_verdict, ai_confidence, timestamp_detection FROM raw_samples WHERE status='PROCESSED' ORDER BY id DESC LIMIT 5")
        recent = []
        for row in c.fetchall():
            r = dict(row)
            # Validação e formatação segura
            try:
                if r.get('timestamp_detection'):
                    dt = datetime.fromtimestamp(r['timestamp_detection'])
                    r['timestamp_formatted'] = dt.strftime('%d/%m/%Y %H:%M:%S')
                else:
                    r['timestamp_formatted'] = 'N/A'
            except:
                r['timestamp_formatted'] = 'N/A'
            
            # Garantir que campos críticos existem
            r.setdefault('symbol', 'UNKNOWN')
            r.setdefault('pattern_detected', 'N/A')
            r.setdefault('ai_verdict', 'PENDING')
            r.setdefault('ai_confidence', 0.0)
            
            recent.append(r)
        
        # Stats
        c.execute("SELECT COUNT(*) as total FROM raw_samples")
        total = c.fetchone()['total']
        c.execute("SELECT COUNT(*) as valid FROM raw_samples WHERE ai_verdict='VALID'")
        valid = c.fetchone()['valid']
        c.execute("SELECT COUNT(*) as invalid FROM raw_samples WHERE ai_verdict='INVALID'")
        invalid = c.fetchone()['invalid']
        
        conn.close()
        return jsonify({
            'recent': recent,
            'stats': {'total': total, 'valid': valid, 'invalid': invalid}
        })
    except Exception as e:
        print(f"Vision DB Error: {e}")
        return jsonify({'error': str(e), 'recent': [], 'stats': {}})



@app.route('/api/vision/alerts')
def get_vision_alerts():
    """Retorna alertas e validações pós-entrada do Vision AI"""
    try:
        alert_file = os.path.join(BASE_DIR, 'vision_alerts.log')
        if not os.path.exists(alert_file):
            return jsonify({'alerts': []})
        with open(alert_file, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()[-30:]  # Últimas 30 linhas
        return jsonify({'alerts': [l.strip() for l in lines if l.strip()]})
    except Exception as e:
        return jsonify({'alerts': [], 'error': str(e)})

@app.route('/brain_images/<path:filename>')
def serve_brain_image(filename):
    """Serve imagens geradas pelo Vision Validator"""
    return send_from_directory(os.path.join(BASE_DIR, 'brain_images'), filename)

@app.route('/api/vision/analysis')
def get_vision_analysis():
    """Retorna análises completas da IA com imagens, reasoning e confidence"""
    try:
        db_path = os.path.join(BASE_DIR, 'sniper_brain.db')
        if not os.path.exists(db_path):
            return jsonify({'analyses': []})
        
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("""
            SELECT id, symbol, timeframe, pattern_detected, direction,
                   ai_verdict, ai_confidence, ai_reasoning, image_path, status
            FROM raw_samples 
            WHERE status = 'PROCESSED'
            ORDER BY id DESC 
            LIMIT 20
        """)
        
        analyses = []
        for row in c.fetchall():
            r = dict(row)
            # Converter image_path para URL servível
            if r.get('image_path'):
                img_file = os.path.basename(r['image_path'])
                r['image_url'] = f"/brain_images/{img_file}"
            else:
                r['image_url'] = None
            del r['image_path']
            analyses.append(r)
        
        conn.close()
        return jsonify({'analyses': analyses})
    except Exception as e:
        print(f"Vision analysis error: {e}")
        return jsonify({'analyses': [], 'error': str(e)})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)

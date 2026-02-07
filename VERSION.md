# Bot Sniper Bybit - Version History

## v2.1.2 (2026-02-07) - CURRENT
**Branch:** `v2.1.2-fix-executor-precision`
**Tag:** `v2.1.2`

### 🐛 Critical Fixes
- **Executor Precision Error:** Fixed `'float' object cannot be interpreted as an integer`
  - `amount_precision` now always converted to `int`
  - Support for float precision values (e.g., 0.001 → 3 decimal places)
  - Added math.log10 conversion logic

- **Exchange Minimum Validation:** 
  - Query `market.limits.amount.min` from exchange
  - Round up when below minimum
  - Log warning when quantity adjusted

### 📈 Risk Management Changes
- **RISK_PER_TRADE:** 1.5% → **5.0%**
  - Allows trading with smaller account sizes
  - Reduces "Position < $5" rejections from 60% to ~10%

### 🛠️ System Restoration
Files restored from git due to corruption:
- `lib_utils.py` - Syntax errors (missing parentheses)
- `lib_padroes.py` - Import errors
- `templates/index.html` - Empty file (0 bytes → 234 lines) **[SITE DOWN CAUSE]**
- `dashboard_server.py` - Corrupted (1 line → 126 lines)
- `bot_telegram_control.py` - Empty (0 lines → 212 lines)
- `bot_manager.py` - Corrupted (1 line → restored)

### 📊 Testing Results
- ✅ All components running (Scanner, Monitor, Dashboard, Telegram)
- ✅ 0 precision errors in logs
- ✅ 3 pairs in watchlist (XLM, LDO, GRT)
- ✅ Account: $20.83 USDT operational

### 🔍 Impact
- **Before:** 100% execution failures (precision error)
- **After:** System fully operational

---

## v2.1.1 (unreleased)
*Skipped*

---

## v2.1.0 (2026-02-05)
**Last Stable Release Before Fixes**
- Dashboard V2.1 (Dark Mode + Charts)
- Manager Persistence Fix
- Nginx SSL Configuration
- Risk Management Phase 3
- Telegram Control Integration

---

## Version Scheme
`MAJOR.MINOR.PATCH`
- **MAJOR:** Breaking changes or full rewrites
- **MINOR:** New features, enhancements
- **PATCH:** Bug fixes, corrections


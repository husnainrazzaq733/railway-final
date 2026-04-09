import logging
import os
import datetime
import socket

# BUGFIX for Hugging Face Spaces [Errno -5] No address associated with hostname
# old_getaddrinfo = socket.getaddrinfo
# def new_getaddrinfo(*args, **kwargs):
#     responses = old_getaddrinfo(*args, **kwargs)
#     return [response for response in responses if response[0] == socket.AF_INET]
# socket.getaddrinfo = new_getaddrinfo

def get_current_time_str():
    pak_time = datetime.datetime.utcnow() + datetime.timedelta(hours=5)
    return pak_time.strftime('%d-%b-%Y  %I:%M:%S %p (PKT)')

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, TypeHandler, ApplicationHandlerStop
from keep_alive import keep_alive
from price_api import get_price, get_spot_price, get_swap_price, get_forex_price, get_pivot_points
from alert_engine import load_alerts, remove_alert, add_alert, get_alerts
from rsi_api import get_crypto_rsi, scan_market_rsi_both
import trade_engine
import auth
import session_engine

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def get_recommendation_text_async(symbol, market_type):
    import asyncio
    loop = asyncio.get_running_loop()
    from rsi_api import get_crypto_rsi
    _, rsi_data = await loop.run_in_executor(None, get_crypto_rsi, symbol, market_type)
    
    if not rsi_data:
        return ""
        
    sell_tfs = []
    buy_tfs = []
    
    for tf in ['15m', '1h', '4h', '1d']:
        val = rsi_data.get(tf)
        if val is not None:
            if val <= 30:
                buy_tfs.append(tf)
            elif val >= 70:
                sell_tfs.append(tf)
                
    buy_word = "LONG" if market_type == 'swap' else "BUY"
    sell_word = "SHORT" if market_type == 'swap' else "SELL"
    
    if buy_tfs and not sell_tfs:
        return f"\n\n🚨 **TRADE SIGNAL** 🚨\n🟢 **Action:** {buy_word}\n📉 **Reason:** Oversold ({', '.join(buy_tfs)})"
    elif sell_tfs and not buy_tfs:
        return f"\n\n🚨 **TRADE SIGNAL** 🚨\n🔴 **Action:** {sell_word}\n📈 **Reason:** Overbought ({', '.join(sell_tfs)})"
    elif buy_tfs and sell_tfs:
         return f"\n\n🚨 **TRADE SIGNAL** 🚨\n⚠️ **Action:** MIXED\n⚖️ **Details:** {buy_word} ({', '.join(buy_tfs)}), {sell_word} ({', '.join(sell_tfs)})"
    else:
        return f"\n\n⚪ **Signal:** NEUTRAL"

async def auth_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Process only physical user interactions
    if not update.effective_user:
        return
        
    chat_id = update.effective_user.id
    is_allowed, is_new_owner = auth.check_and_authorize(chat_id)
    
    if is_new_owner:
        if update.message:
            await update.message.reply_text(f"🎉 **Congratulations!**\nYou are the first person to use this bot, so you have automatically been made the **OWNER**.\n\nYour Chat ID is `{chat_id}`.\nYou can now use `/adduser <id>` to grant others access.", parse_mode='Markdown')
        return # Allow this interaction to continue!
        
    if not is_allowed:
        if update.message and update.message.text and update.message.text.startswith('/start'):
            # Only reply to start so we don't spam them on every message
            await update.message.reply_text(f"⛔ **Unauthorized**\nYou do not have permission to use this bot.\nIf you know the owner, give them your Chat ID: `{chat_id}`", parse_mode='Markdown')
        raise ApplicationHandlerStop()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_keyboard = [[KeyboardButton("🛠️ Show All Commands")]]
    reply_markup_persistent = ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True)
    
    keyboard = [
        [
            InlineKeyboardButton("🪙 BTC", callback_data='price_BTCUSDT'),
            InlineKeyboardButton("🪙 ETH", callback_data='price_ETHUSDT'),
            InlineKeyboardButton("🪙 SOL", callback_data='price_SOLUSDT')
        ],
        [
            InlineKeyboardButton("💵 EUR/USD", callback_data='price_EURUSD=X'),
            InlineKeyboardButton("💵 GBP/USD", callback_data='price_GBPUSD=X'),
            InlineKeyboardButton("⚜️ Gold", callback_data='price_XAUUSD=X')
        ]
    ]
    inline_markup = InlineKeyboardMarkup(keyboard)
    
    # Send a small setup message to embed the persistent bottom keyboard
    await update.message.reply_text("Tap the bottom button anytime to see commands ⬇️", reply_markup=reply_markup_persistent)
    
    # Send the main interactive menu
    await update.message.reply_text(
        '👋 Welcome to the Crypto & Forex Price Alert Bot!\n\n'
        '• Select a popular pair below for a quick price check.', 
        reply_markup=inline_markup
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🛠️ Show All Commands":
        help_text = (
            "🛠️ **Bot Commands Menu:**\n\n"
            "🔹 `/start` - Main menu\n"
            "🔹 `/spotprice` - Spot Live (e.g `/spotprice BTC`)\n"
            "🔹 `/setspotalert` - Spot Alert (e.g `/setspotalert BTC 65000`)\n"
            "🔹 `/swapprice` - Swap Live (e.g `/swapprice ETH`)\n"
            "🔹 `/setswapalert` - Swap Alert (e.g `/setswapalert ETH 3500`)\n"
            "🔹 `/forexprice` - Forex Live (e.g `/forexprice EUR`)\n"
            "🔹 `/setforexalert` - Forex Alert (e.g `/setforexalert EUR 1.1`)\n"
            "🔹 `/gold` - Gold Live Price\n"
            "🔹 `/setgoldalert` - Gold Alert (e.g `/setgoldalert 2300`)\n"
            "🔹 `/rsi` - Check RSI for a coin (e.g `/rsi BTC`)\n"
            "🔹 `/scan_rsi` - Scan top coins for Buy/Sell zones\n"
            "🔹 `/list` - View your active alerts list\n"
            "🔹 `/deletealert <id>` - Delete manual alert\n"
            "🔹 `/tracktrade` - Track RR targets (e.g `/tracktrade BTC 65000 64000`)\n"
            "🔹 `/mytrades` - View tracked trades\n"
            "🔹 `/deletetrade <id>` - Remove tracked trade\n"
            "🔹 `/session` - Live Forex trading sessions\n"
            "🔹 `/todaynews` - Today's High Impact USD News 📰\n"
        )
        if auth.is_owner(update.effective_user.id):
            help_text += (
                "\n👑 **Owner Commands:**\n"
                "🔹 `/adduser <id>` - Authorize user\n"
                "🔹 `/removeuser <id>` - Revoke access\n"
                "🔹 `/users` - List users\n"
            )
        await update.message.reply_text(help_text, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('scan_market_'):
        market_type = data.replace('scan_market_', '')
        keyboard = [
            [
                InlineKeyboardButton("15m", callback_data=f'scan_tf_{market_type}_15m'),
                InlineKeyboardButton("1h", callback_data=f'scan_tf_{market_type}_1h')
            ],
            [
                InlineKeyboardButton("4h", callback_data=f'scan_tf_{market_type}_4h'),
                InlineKeyboardButton("1D", callback_data=f'scan_tf_{market_type}_1d')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"🪙 Selected: **{market_type.capitalize()}**.\nNow select the Timeframe:", parse_mode='Markdown', reply_markup=reply_markup)
        return
        
    if data.startswith('scan_tf_'):
        parts = data.split('_')
        market_type = parts[2]
        tf = parts[3]
        
        await query.edit_message_text(text=f"⏳ Scanning top 300 **{market_type.capitalize()}** coins for **{tf}** Buy/Sell zones...\nThis will take ~10-15 seconds.", parse_mode='Markdown')
        
        import asyncio
        loop = asyncio.get_running_loop()
        buy_results, sell_results = await loop.run_in_executor(None, scan_market_rsi_both, market_type, tf, 300)
        
        if not buy_results and not sell_results:
             await query.edit_message_text(text=f"📊 **Scan complete.**\nNo coins found in Buy or Sell zones for **{tf}**.", parse_mode='Markdown')
             return
             
        text = f"🔍 **{tf} {market_type.capitalize()} Scan Results**\n\n"
        
        if buy_results:
            text += "🟢 **BUY ZONE (Oversold <= 30)**\n"
            for sym, rval in buy_results[:15]:
                text += f"▪️ `{sym}` : **{rval}**\n"
            text += "\n"
            
        if sell_results:
            text += "🔴 **SELL ZONE (Overbought >= 70)**\n"
            for sym, rval in sell_results[:15]:
                text += f"▪️ `{sym}` : **{rval}**\n"
            text += "\n"
                
        if len(text) > 3800:
            text = text[:3800] + "\n*...list truncated for length.*"
            
        text += f"\n⏰ {get_current_time_str()}"
        await query.edit_message_text(text=text, parse_mode='Markdown')
        return

    if data.startswith('price_'):
        symbol = data.split('_', 1)[1]
        price, domain, resolved_symbol = get_price(symbol)
        if price:
            rec = ""
            if domain == 'crypto':
                # Quick price check defaults to spot, but we can just use spot
                rec = await get_recommendation_text_async(resolved_symbol, 'spot')
            await query.edit_message_text(text=f"📈 **Live Price for {resolved_symbol}:** `{price}`{rec}\n\n⏰ {get_current_time_str()}", parse_mode='Markdown')
        else:
            await query.edit_message_text(text=f"❌ Could not fetch price for {symbol}.")

async def spot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Usage: /spotprice <symbol>\nExample: /spotprice BTC")
        return
    base_symbol = context.args[0].upper()
    symbol = base_symbol if base_symbol.endswith("USDT") else base_symbol + "USDT"
    price = get_spot_price(symbol)
    if price is not None:
        rec = await get_recommendation_text_async(symbol, 'spot')
        pivots = get_pivot_points(symbol, is_crypto=True, is_swap=False)
        pivot_txt = ""
        if pivots:
            pivot_txt = f"\n\n📐 **Support & Resistance:**\n`  R2 : {pivots['r2']}`\n`  R1 : {pivots['r1']}`\n`  P  : {pivots['p']}`\n`  S1 : {pivots['s1']}`\n`  S2 : {pivots['s2']}`"
            
        await update.message.reply_text(f"🪙 **Spot Price for {symbol}:** `{price}`{rec}{pivot_txt}\n\n⏰ {get_current_time_str()}", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Could not fetch Spot price for {symbol}.")

async def swap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Usage: /swapprice <symbol>\nExample: /swapprice BTC")
        return
    base_symbol = context.args[0].upper()
    symbol = base_symbol if base_symbol.endswith("USDT") else base_symbol + "USDT"
    price = get_swap_price(symbol)
    if price is not None:
        rec = await get_recommendation_text_async(symbol, 'swap')
        pivots = get_pivot_points(symbol, is_crypto=True, is_swap=True)
        pivot_txt = ""
        if pivots:
            pivot_txt = f"\n\n📐 **Support & Resistance:**\n`  R2 : {pivots['r2']}`\n`  R1 : {pivots['r1']}`\n`  P  : {pivots['p']}`\n`  S1 : {pivots['s1']}`\n`  S2 : {pivots['s2']}`"
            
        await update.message.reply_text(f"🪙 **Swap Price for {symbol}:** `{price}`{rec}{pivot_txt}\n\n⏰ {get_current_time_str()}", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Could not fetch Swap price for {symbol}.")

async def forex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Usage: /forexprice <symbol>\nExample: /forexprice EUR")
        return
    base_symbol = context.args[0].upper().replace("/", "")
    if len(base_symbol) == 3 and "=" not in base_symbol:
        symbol = base_symbol + "USD=X"
    elif "=" not in base_symbol:
        symbol = base_symbol + "=X"
    else:
        symbol = base_symbol
        
    price = get_forex_price(symbol)
    if price is not None:
        display = symbol.replace("=X", "")
        if len(display) == 6:
            display = display[:3] + "/" + display[3:]
        await update.message.reply_text(f"💵 Live Price for {display}: {price}\n⏰ {get_current_time_str()}")
    else:
        await update.message.reply_text(f"❌ Could not fetch price for {symbol}.")

async def setspot_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("ℹ️ Usage: /setspotalert <symbol> <target_price>\nExample: /setspotalert BTC 65000")
        return
        
    base_symbol = context.args[0].upper()
    try:
        target_price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Target price must be a valid number.")
        return
        
    symbol = base_symbol if base_symbol.endswith("USDT") else base_symbol + "USDT"
    current_price = get_spot_price(symbol)
    
    if current_price is None:
        await update.message.reply_text(f"❌ Could not fetch initial Spot price for {symbol}.")
        return
        
    condition = 'above' if target_price > current_price else 'below'
    user_name = update.effective_user.first_name
    add_alert(update.message.chat_id, user_name, symbol, target_price, condition)
    await update.message.reply_text(f"✅ Spot Alert set by **{user_name}**! I will notify when `{symbol}` (Spot) goes **{condition.upper()}** {target_price}.\n\n(Current price is {current_price})\n⏰ Time: {get_current_time_str()}", parse_mode='Markdown')

async def setswap_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("ℹ️ Usage: /setswapalert <symbol> <target_price>\nExample: /setswapalert BTC 65000")
        return
        
    base_symbol = context.args[0].upper()
    try:
        target_price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Target price must be a valid number.")
        return
        
    symbol = base_symbol if base_symbol.endswith("USDT") else base_symbol + "USDT"
    current_price = get_swap_price(symbol)
    
    if current_price is None:
        await update.message.reply_text(f"❌ Could not fetch initial Swap price for {symbol}.")
        return
        
    condition = 'above' if target_price > current_price else 'below'
    user_name = update.effective_user.first_name
    add_alert(update.message.chat_id, user_name, symbol, target_price, condition)
    await update.message.reply_text(f"✅ Swap Alert set by **{user_name}**! I will notify when `{symbol}` (Swap) goes **{condition.upper()}** {target_price}.\n\n(Current price is {current_price})\n⏰ Time: {get_current_time_str()}", parse_mode='Markdown')

async def setforex_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("ℹ️ Usage: /setforexalert <symbol> <target_price>\nExample: /setforexalert EUR 1.10")
        return
        
    base_symbol = context.args[0].upper().replace("/", "")
    try:
        target_price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Target price must be a valid number.")
        return
        
    if len(base_symbol) == 3 and "=" not in base_symbol:
        symbol = base_symbol + "USD=X"
    elif "=" not in base_symbol:
        symbol = base_symbol + "=X"
    else:
        symbol = base_symbol
        
    current_price = get_forex_price(symbol)
    
    if current_price is None:
        await update.message.reply_text(f"❌ Could not fetch initial price for {symbol}.")
        return
        
    condition = 'above' if target_price > current_price else 'below'
    display = symbol.replace("=X", "")
    if len(display) == 6:
        display = display[:3] + "/" + display[3:]
        
    user_name = update.effective_user.first_name
    add_alert(update.message.chat_id, user_name, symbol, target_price, condition)
    await update.message.reply_text(f"✅ Forex Alert set by **{user_name}**! I will notify when `{display}` goes **{condition.upper()}** {target_price}.\n\n(Current price is {current_price})\n⏰ Time: {get_current_time_str()}", parse_mode='Markdown')

async def gold_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = "XAUUSD=X"
    price = get_forex_price(symbol)
    if price is not None:
        pivots = get_pivot_points(symbol, is_crypto=False, is_gold=True)
        pivot_txt = ""
        if pivots:
            pivot_txt = f"\n\n📐 **Support & Resistance:**\n`  R2 : {pivots['r2']}`\n`  R1 : {pivots['r1']}`\n`  P  : {pivots['p']}`\n`  S1 : {pivots['s1']}`\n`  S2 : {pivots['s2']}`"
        await update.message.reply_text(f"⚜️ **Live Price for Gold:** `{price}`{pivot_txt}\n\n⏰ {get_current_time_str()}", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Could not fetch price for Gold.")

async def setgold_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 1:
        await update.message.reply_text("ℹ️ Usage: /setgoldalert <target_price>\nExample: /setgoldalert 2350.5")
        return
        
    try:
        target_price = float(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Target price must be a valid number.")
        return
        
    symbol = "XAUUSD=X"
    current_price = get_forex_price(symbol)
    
    if current_price is None:
        await update.message.reply_text(f"❌ Could not fetch initial price for Gold.")
        return
        
    condition = 'above' if target_price > current_price else 'below'
    # For display purposes in alerts
    display_symbol = "Gold" 
    # But in alerts.json we must save GC=F so the engine can check it
    user_name = update.effective_user.first_name
    add_alert(update.message.chat_id, user_name, symbol, target_price, condition)
    await update.message.reply_text(f"✅ Gold Alert set by **{user_name}**! I will notify when Gold goes **{condition.upper()}** {target_price}.\n\n(Current price is {current_price})\n⏰ Time: {get_current_time_str()}", parse_mode='Markdown')

async def rsi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Usage: /rsi <symbol> [spot/swap]\nExample: /rsi BTC swap")
        return
        
    symbol = context.args[0]
    market_type = 'spot'
    if len(context.args) > 1 and context.args[1].lower() == 'swap':
        market_type = 'swap'
        
    await update.message.reply_text(f"⏳ Calculating RSI for `{symbol}` ({market_type.capitalize()}) across multiple timeframes...")
    
    resolved_symbol, rsi_data = get_crypto_rsi(symbol, market_type)
    
    if rsi_data is None or all(v is None for v in rsi_data.values()):
        await update.message.reply_text(f"❌ Could not fetch RSI data for {symbol}.")
        return
        
    text = f"📊 **RSI (14) for {resolved_symbol}**\n\n"
    for tf in ['15m', '1h', '4h', '1d']:
        val = rsi_data.get(tf)
        if val is None:
            text += f"🔹 **{tf}**: `N/A`\n"
            continue
            
        if val > 70:
            emoji = "🔴 (Overbought/Sell Zone)"
        elif val < 30:
            emoji = "🟢 (Oversold/Buy Zone)"
        else:
            emoji = "⚪ (Neutral)"
            
        text += f"🔹 **{tf}**: `{val}` {emoji}\n"
        
    text += f"\n⏰ {get_current_time_str()}"
    await update.message.reply_text(text, parse_mode='Markdown')

async def scan_rsi_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("🪙 Spot Coins", callback_data='scan_market_spot'),
            InlineKeyboardButton("🪙 Swap Coins", callback_data='scan_market_swap')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Select the market you want to scan for RSI (Top 300 coins):", reply_markup=reply_markup)

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alerts = get_alerts(update.message.chat_id)
    if not alerts:
        await update.message.reply_text("You have no active alerts.")
        return
        
    text = f"📋 **Your Active Alerts:**\n⏰ {get_current_time_str()}\n\n"

    for a in alerts:
        a_user = a.get('user_name', 'Unknown')
        text += f"🔹 **ID: {a['id']}** | `{a['symbol']}` -> target **{a['target_price']}** (by {a_user})\n"
    text += "\n_Use /deletealert <ID> to remove an alert._"
    await update.message.reply_text(text, parse_mode='Markdown')

async def deletealert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Usage: /deletealert <id>\nCheck /list to find the ID of the alert.")
        return
        
    try:
        alert_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Alert ID must be a valid number.")
        return
        
    user_alerts = get_alerts(update.message.chat_id)
    alert_exists = any(a['id'] == alert_id for a in user_alerts)
    
    if alert_exists:
        remove_alert(alert_id)
        await update.message.reply_text(f"🗑️ Alert ID {alert_id} has been deleted permanently.")
    else:
        await update.message.reply_text(f"❌ You do not have an active alert with ID {alert_id}.")

async def check_alerts(context: ContextTypes.DEFAULT_TYPE):
    alerts = load_alerts()
    for alert in alerts:
        current_price, _, _ = get_price(alert['symbol'])
        if current_price is None:
            continue
            
        triggered = False
        text = ""
        if alert['condition'] == 'above' and current_price >= alert['target_price']:
            triggered = True
            text = f"UP"
        elif alert['condition'] == 'below' and current_price <= alert['target_price']:
            triggered = True
            text = f"DOWN"
            
        if triggered:
            # We explicitly format this message to emphasize up/down
            emoji = "🟢" if text == "UP" else "🔴"
            
            # Get current time
            trigger_time = get_current_time_str()
            a_user = alert.get('user_name', 'Unknown')
            
            message = f"🚨 {emoji} **PRICE ALERT!** {emoji} 🚨\n\n`{alert['symbol']}` price went **{text}** to **{current_price}**!\n\n*(Alert set by: {a_user})*\n⏰ **Time:** {trigger_time}\n\n_Auto-deleting one-time alert (Target was {alert['target_price']})_"
            try:
                await context.bot.send_message(chat_id=alert['chat_id'], text=message, parse_mode='Markdown')
                remove_alert(alert['id'])
            except Exception as e:
                logging.error(f"Failed to send alert to {alert['chat_id']}: {e}")

async def tracktrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        await update.message.reply_text("ℹ️ Usage: /tracktrade <symbol> <entry_price> <stop_loss>\nExample: /tracktrade BTCUSDT 65000 64000")
        return
        
    symbol = context.args[0].upper()
    try:
        entry_price = float(context.args[1])
        stop_loss = float(context.args[2])
    except ValueError:
        await update.message.reply_text("❌ Entry price and stop loss must be valid numbers.")
        return
        
    if entry_price == stop_loss:
        await update.message.reply_text("❌ Entry price and stop loss cannot be the same.")
        return
        
    current_price, _, resolved_symbol = get_price(symbol)
    if current_price is None:
        await update.message.reply_text(f"❌ Could not fetch price for {symbol}. Make sure it is a valid crypto or forex ticker.")
        return
        
    user_name = update.effective_user.first_name
    trade_id, trade = trade_engine.add_trade(update.message.chat_id, user_name, resolved_symbol, entry_price, stop_loss)
    
    position_type = "🟢 LONG" if trade['is_long'] else "🔴 SHORT"
    
    msg = f"🚀 **TRADE TRACKER ACTIVATED!** 🚀\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🔸 **Pair:** `{resolved_symbol}`\n"
    msg += f"🔸 **Position:** {position_type}\n"
    msg += f"🔸 **Entry:** `{entry_price}`\n"
    msg += f"🔸 **Stop Loss:** `{stop_loss}`\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"🎯 **AUTO-CALCULATED TARGETS**\n"
    msg += f"✅ **Target 1 (1:1.5 RR):** `{trade['t1']}`\n"
    msg += f"✅ **Target 2 (1:2.0 RR):** `{trade['t2']}`\n"
    msg += f"🚀 **Target 3 (1:3.0 RR):** `{trade['t3']}`\n"
    msg += f"━━━━━━━━━━━━━━━━━━\n"
    msg += f"⏳ _Watching the market for you..._\n"
    msg += f"⏰ {get_current_time_str()}"
    
    await update.message.reply_text(msg, parse_mode='Markdown')

async def mytrades_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    trades = trade_engine.get_user_trades(update.message.chat_id)
    if not trades:
        await update.message.reply_text("You are not tracking any trades.")
        return
        
    text = f"📋 **Your Tracked Trades:**\n⏰ {get_current_time_str()}\n\n"

    for t in trades:
        ptype = "LONG" if t['is_long'] else "SHORT"
        text += f"🔹 **ID: {t['id']}** | `{t['symbol']}` | {ptype} @ {t['entry_price']} | SL: {t['stop_loss']}\n"
        if t['t1_hit']: text += "   ✅ Target 1 Hit\n"
        if t['t2_hit']: text += "   ✅ Target 2 Hit\n"
    text += "\n_Use /deletetrade <ID> to stop tracking._"
    await update.message.reply_text(text, parse_mode='Markdown')

async def deletetrade_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("ℹ️ Usage: /deletetrade <id>\nCheck /mytrades to find the ID of the trade.")
        return
        
    try:
        trade_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Trade ID must be a valid number.")
        return
        
    user_trades = trade_engine.get_user_trades(update.message.chat_id)
    trade_exists = any(t['id'] == trade_id for t in user_trades)
    
    if trade_exists:
        trade_engine.remove_trade(trade_id)
        await update.message.reply_text(f"🗑️ Tracked trade ID {trade_id} has been deleted permanently.")
    else:
        await update.message.reply_text(f"❌ You do not have an active tracked trade with ID {trade_id}.")

async def check_active_trades(context: ContextTypes.DEFAULT_TYPE):
    trades = trade_engine.load_trades()
    for t in trades:
        current_price, _, _ = get_price(t['symbol'])
        if current_price is None:
            continue
            
        sl_hit = False
        t1_new_hit = False
        t2_new_hit = False
        t3_new_hit = False
        
        if t['is_long']:
            if current_price <= t['stop_loss']: sl_hit = True
            if current_price >= t['t3']: t3_new_hit = True
            elif current_price >= t['t2'] and not t['t2_hit']: t2_new_hit = True
            elif current_price >= t['t1'] and not t['t1_hit']: t1_new_hit = True
        else:
            if current_price >= t['stop_loss']: sl_hit = True
            if current_price <= t['t3']: t3_new_hit = True
            elif current_price <= t['t2'] and not t['t2_hit']: t2_new_hit = True
            elif current_price <= t['t1'] and not t['t1_hit']: t1_new_hit = True
            
        a_user = t.get('user_name', 'Unknown')
        base_msg_info = f"`{t['symbol']}` ({'LONG' if t['is_long'] else 'SHORT'})"
        
        try:
            if sl_hit:
                msg = f"😭 **STOP LOSS HIT!** 😭\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"💔 Oh no... The market went against us!\n\n"
                msg += f"🔸 **Pair:** {base_msg_info}\n"
                msg += f"🔸 **Stop Loss At:** `{t['stop_loss']}`\n"
                msg += f"🔸 **Current Price:** `{current_price}`\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"Better luck next time! 😔\n"
                msg += f"⏰ {get_current_time_str()}"
                
                await context.bot.send_message(chat_id=t['chat_id'], text=msg, parse_mode='Markdown')
                trade_engine.remove_trade(t['id'])
                continue
                
            if t3_new_hit:
                msg = f"🚀🚀 **FULL TARGET HIT! (1:3 RR)** 🚀🚀\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"👑 YOU ARE A TRADING LEGEND! 🥂💰\n\n"
                msg += f"🔸 **Pair:** {base_msg_info}\n"
                msg += f"🔸 **Final Target:** `{t['t3']}`\n"
                msg += f"🔸 **Current Price:** `{current_price}`\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"_Tracker auto-closed. Enjoy your gains!_\n"
                msg += f"⏰ {get_current_time_str()}"

                await context.bot.send_message(chat_id=t['chat_id'], text=msg, parse_mode='Markdown')
                trade_engine.remove_trade(t['id'])
                continue
                
            if t2_new_hit:
                msg = f"🔥 **TARGET 2 SMASHED! (1:2 RR)** 🔥\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"🕺 Unstoppable! Massive profits! 🍾\n\n"
                msg += f"🔸 **Pair:** {base_msg_info}\n"
                msg += f"🔸 **Target Reached:** `{t['t2']}`\n"
                msg += f"🔸 **Current Price:** `{current_price}`\n"
                msg += f"🔒 **Stop Loss Moved to T1:** `{t['t1']}`\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"⏰ {get_current_time_str()}"

                await context.bot.send_message(chat_id=t['chat_id'], text=msg, parse_mode='Markdown')
                trade_engine.update_trade_target_hit(t['id'], 2)
                trade_engine.update_trade_sl(t['id'], t['t1'])
                t['t2_hit'] = True 
                
            if t1_new_hit and not t['t1_hit']: 
                msg = f"💸 **TARGET 1 SECURED! (1:1.5 RR)** 💸\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"🎉 Great job! We are in profit! 🤑\n\n"
                msg += f"🔸 **Pair:** {base_msg_info}\n"
                msg += f"🔸 **Target Reached:** `{t['t1']}`\n"
                msg += f"🔸 **Current Price:** `{current_price}`\n"
                msg += f"🔒 **Stop Loss Moved to Entry:** `{t['entry_price']}`\n"
                msg += f"━━━━━━━━━━━━━━━━━━\n"
                msg += f"⏰ {get_current_time_str()}"

                await context.bot.send_message(chat_id=t['chat_id'], text=msg, parse_mode='Markdown')
                trade_engine.update_trade_target_hit(t['id'], 1)
                trade_engine.update_trade_sl(t['id'], t['entry_price'])
        except Exception as e:
            import logging
            logging.error(f"Failed to send trade alert to {t['chat_id']}: {e}")

async def adduser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id
    if not auth.is_owner(chat_id):
        await update.message.reply_text("❌ Only the Owner can use this command.")
        return
        
    if not context.args:
        await update.message.reply_text("ℹ️ Usage: /adduser <chat_id>\nExample: /adduser 123456789")
        return
        
    try:
        new_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Chat ID must be a number.")
        return
        
    success = auth.add_user(new_id)
    if success:
        await update.message.reply_text(f"✅ User `{new_id}` has been authorized to use the bot.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"⚠️ User `{new_id}` is already authorized or is the owner.", parse_mode='Markdown')

async def removeuser_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id
    if not auth.is_owner(chat_id):
        await update.message.reply_text("❌ Only the Owner can use this command.")
        return
        
    if not context.args:
        await update.message.reply_text("ℹ️ Usage: /removeuser <chat_id>\nExample: /removeuser 123456789")
        return
        
    try:
        rem_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Chat ID must be a number.")
        return
        
    success = auth.remove_user(rem_id)
    if success:
        await update.message.reply_text(f"✅ User `{rem_id}` authorization revoked.", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"⚠️ User `{rem_id}` is not in the allowed list.", parse_mode='Markdown')

async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id
    if not auth.is_owner(chat_id):
        await update.message.reply_text("❌ Only the Owner can use this command.")
        return
        
    data = auth.get_auth_data()
    text = f"👑 **Owner ID:** `{data['owner']}`\n\n👥 **Allowed Users:**\n"
    if not data["allowed_users"]:
        text += "- None -"
    else:
        for u in data["allowed_users"]:
            text += f"- `{u}`\n"
            
    await update.message.reply_text(text, parse_mode='Markdown')

async def session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from session_engine import SESSIONS, get_pkt_now, get_all_active_sessions
    now = get_pkt_now()
    active = get_all_active_sessions()
    
    text = f"🌍 **GLOBAL FOREX SESSIONS** 🌍\n"
    text += f"⏰ *Current Time:* {now.strftime('%I:%M %p')} (PKT)\n\n"
    
    for name, s in SESSIONS.items():
        if name in active:
            status = "✅ OPEN"
        else:
            status = "🔴 CLOSED"
            
        start_str = f"{s['start']:02d}:00" if s['start'] >= 10 else f"0{s['start']}:00"
        end_str = f"{s['end']:02d}:00" if s['end'] >= 10 else f"0{s['end']}:00"
        text += f"{s['emoji']} **{name}**: {status}\n  └ _Hours:_ {start_str} - {end_str} PKT\n\n"
        
    await update.message.reply_text(text, parse_mode='Markdown')

async def notify_sessions(context: ContextTypes.DEFAULT_TYPE):
    from session_engine import check_for_state_changes
    from auth import get_auth_data
    
    msgs = check_for_state_changes()
    if not msgs:
         return
         
    auth_data = get_auth_data()
    all_users = set(auth_data['allowed_users'])
    if auth_data['owner']:
        all_users.add(auth_data['owner'])
        
    combined_msg = "🔔 **SESSION UPDATE** 🔔\n\n" + "\n\n".join(msgs) + "\n\n_Use /session to check all status._"
    
    for uid in all_users:
        try:
            await context.bot.send_message(chat_id=uid, text=combined_msg, parse_mode='Markdown')
        except Exception as e:
            pass

async def check_news_alerts(context: ContextTypes.DEFAULT_TYPE):
    from news_api import check_and_get_news_alerts
    from auth import get_auth_data
    
    alerts = check_and_get_news_alerts()
    if not alerts:
         return
         
    auth_data = get_auth_data()
    all_users = set(auth_data['allowed_users'])
    if auth_data['owner']:
        all_users.add(auth_data['owner'])
        
    for item in alerts:
        title = item['title'].lower()
        # Handle exceptions where Higher = Bad for USD
        if 'unemployment' in title or 'jobless' in title:
            impact_high = "USD weakens 🔴 -> Gold/Crypto Pumps 🟢"
            impact_low = "USD strengthens 🟢 -> Gold/Crypto Drops 🔴"
        else:
            impact_high = "USD strengthens 🟢 -> Gold/Crypto Drops 🔴"
            impact_low = "USD weakens 🔴 -> Gold/Crypto Pumps 🟢"

        # Convert event UTC time to PKT for display
        event_time_utc = item.get('event_time_utc')
        if event_time_utc:
            import datetime as _dt
            event_time_pkt = event_time_utc + _dt.timedelta(hours=5)
            event_time_str = event_time_pkt.strftime('%I:%M %p PKT')
        else:
            event_time_str = "N/A"

        msg = f"⚠️ **HIGH IMPACT NEWS APPROACHING** ⚠️\n\n"
        msg += f"📰 **Event:** `{item['title']}`\n"
        msg += f"🕐 **Scheduled At:** `{event_time_str}`\n"
        msg += f"⏳ **Time Left:** `~{item['time_left']} mins`\n"
        msg += f"📉 **Forecast:** `{item['forecast']}` (Previous Data: `{item['previous']}`)\n\n"
        msg += f"📊 **Market Impact Guide:**\n"
        msg += f"▪️ If data comes > Forecast: {impact_high}\n"
        msg += f"▪️ If data comes < Forecast: {impact_low}\n\n"
        msg += f"💡 _Manage your open positions! Expect extreme volatility._\n"
        
        for uid in all_users:
            try:
                await context.bot.send_message(chat_id=uid, text=msg, parse_mode='Markdown')
            except Exception:
                pass

async def todaynews_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from news_api import get_today_high_impact_news
    
    await update.message.reply_text("⏳ Fetching today's high impact USD news...")
    
    events = get_today_high_impact_news()
    
    if not events:
        await update.message.reply_text(
            "✅ No high impact USD news scheduled for today!\n"
            f"⏰ {get_current_time_str()}"
        )
        return
    
    # Get today's date in PKT
    today_pkt = (datetime.datetime.utcnow() + datetime.timedelta(hours=5)).strftime('%d %b %Y')
    
    text = f"📅 **Today's High Impact USD News** ({today_pkt})\n"
    text += f"━━━━━━━━━━━━━━━━━━\n\n"
    
    for e in events:
        time_str = e['event_time_pkt'].strftime('%I:%M %p')
        status_emoji = "✅" if e['is_past'] else "🔴"
        text += f"{status_emoji} **{time_str} PKT** — `{e['title']}`\n"
        text += f"   📊 Forecast: `{e['forecast']}` | Prev: `{e['previous']}`\n"
        text += f"   _{e['status']}_\n\n"
    
    text += f"━━━━━━━━━━━━━━━━━━\n"
    text += f"🔴 = Upcoming  |  ✅ = Already Released\n"
    text += f"⏰ {get_current_time_str()}"
    
    await update.message.reply_text(text, parse_mode='Markdown')

def setup_bot():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: Set TELEGRAM_BOT_TOKEN environment variable!")
        return None
    
    application = ApplicationBuilder().token(token.strip()).build()

    application.add_handler(TypeHandler(Update, auth_middleware), group=-1)

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('spotprice', spot_command))
    application.add_handler(CommandHandler('swapprice', swap_command))
    application.add_handler(CommandHandler('forexprice', forex_command))
    application.add_handler(CommandHandler('gold', gold_command))
    application.add_handler(CommandHandler('setspotalert', setspot_command))
    application.add_handler(CommandHandler('setswapalert', setswap_command))
    application.add_handler(CommandHandler('setforexalert', setforex_command))
    application.add_handler(CommandHandler('setgoldalert', setgold_command))
    application.add_handler(CommandHandler('rsi', rsi_command))
    application.add_handler(CommandHandler('scan_rsi', scan_rsi_command))
    application.add_handler(CommandHandler('deletealert', deletealert_command))
    application.add_handler(CommandHandler('list', list_command))
    application.add_handler(CommandHandler('tracktrade', tracktrade_command))
    application.add_handler(CommandHandler('mytrades', mytrades_command))
    application.add_handler(CommandHandler('deletetrade', deletetrade_command))
    application.add_handler(CommandHandler('adduser', adduser_command))
    application.add_handler(CommandHandler('removeuser', removeuser_command))
    application.add_handler(CommandHandler('users', users_command))
    application.add_handler(CommandHandler('session', session_command))
    application.add_handler(CommandHandler('todaynews', todaynews_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    job_queue = application.job_queue
    job_queue.run_repeating(check_alerts, interval=20, first=10)
    job_queue.run_repeating(check_active_trades, interval=20, first=15)
    job_queue.run_repeating(notify_sessions, interval=60, first=5)
    job_queue.run_repeating(check_news_alerts, interval=900, first=20)
    
    return application

if __name__ == '__main__':
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    keep_alive()
    
    app = setup_bot()
    if app:
        print("Bot is up and running in polling mode...")
        app.run_polling()

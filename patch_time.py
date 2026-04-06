import re

with open("main.py", "r", encoding="utf-8") as f:
    code = f.read()

# Add get_current_time_str helper
if "def get_current_time_str():" not in code:
    code = code.replace(
        "import datetime",
        "import datetime\n\ndef get_current_time_str():\n    return datetime.datetime.utcnow().strftime('%d-%b-%Y  %I:%M:%S %p (UTC)')\n"
    )

# Patch live price messages
code = re.sub(
    r'(await update\.message\.reply_text\(f"(?:🪙|💵|⚜️) (?:Spot|Swap|Live) Price for \{[^\}]+\}: \{[^\}]+\})("\))',
    r'\1\\n⏰ {get_current_time_str()}"\)',
    code
)

# Patch button handler
code = re.sub(
    r'(await query\.edit_message_text\(text=f"📈 Live Price for \{[^\}]+\}: \{[^\}]+\})("\))',
    r'\1\\n⏰ {get_current_time_str()}"\)',
    code
)

# Patch setalert confirmations
code = re.sub(
    r'(\(Current price is \{current_price\}\))(")',
    r'\1\\n⏰ Time: {get_current_time_str()}"',
    code
)

# Patch list command
code = re.sub(
    r'(text = "📋 \*\*Your Active Alerts:\*\*\\n\\n")',
    r'text = f"📋 **Your Active Alerts:**\\n⏰ {get_current_time_str()}\\n\\n"\n',
    code
)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Patching complete!")

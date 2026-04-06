with open("main.py", "r", encoding="utf-8") as f:
    text = f.read()
text = text.replace('")\)', '")')
text = text.replace('"\\)', '")')
with open("main.py", "w", encoding="utf-8") as f:
    f.write(text)

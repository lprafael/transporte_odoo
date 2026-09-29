import re

with open('scratch/broker_chat_text.txt', 'r', encoding='utf-8') as f:
    text = f.read()

# Let's extract the actual conversation content
# In Gemini web dumps, conversation usually starts after UI elements
# Let's find lines that discuss the broker, architecture, transport, etc.
lines = text.splitlines()

# Filter out empty or duplicate lines
cleaned_lines = []
last_line = ""
for line in lines:
    line_s = line.strip()
    # Skip UI chrome
    if line_s in ["Gemini", "Compartir", "Share", "Expandir", "Colapsar", "Copiar", "Editar", "Reintentar"]:
        continue
    if line_s and line_s != last_line:
        cleaned_lines.append(line_s)
        last_line = line_s

full_cleaned = "\n".join(cleaned_lines)
with open('scratch/broker_chat_clean.txt', 'w', encoding='utf-8') as f:
    f.write(full_cleaned)

print(f"Cleaned lines: {len(cleaned_lines)}")

# Look for user queries and model responses
# Print a table of contents or main headings
headings = [line for line in cleaned_lines if line.startswith("#") or (len(line) < 80 and any(w in line.lower() for w in ["broker", "arquitectura", "gps", "componente", "fase", "paso", "conclusión", "pregunta"]))]
print(f"Key headings/lines found: {len(headings)}")
for h in headings[:30]:
    print(f" - {h}")

import subprocess
import time
import os
import re
import html

url = "https://gemini.google.com/share/066f21229f5b"
edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not os.path.exists(edge_path):
    edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

print(f"Using Edge at: {edge_path}")
print(f"Target URL: {url}")

cmd = [
    edge_path,
    "--headless",
    "--disable-gpu",
    "--virtual-time-budget=20000",
    "--dump-dom",
    url
]

out_file = r"scratch/broker_chat_dump.html"
with open(out_file, "w", encoding="utf-8") as f:
    res = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

print(f"Dump complete. Status: {res.returncode}. Output size: {os.path.getsize(out_file)} bytes")

with open(out_file, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

# Strip tags to get clean readable text
# Replace <br> and </p>, </div>, </li>, </tr> with newlines
cleaned = re.sub(r'(?i)<(br|p|div|li|tr|h1|h2|h3|h4|h5|h6)[^>]*>', '\n', content)
cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
cleaned = html.unescape(cleaned)
# Normalize spaces
lines = [line.strip() for line in cleaned.splitlines()]
lines = [l for l in lines if l]
all_text = '\n'.join(lines)

with open("scratch/broker_chat_text.txt", "w", encoding="utf-8") as f:
    f.write(all_text)

print(f"Text extraction complete. Total lines: {len(lines)}, chars: {len(all_text)} saved to scratch/broker_chat_text.txt")

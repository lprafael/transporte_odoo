# -*- coding: utf-8 -*-
import urllib.request
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

url = 'https://gemini.google.com/share/c0013c1f3c1c?skid=c90a4531-74b9-482d-92cc-03ce2080173a'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
try:
    with urllib.request.urlopen(req) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
        
    print(f"HTML downloaded. Length: {len(html)}")
    
    # Check for words in HTML
    words = ['almacenamiento', 'telemetria', 'traccar', 'timescale', 'geocerca', 'coordenadas', 'mosquitto', 'emqx', 'redis', 'database', 'base de datos']
    for w in words:
        matches = list(re.finditer(w, html, re.IGNORECASE))
        print(f"Word '{w}': {len(matches)} matches")
        if matches:
            for m in matches[:2]:
                snippet = html[max(0, m.start()-100):min(len(html), m.end()+100)]
                print(f"   Snippet: {snippet.strip()}")
                
except Exception as e:
    print(f"Error: {e}")

# -*- coding: utf-8 -*-
import urllib.request
import urllib.parse
import re
import json

url = 'https://gemini.google.com/share/c0013c1f3c1c?skid=c90a4531-74b9-482d-92cc-03ce2080173a'
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-419,es;q=0.9,en;q=0.8'
})
with urllib.request.urlopen(req) as resp:
    html = resp.read().decode('utf-8', errors='ignore')

# Extract WIZ_global_data
wiz_match = re.search(r'window\.WIZ_global_data\s*=\s*(\{.*?\});', html, re.DOTALL)
if wiz_match:
    try:
        data = json.loads(wiz_match.group(1))
        print("WIZ keys:", list(data.keys()))
        at = data.get("SNlM0e", "")
        print("at token:", at)
    except Exception as e:
        print("Error parsing WIZ:", e)

# Look for RPC calls for shared chat
# Usually URL is: /_/BardChatUi/data/batchexecute
# We can test RPCs
rpc_candidates = ['o8xXec', 'd22x4b', 'fK9Jle', 'q64D9c', 'wX9L3b', 'rO0T1e']
share_id = 'c0013c1f3c1c'

for rpc in rpc_candidates:
    rpc_payload = [[[rpc, json.dumps([share_id]), None, "generic"]]]
    body = urllib.parse.urlencode({
        'f.req': json.dumps(rpc_payload),
        'at': at
    }).encode('utf-8')
    
    exec_url = 'https://gemini.google.com/_/BardChatUi/data/batchexecute?rpcids=' + rpc + '&_reqid=123456&rt=c'
    req2 = urllib.request.Request(exec_url, data=body, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'
    })
    try:
        with urllib.request.urlopen(req2) as resp2:
            res_text = resp2.read().decode('utf-8', errors='ignore')
            if share_id in res_text or 'almacenamiento' in res_text.lower() or len(res_text) > 1000:
                print(f"RPC {rpc} responded with {len(res_text)} bytes!")
                with open(f"scratch/rpc_{rpc}.txt", "w", encoding="utf-8") as out:
                    out.write(res_text)
            else:
                print(f"RPC {rpc}: len {len(res_text)}")
    except Exception as e:
        print(f"RPC {rpc} error:", e)

# -*- coding: utf-8 -*-
import urllib.request
import json

def test_waze():
    # 1. Endpoint /api/v1/waze/traffic
    with urllib.request.urlopen("http://localhost:8088/api/v1/waze/traffic") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode('utf-8'))
        print(f"1. /api/v1/waze/traffic OK! Source: {data.get('source')} | Alerts: {data.get('total_alerts')} | Jams: {data.get('total_jams')}")

    # 2. Endpoint /api/v1/waze/corridor-impacts
    with urllib.request.urlopen("http://localhost:8088/api/v1/waze/corridor-impacts") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode('utf-8'))
        impacts = data.get("corridor_impacts", {})
        print(f"2. /api/v1/waze/corridor-impacts OK! Corridors impacted: {len(impacts)}")
        for r_id, imp in impacts.items():
            print(f"   - [{r_id.upper()}] Severity: {imp.get('severity')} | Delay: +{imp.get('total_delay_minutes')} min | Summary: {imp.get('summary_text')}")

    # 3. HTML /map contains Waze layers
    with urllib.request.urlopen("http://localhost:8088/map") as resp:
        html = resp.read().decode('utf-8')
        assert "chk-waze-jams" in html
        assert "chk-waze-alerts" in html
        assert "fetchAndRenderWaze" in html
        print(f"3. /map (Radar GPS) OK! Waze layers & controls present (Length: {len(html)} bytes)")

    # 4. HTML /headway contains Waze integration
    with urllib.request.urlopen("http://localhost:8088/headway") as resp:
        html = resp.read().decode('utf-8')
        assert "modal-waze-card" in html
        assert "modal-waze-nav-btn" in html
        print(f"4. /headway (Tablero Lineal) OK! Waze card & deep-links present (Length: {len(html)} bytes)")

if __name__ == "__main__":
    test_waze()

# -*- coding: utf-8 -*-
import urllib.request
import json

def test_endpoints():
    headway_url = "http://localhost:8088/headway"
    map_url = "http://localhost:8088/map?bus=00005"
    data_url = "http://localhost:8088/api/v1/headway/data"

    with urllib.request.urlopen(headway_url) as resp:
        html = resp.read().decode('utf-8')
        assert resp.status == 200
        assert "bus-modal" in html
        assert "btn-sound-toggle" in html
        assert "playBunchingTone" in html
        assert "locateSelectedBusOnMap" in html
        print("HEADWAY HTML OK! Bytes:", len(html))

    with urllib.request.urlopen(map_url) as resp:
        html = resp.read().decode('utf-8')
        assert resp.status == 200
        assert "focusBus" in html
        assert "_hasAutoFocusedBus" in html
        print("MAP RADAR HTML OK! Bytes:", len(html))

    with urllib.request.urlopen(data_url) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        print(f"HEADWAY DATA OK! Active buses: {data.get('total_active_buses')} | Bunching: {data.get('total_bunching_alerts')}")

if __name__ == "__main__":
    test_endpoints()

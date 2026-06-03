import urllib.request, re

# The sz codes might need different prefix in the API
codes = {
    "sz002741": "sz002741", 
    "sz000997": "sz000997", 
    "sz002816": "sz002816",
    "sz001366": "sz001366",
    "sz002576": "sz002576",
    "sz001266": "sz001266"
}

for code, api_code in codes.items():
    try:
        url = f"https://qt.gtimg.cn/q={api_code}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        raw = resp.read()
        text = raw.decode('gbk')
        # Extract the name - format: ="1~NAME~CODE~...
        parts = text.split('~')
        if len(parts) >= 3:
            name = parts[1]
            ccode = parts[2]
            print(f"{code}: {name} ({ccode})")
    except Exception as e:
        print(f"{code}: ERROR {e}")

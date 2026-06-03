import urllib.request, re

codes = ["sh603373", "sh603127", "sh600246", "sz002965"]
for code in codes:
    try:
        url = f"https://qt.gtimg.cn/q={code}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        text = resp.read().decode('gbk')
        parts = text.split('~')
        if len(parts) >= 3:
            print(f"{code}: {parts[1]}")
    except Exception as e:
        print(f"{code}: ERROR")

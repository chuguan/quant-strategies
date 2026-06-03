import urllib.request, re, json

codes = ["sh603867", "sz002741", "sz000997", "sh603890", "sz002816", "sz001366", "sh601208", "sh603800", "sz002576", "sz001266"]

names = {}
for code in codes:
    try:
        url = f"https://qt.gtimg.cn/q={code}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=5)
        raw = resp.read()
        # Try GBK decode
        text = raw.decode('gbk')
        m = re.search(r'="1~(.+?)~' + code[2:], text)
        if m:
            names[code] = m.group(1).strip()
            print(f"{code}: {m.group(1)}")
    except Exception as e:
        print(f"{code}: ERROR {e}")

print("\n--- 冠军排名 ---")
print(f"{'排名':<4} {'代码':<12} {'名称':<12} {'买入价':<10}")
print("-"*40)

# Latest close price info
import json
cache = r"C:\Users\12546\AppData\Local\hermes\hermes-agent\cache"

prices = {}
for code in codes:
    fn = f"{cache}\\{code}.json"
    try:
        with open(fn, 'rb') as f:
            d = json.loads(f.read().decode('utf-8'))
        r = d[-1]
        prices[code] = r['close']
    except:
        prices[code] = "?"

rankings = [
    ("🥇", "sh603867"),
    ("🥈", "sz002741"),
    ("🥉", "sz000997"),
    ("4", "sh603890"),
    ("5", "sz002816"),
    ("6", "sz001366"),
    ("7", "sh601208"),
    ("8", "sh603800"),
    ("9", "sz002576"),
    ("10", "sz001266"),
]

for rank, code in rankings:
    name = names.get(code, "?")
    price = prices.get(code, "?")
    if isinstance(price, (int, float)):
        print(f"{rank:<4} {code:<12} {name:<12} {price:<10.2f}")
    else:
        print(f"{rank:<4} {code:<12} {name:<12} {price}")

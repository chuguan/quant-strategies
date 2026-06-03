"""超人v2.1 今日选股 — 逐个API"""
import urllib.request, json, pickle, time

with open('big_cache.pkl','rb') as f:
    c = pickle.load(f)
names, real = c['names'], c['real']
codes = [c for c in names if c.startswith('sh6') or c.startswith('sz00') or c.startswith('sz001') or c.startswith('sz002')]
print(f'主板: {len(codes)}只', flush=True)

def score_stock(pct, vr, cl):
    sc = 10
    if 4.5 <= pct <= 6.5: sc += 12
    elif 6.5 < pct <= 7: sc += 5
    elif 4.0 <= pct < 4.5: sc += 5
    if 60 <= cl <= 85: sc += 10
    if cl > 90: sc -= 15
    if 0.8 <= vr <= 1.5: sc += 10
    if pct > 7: sc -= 10
    if vr > 3: sc -= 10
    return sc

# 用腾讯K线API批量获取（已验证可以工作）
# 格式: https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=code,day,,,1,qfq
# 但单个查太慢，试试批量
# 用新浪的批量接口
# 或者用腾讯的批量hq接口

# 试试腾讯批量hq
url = 'https://web.ifzq.gtimg.cn/appstock/app/hq/v2/hq?codes='
# 取前500只股票
batch = codes[:500]
codes_str = ','.join(batch)
try:
    req = urllib.request.Request(url+codes_str, headers={'User-Agent':'Mozilla/5.0'})
    r = urllib.request.urlopen(req, timeout=10)
    data = json.loads(r.read())
print(f'API返回keys: {str(list(data.keys()))}', flush=True)
    if 'data' in data:
        dk = list(data['data'].keys())
        print(f'data keys: {str(dk)}', flush=True)
        if 'qt' in data['data']:
            print(f'qt type: {str(type(data["data"]["qt"]))}', flush=True)
            if isinstance(data['data']['qt'], list):
                qlen = len(data['data']['qt'])
                print(f'qt数量: {qlen}', flush=True)
                if data['data']['qt']:
                    print(f'qt[0] type: {type(data[\"data\"][\"qt\"][0])}', flush=True)
                    print(f'qt[0]: {str(data[\"data\"][\"qt\"][0])[:300]}', flush=True)
            elif isinstance(data['data']['qt'], dict):
                print(f'qt keys: {list(data[\"data\"][\"qt\"].keys())[:5]}', flush=True)
                k = list(data['data']['qt'].keys())[0]
                print(f'qt[{k}] type: {type(data[\"data\"][\"qt\"][k])}', flush=True)
                print(f'qt[{k}]: {str(data[\"data\"][\"qt\"][k])[:300]}', flush=True)
except Exception as e:
    print(f'API错误: {e}', flush=True)

# 也试试腾讯的另一个接口
print('\n尝试hq_str接口...', flush=True)
import subprocess
batch_str = ','.join(batch[:10])
r = subprocess.run(['curl','-s','--max-time','5',f'http://qt.gtimg.cn/q={batch_str}'], capture_output=True)
txt = r.stdout.decode('gbk', errors='replace')
print(txt[:500], flush=True)

"""
神龙启动 v1.0 — 五连板XGBoost识别策略
基于3年942个五连板数据训练，识别启动前信号

用法:
  from 神龙启动 import scan_dragon
  results = scan_dragon()  # 扫描全市场
"""
import os, sys, pickle, numpy as np, json, time
from datetime import datetime

SCRIPTS_DIR = os.path.expanduser('~/AppData/Local/hermes/scripts')
sys.path.insert(0, SCRIPTS_DIR)

# 加载模型
MODEL_PATH = os.path.join(SCRIPTS_DIR, 'five_board_3y_xgb.pkl')
if os.path.exists(MODEL_PATH):
    import joblib
    MODEL = joblib.load(MODEL_PATH)
    MODEL_LOADED = True
else:
    MODEL_LOADED = False
    print('⚠️ 模型未找到，请先训练')

PREFIX = lambda c: 'sh' if c.startswith('6') else 'sz'
IS_MAIN = lambda c: c.startswith(('600','601','603','605','000','001','002'))

def get_kline(code, days=20):
    """获取日K线数据"""
    import akshare as ak
    sym = f"{PREFIX(code)}{code}"
    try:
        df = ak.stock_zh_a_daily(symbol=sym, adjust='qfq')
        records = []; prev = None
        for _, row in df.iterrows():
            dt = str(row['date'])[:10]
            c = float(row['close'])
            o = float(row['open'])
            h = float(row['high'])
            l = float(row['low'])
            v = float(row['volume'])
            p = round((c - prev) / prev * 100, 2) if prev and prev > 0 else 0
            records.append({'date': dt, 'close': c, 'open': o, 'high': h, 'low': l, 
                           'volume': v, 'p': p})
            prev = c
        return records[-days:] if len(records) > days else records
    except:
        return None

def compute_features(records):
    """
    从7天K线提取特征
    返回特征向量和结构化数据
    """
    if len(records) < 7: return None
    
    pre7 = records[-7:]
    d0 = records[-1]  # 当天
    
    pre_ps = [x['p'] for x in pre7]
    pre_cls = [(x['close']-x['low'])/(x['high']-x['low'])*100 
               if (x['high']-x['low'])>0 else 50 for x in pre7]
    
    feats = np.array([[
        sum(pre_ps),                              # pre7_sum_p
        sum(1 for p in pre_ps if p>0),             # pre7_up_days
        sum(1 for p in pre_ps if p<0),             # pre7_down_days
        max(pre_ps) if pre_ps else 0,              # pre7_max_p
        min(pre_ps) if pre_ps else 0,              # pre7_min_p
        pre_ps[-1] if len(pre_ps)>=1 else 0,        # t_1_p
        pre_ps[-2] if len(pre_ps)>=2 else 0,        # t_2_p
        pre_ps[-3] if len(pre_ps)>=3 else 0,        # t_3_p
        sum(pre_cls)/len(pre_cls) if pre_cls else 50, # pre7_avg_cl
        pre_cls[-1] if len(pre_cls)>=1 else 50,      # t_1_cl
        pre_cls[-1]-pre_cls[-3] if len(pre_cls)>=3 else 0, # cl_trend_3d
        0, 0,  # d0_p, d0_cl (占位，实际用0)
    ]])
    
    detail = {
        'pre7_sum': round(sum(pre_ps), 1),
        'up_days': sum(1 for p in pre_ps if p>0),
        'down_days': sum(1 for p in pre_ps if p<0),
        'max_p': round(max(pre_ps), 1),
        'min_p': round(min(pre_ps), 1),
        't1_p': round(pre_ps[-1], 2),
        't2_p': round(pre_ps[-2], 2),
        'avg_cl': round(sum(pre_cls)/len(pre_cls), 1),
        't1_cl': round(pre_cls[-1], 1),
        'cl_trend': round(pre_cls[-1]-pre_cls[-3], 1),
        'today_p': round(d0['p'], 2),
        'today_cl': round((d0['close']-d0['low'])/(d0['high']-d0['low'])*100, 1) 
                    if (d0['high']-d0['low'])>0 else 50,
        'close': d0['close'],
    }
    return feats, detail

def scan_dragon(codes=None, top_n=10, min_prob=0.3, use_cache=True):
    """
    全市场扫描神龙启动信号
    
    Args:
        codes: 股票代码列表，None=全市场主板
        top_n: 输出前N只
        min_prob: 最小概率阈值
        use_cache: 优先使用big_cache（快）还是AkShare（慢但全）
    """
    if not MODEL_LOADED:
        return []
    
    # 获取股票列表
    if codes is None:
        pool = json.load(open(os.path.join(SCRIPTS_DIR, '活跃股票池_3043.json'), encoding='utf-8'))
        codes = sorted(set(c for c in pool['codes'] if IS_MAIN(c)))
    
    # 加载big_cache
    V13_DIR = os.path.join(SCRIPTS_DIR, 'release', 'V13')
    with open(os.path.join(V13_DIR, 'big_cache_full.pkl'), 'rb') as f:
        d = pickle.load(f)
    data, names = d['data'], d['names']
    dates = sorted(data.keys())
    
    if use_cache:
        return _scan_from_cache(codes, data, dates, names, top_n, min_prob)
    else:
        return _scan_from_akshare(codes, names, top_n, min_prob)

def _scan_from_cache(codes, data, dates, names, top_n, min_prob):
    """用big_cache扫描（快，约30秒）"""
    results = []
    latest_dates = dates[-10:]
    
    for code in codes:
        nm = names.get(code, '')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        
        stock_records = []
        for dt in reversed(latest_dates):
            if dt not in data: continue
            for s in data[dt]:
                if s['code'] == code:
                    stock_records.append({
                        'date': dt, 'p': s.get('p',0) or 0,
                        'cl': s.get('cl',50) or 50,
                        'close': s.get('close',0) or 0,
                    })
                    break
        
        if len(stock_records) < 8: continue
        
        # 今日涨幅在3-8.5%之间（强但没封板，有望晋级涨停）
        today_p = stock_records[0]['p']
        if today_p < 3 or today_p >= 9.5: continue
        
        # 前7天
        pre7 = stock_records[1:8]
        if len(pre7) < 7: continue
        
        pre_ps = [x['p'] for x in pre7]
        pre_cls = [x['cl'] for x in pre7]
        
        # 用实际今日涨幅做d0_p
        feats = np.array([[
            sum(pre_ps),
            sum(1 for p in pre_ps if p>0),
            sum(1 for p in pre_ps if p<0),
            max(pre_ps) if pre_ps else 0,
            min(pre_ps) if pre_ps else 0,
            pre_ps[-1], pre_ps[-2] if len(pre_ps)>=2 else 0,
            pre_ps[-3] if len(pre_ps)>=3 else 0,
            sum(pre_cls)/len(pre_cls) if pre_cls else 50,
            pre_cls[-1] if pre_cls else 50,
            pre_cls[-1]-pre_cls[-3] if len(pre_cls)>=3 else 0,
            today_p,  # d0_p = 今日实际涨幅
            stock_records[0]['cl'],  # d0_cl
        ]])
        
        prob = MODEL.predict_proba(feats)[0][1]
        
        if prob >= min_prob:
            detail = {
                'pre7_sum': round(sum(pre_ps), 1),
                'up_days': sum(1 for p in pre_ps if p>0),
                'down_days': sum(1 for p in pre_ps if p<0),
                'max_p': round(max(pre_ps), 1),
                'min_p': round(min(pre_ps), 1),
                't1_p': round(pre_ps[-1], 2),
                'avg_cl': round(sum(pre_cls)/len(pre_cls), 1),
                'today_p': round(today_p, 2),
            }
            results.append((code, nm, round(prob, 3), detail))
    
    results.sort(key=lambda x: -x[2])
    return results[:top_n]

def _scan_from_akshare(codes, names, top_n, min_prob):
    """用AkShare逐只下载（慢但数据全）"""
    import akshare as ak
    results = []
    
    for i, code in enumerate(codes[:500]):  # 限500只
        rec = get_kline(code, days=14)
        if not rec or len(rec) < 8: continue
        if rec[-1]['p'] >= 9.5: continue
        nm = names.get(code, '')
        if 'ST' in nm or '*ST' in nm or '退' in nm: continue
        
        feats, detail = compute_features(rec)
        if feats is None: continue
        
        prob = MODEL.predict_proba(feats)[0][1]
        if prob >= min_prob:
            results.append((code, nm, round(prob, 3), detail))
        
        if (i+1) % 100 == 0:
            print(f'  [{i+1}/{min(500,len(codes))}] 已发现{len(results)}个')
        time.sleep(0.05)
    
    results.sort(key=lambda x: -x[2])
    return results[:top_n]

def format_dragon(results):
    """格式化输出"""
    if not results:
        return '🐉 神龙启动: 今日无信号'
    
    lines = [f'🐉 神龙启动 v1.0 — 五连板预测 {datetime.now().strftime("%Y-%m-%d")}']
    lines.append(f'{"":-^55}')
    lines.append(f'{"#":>2} {"名称":>8} {"代码":>6} {"概率":>6} {"T-1涨":>6} {"前7天":>6} {"最大":>5} {"最小":>5} {"CL":>4}')
    lines.append(f'{"":-^55}')
    
    for i, (code, nm, prob, d) in enumerate(results, 1):
        prob_str = f'{prob*100:.0f}%' if prob >= 0.7 else f'{prob*100:.0f}%'
        marker = '🐉' if prob >= 0.7 else '⭐' if prob >= 0.5 else '○'
        lines.append(f'{i:>2} {nm[:6]:>8} {code:>6} {prob_str:>6} {d["t1_p"]:>+5.1f}% {d["pre7_sum"]:>+5.1f}% {d["max_p"]:>+4.1f}% {d["min_p"]:>+4.1f}% {d["avg_cl"]:>4.0f} {marker}')
    
    lines.append(f'{"":-^55}')
    lines.append(f'🐉 规则: 前7天洗盘+放量+预热 → T日启动涨停')
    return '\n'.join(lines)

if __name__ == '__main__':
    results = scan_dragon(top_n=10, min_prob=0.3)
    print(format_dragon(results))

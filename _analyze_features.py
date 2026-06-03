import pickle
import numpy as np

# 加载原版features_30d.pkl分析特征含义
pkl_path = r'C:\Users\12546\AppData\Local\hermes\scripts\release\V13\features_30d.pkl'
with open(pkl_path, 'rb') as f:
    feat = pickle.load(f)

print(f'类型: {type(feat)}')
if isinstance(feat, dict):
    # 看一个样例
    keys = list(feat.keys())
    print(f'条目数: {len(keys)}')
    sample_key = keys[0]
    print(f'键格式: {sample_key}')
    sample_val = feat[sample_key]
    print(f'值类型: {type(sample_val)}')
    if isinstance(sample_val, dict):
        print(f'键列表: {list(sample_val.keys())}')
        print(f'值: {sample_val}')
    
    # 统计各字段分布
    print('\n=== 各字段统计 ===')
    stats = {}
    for k, v in feat.items():
        if isinstance(v, dict):
            for fk, fv in v.items():
                if fk not in stats:
                    stats[fk] = []
                if fv is not None:
                    stats[fk].append(fv)
    
    for fk, vals in stats.items():
        if vals:
            arr = np.array(vals)
            print(f'{fk}: min={arr.min():.2f} max={arr.max():.2f} mean={arr.mean():.2f} median={np.median(arr):.2f} (n={len(vals)})')
    
    # 看几个t4_shadow, cons_up, peak_decay的例子
    print('\n=== t4_shadow > 30 的例子 ===')
    big_t4s = [(k, v) for k, v in feat.items() if isinstance(v, dict) and v.get('t4_shadow', 0) > 30]
    for k, v in big_t4s[:5]:
        print(f'{k}: {v}')
    
    print('\n=== cons_up >= 5 的例子 ===')
    big_cu = [(k, v) for k, v in feat.items() if isinstance(v, dict) and v.get('cons_up', 0) >= 5]
    for k, v in big_cu[:5]:
        print(f'{k}: {v}')
    
    print('\n=== peak_decay > 5 的例子 ===')
    big_pd = [(k, v) for k, v in feat.items() if isinstance(v, dict) and v.get('peak_decay', 0) > 5]
    for k, v in big_pd[:5]:
        print(f'{k}: {v}')
    
    # 看slope5的计算方法 — 与d1-d5的关系
    print('\n=== slope5 vs d1-d5 验证 ===')
    for k, v in list(feat.items())[:5]:
        if isinstance(v, dict):
            d = v
            print(f'{k}: d1={d.get("d1",0):.2f} d2={d.get("d2",0):.2f} d3={d.get("d3",0):.2f} d4={d.get("d4",0):.2f} d5={d.get("d5",0):.2f} slp5={d.get("slope5",0):.2f}')
            # 尝试反推slope5：是d1+d2+d3+d4+d5的均值？
            dvals = [d.get(f'd{i}', 0) for i in range(1,6)]
            linear_fit = np.polyfit(range(5), dvals, 1)[0] if len(set(dvals)) > 1 else 0
            avg = np.mean(dvals)
            print(f'  线性斜率: {linear_fit:.4f}, 均值: {avg:.4f}, 差值绝对值: {abs(d.get("slope5", 0) - linear_fit):.4f}')

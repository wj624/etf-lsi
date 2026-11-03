# -*- coding: utf-8 -*-
"""
模块一 + 模块二 · 双宽基诊断
对沪深300、创业板两条赛道分别计算：
  持仓市值占比、250日分位、Spread 开口差、20日回归斜率、近5日份额净申赎、5档背离状态
输出：summary.json（含两条赛道）+ series_<key>.json（供绘图/看板）
"""
import json, os, sys, statistics

from config import TRACKS, ORDER

BASE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(BASE, 'raw_data.json')
SUMMARY = os.path.join(BASE, 'summary.json')

if not os.path.exists(RAW):
    print('!! 缺少 raw_data.json，请先运行 fetch_data.py')
    sys.exit(1)

with open(RAW, encoding='utf-8') as f:
    RAW_ALL = json.load(f)


def f(v):
    try:
        return float(v)
    except Exception:
        return None


def norm(series):
    lo, hi = min(series), max(series)
    rng = hi - lo if hi > lo else 1.0
    return [(v - lo) / rng * 100.0 for v in series]


def roll_norm(series, win=250):
    """滚动窗口归一化（0~100 分位）。

    展示窗口从 250 天扩到 5 年后，不能再对整段序列做 min/max —— 那样历史越长、
    极值越可能落在远端，近端曲线会被压成一条直线，Spread 的 ±25 阈值也就失去意义。
    这里对每个点只取它之前 win 个观测（不足则用已全部样本）做 min/max：
      · 最后一点 == 原来的整段 norm（窗口就是最后 250 天），今日读数完全不变；
      · 历史各点各自可比，扩窗不会让旧结论漂移。
    """
    out = []
    for i in range(len(series)):
        lo_i = max(0, i - win + 1)
        w = series[lo_i:i + 1]
        lo, hi = min(w), max(w)
        rng = hi - lo if hi > lo else 1.0
        out.append((series[i] - lo) / rng * 100.0)
    return out


def slope(ys, n=20):
    m = min(n, len(ys))
    y = ys[-m:]
    x = list(range(m))
    mx = sum(x) / m
    my = sum(y) / m
    den = sum((xi - mx) ** 2 for xi in x)
    if den == 0:
        return 0.0
    return sum((xi - mx) * (yi - my) for xi, yi in zip(x, y)) / den


def repair_price_steps(rows, etfs, near=10, th=1.5, jump=0.35):
    """修复单只 ETF 的「净值复权断点」，避免 5 年曲线出现假台阶。

    背景：westock 对个别 ETF 的历史净值/收盘价做过前复权（份额不变、价格整体打折）。
    实测 510310 在 2024-09-20 之前的净值只有真实值的一半，导致「份额×净值」在断点处凭空翻倍，
    5 年持仓占比曲线上就是一道 +17% 的假台阶。

    判据（两道，都得过）：
      ① 单日比值突变：ratio = nav ÷ 指数点位 对指数 ETF 长期近似常数，一天里变化超过 jump(35%)
         在数学上不可能，只可能是复权断点；
      ② 持续性：断点后 near(10) 个交易日的中位数与断点前 near 个相差超过 th(1.5) 倍。
    修正：断点之前的市值整体乘 (后/前)，链式循环直到找不到新的断点。
    只改 mvs（市值），不动 shares/nav，所以悬停明细里的份额、净值仍是原始值。
    """
    n = len(rows)
    logs = []
    for code, name, sym in etfs:
        ratio = []
        for x in rows:
            nv, ic = x['nav'].get(code), x['idx_close']
            ratio.append((nv / ic) if (nv and ic) else None)

        for _round in range(6):          # 最多修 6 处断点
            best, bi = 0.0, -1
            for i in range(1, n):
                a, b = ratio[i - 1], ratio[i]
                if not a or not b:
                    continue
                ch = abs(b / a - 1.0)
                if ch > best:
                    best, bi = ch, i
            if bi < 0 or best <= jump:
                break
            pre = [v for v in ratio[max(0, bi - near):bi] if v]
            post = [v for v in ratio[bi:bi + near] if v]
            if len(pre) < 3 or len(post) < 3:
                break
            mp, mo = statistics.median(pre), statistics.median(post)
            if not mp or not mo:
                break
            if 1.0 / th <= mo / mp <= th:      # 只是一次噪声尖刺，不是断点
                break
            k = mo / mp
            for j in range(bi):
                v = rows[j]['mvs'].get(code)
                if v:
                    rows[j]['mvs'][code] = v * k
                if ratio[j]:
                    ratio[j] *= k              # 同步基准，便于继续找下一个断点
            logs.append('%s %s 之前 ×%.3f（净值被前复权）' % (name, rows[bi]['date'], k))
    return logs


def analyze_track(key):
    cfg = TRACKS[key]
    etfs = cfg['etf_list']
    lbl = cfg['labels']

    daily = (RAW_ALL.get(key) or {}).get('daily') or {}
    if not daily:
        print('!! %s 无数据' % key)
        return None, None
    # 展示窗口由取数端决定（fetch_data.DAYS ≈ 5 年），这里不再二次截断到 250 天；
    # 分位/斜率等指标各自按固定窗口计算（见 roll_norm / slope），与展示长度解耦。
    dates = sorted(daily.keys())

    rows = []
    for d in dates:
        r = daily[d]
        mvs, tot, ok = {}, 0.0, True
        for code, name, sym in etfs:
            e = r.get(code) or {}
            sh = f(e.get('shares'))
            nv = f(e.get('nav')) or f(e.get('close'))
            # 口径1：优先 份额 × 单位净值(或收盘价)，避免接口 size 在份额未披露时连同市值一起冻结
            mv = (sh * nv) if (sh and nv) else f(e.get('size'))
            if mv is None:
                ok = False
                mv = 0.0
            mvs[code] = mv
            tot += mv
        rows.append({
            'date': d, 'etf_mv': tot if ok else None,
            'idx_close': f(r.get('idx_close')),
            # 兼容两种字段名：fetch_data 写入 idx_float_mv，历史缓存可能仍是 idx_mv
            'idx_mv': f(r.get('idx_float_mv')) or f(r.get('idx_mv')),
            'mvs': mvs,
            'shares': {c: f((r.get(c) or {}).get('shares')) for c, _, _ in etfs},
            'nav': {c: f((r.get(c) or {}).get('nav')) for c, _, _ in etfs},
            'chg': {c: f((r.get(c) or {}).get('sharesChg')) for c, _, _ in etfs},
        })

    # ---- 复权断点修复（净值被整体打折的 ETF，只影响市值，不影响持仓占比的量纲）----
    _fix = repair_price_steps(rows, etfs)
    if _fix:
        print('[%s] 检测到净值复权断点，已按比例还原：%s' % (key, '；'.join(_fix)))
        for x in rows:                  # 市值改动后必须重算合计
            vals = [x['mvs'].get(c) for c, _, _ in etfs]
            x['etf_mv'] = sum(vals) if all(v is not None for v in vals) else None

    # ---- 份额披露滞后识别（不捆绑 nav）----
    # 判据：只要 4 只 ETF 当日份额与前一日全部相同，即判定尚未披露并截断尾部
    def _is_stale(a, b):
        sa, sb = a.get('shares') or {}, b.get('shares') or {}
        valid = [c for c, _, _ in etfs if sa.get(c) is not None and sb.get(c) is not None]
        if not valid:
            return False
        return all(sa.get(c) == sb.get(c) for c in valid)

    stale_tail, i = 0, len(rows) - 1
    while i >= 1 and _is_stale(rows[i], rows[i - 1]):
        stale_tail += 1
        i -= 1
    latest_trading_day = rows[-1]['date'] if rows else None
    shares_asof = rows[-1 - stale_tail]['date'] if rows else None
    if stale_tail:
        print('[%s 份额披露滞后] %s 起的 %d 个交易日沿用上一次披露值，已截断至 %s'
              % (key, rows[-stale_tail]['date'], stale_tail, shares_asof))
        rows = rows[:len(rows) - stale_tail]

    # ---- chg 用相邻交易日真实份额差重算 ----
    for idx in range(1, len(rows)):
        prev_sh = rows[idx - 1].get('shares') or {}
        cur_sh = rows[idx].get('shares') or {}
        for c, _, _ in etfs:
            if cur_sh.get(c) is not None and prev_sh.get(c) is not None:
                rows[idx]['chg'][c] = cur_sh[c] - prev_sh[c]

    # ---- 流通市值单位归一（个别日期返回「亿元」）----
    _mv = [x['idx_mv'] for x in rows if x['idx_mv']]
    _med = statistics.median(_mv) if _mv else 0
    for x in rows:
        if x['idx_mv'] and _med and x['idx_mv'] < _med / 100:
            x['idx_mv'] = x['idx_mv'] * 1e8

    # ---- 缺失流通市值：用「流通市值/收盘价」比例的邻近值插值 ----
    valid = [x for x in rows if x['idx_mv'] and x['idx_close']]
    if valid:
        base_ratio = statistics.median([x['idx_mv'] / x['idx_close'] for x in valid])
        for x in rows:
            if not x['idx_mv'] and x['idx_close']:
                x['idx_mv'] = x['idx_close'] * base_ratio

    rows = [x for x in rows if x['etf_mv'] and x['idx_mv'] and x['idx_close']]
    if len(rows) < 30:
        print('!! %s 有效数据不足（%d 天）' % (key, len(rows)))
        return None, None

    dates = [x['date'] for x in rows]
    hold = [x['etf_mv'] / x['idx_mv'] * 100.0 for x in rows]
    idx = [x['idx_close'] for x in rows]
    hold_pct, idx_pct = roll_norm(hold), roll_norm(idx)
    spread = [a - b for a, b in zip(hold_pct, idx_pct)]

    N = 20
    hold_slope, idx_slope = slope(hold_pct, N), slope(idx_pct, N)
    idx_ret20 = (idx[-1] / idx[-1 - N] - 1) * 100 if len(idx) > N else 0.0
    hold_ret20 = (hold[-1] / hold[-1 - N] - 1) * 100 if len(hold) > N else 0.0

    def tot_shares(i):
        return sum([v for c, _, _ in etfs for v in [rows[i]['shares'].get(c)] if v])

    sh_now = tot_shares(-1)
    sh_5 = tot_shares(-6) if len(rows) > 6 else tot_shares(0)
    sh_1 = tot_shares(-2) if len(rows) > 2 else tot_shares(0)
    net5 = (sh_now - sh_5) / 1e8
    net1 = (sh_now - sh_1) / 1e8
    net5_ratio = (sh_now / sh_5 - 1) * 100 if sh_5 else 0.0

    cur_spread, hold_now, idx_now = spread[-1], hold[-1], idx[-1]
    significant_redeem = (net5 < 0) or (net1 < 0 and abs(net1) > 0.5 * max(abs(net5), 1e-9))
    significant_subscribe = net5 > 0

    if cur_spread <= -25:
        status, level = '🚨 负向大劈叉（主力已撤/指数虚高）', 'danger'
        reason = ('开口差值 %.1f ≤ -25：紫线（%s）高高在上、橙线（ETF持仓占比）大幅下台阶，持仓与指数严重背离。'
                  % (cur_spread, cfg['index_name']))
    elif cur_spread >= 25:
        status, level = '⚡ 正向大劈叉（指数超跌脱离持仓区）', 'warn'
        reason = ('开口差值 %+.1f ≥ +25：橙线（ETF持仓占比）锁仓高位、紫线（%s）深度回调，裂开大喇叭口。'
                  % (cur_spread, cfg['index_name']))
    elif (idx_slope > 0 or idx_pct[-1] > 65) and (hold_slope < 0 or significant_redeem):
        status, level = '⚠️ 疑似暗中减持（顶背离）', 'danger'
        reason = ('近20日%s分位斜率 %+.2f/日（分位 %.0f），但ETF持仓占比斜率 %+.2f/日，近5日份额净变化 %+.1f 亿份 → 指数向上而持仓撤退。'
                  % (cfg['index_name'], idx_slope, idx_pct[-1], hold_slope, net5))
    elif idx_ret20 < 0 and hold_ret20 > 0 and significant_subscribe:
        status, level = '🛡️ 疑似护盘吸筹（底背离）', 'good'
        reason = ('近20日%s %+.2f%%，但ETF持仓占比 %+.2f%%、近5日份额净申购 %+.1f 亿份 → 指数下跌而资金逆势加仓。'
                  % (cfg['index_name'], idx_ret20, hold_ret20, net5))
    else:
        status, level = '✅ 同步运行（差值正常）', 'ok'
        reason = '开口差值 %+.1f 处于 ±25 阈值内，两线近20日斜率同向，未触发背离或劈叉信号。' % cur_spread

    summary = dict(
        key=key, name=cfg['name'], title=cfg['title'],
        index_name=cfg['index_name'], index_code=cfg['index_code'],
        date=dates[-1], status=status, level=level, reason=reason,
        shares_asof=shares_asof, stale_tail=stale_tail,
        latest_trading_day=latest_trading_day,
        hold_pct=hold_now, idx_close=idx_now, spread=cur_spread,
        hold_slope=hold_slope, idx_slope=idx_slope,
        idx_ret20=idx_ret20, hold_ret20=hold_ret20,
        net5=net5, net1=net1, net5_ratio=net5_ratio,
        etf_mv=rows[-1]['etf_mv'], idx_mv=rows[-1]['idx_mv'],
        hold_pct_pos=hold_pct[-1], idx_pct_pos=idx_pct[-1],
        n=len(rows), span=(dates[0], dates[-1]),
        labels=lbl,
    )

    # 近 5 日每只 ETF 份额明细
    tail_n = min(5, len(rows))
    share_rows = []
    for j in range(len(rows) - tail_n, len(rows)):
        share_rows.append({
            'date': rows[j]['date'],
            'shares': {sym: rows[j]['shares'].get(c) for c, _, sym in etfs},
            'chg': {sym: rows[j]['chg'].get(c) for c, _, sym in etfs},
            'total_shares': sum([v for c, _, _ in etfs for v in [rows[j]['shares'].get(c)] if v]),
        })
    summary['share_rows'] = share_rows
    summary['etf_names'] = {sym: name for _, name, sym in etfs}

    pack = {
        'dates': dates, 'hold': hold, 'idx': idx,
        'hold_pct': hold_pct, 'idx_pct': idx_pct, 'spread': spread,
        'etf_mv': [x['etf_mv'] for x in rows],
        'per_etf': {sym: [x['mvs'].get(c) for x in rows] for c, _, sym in etfs},
        'per_etf_shares': {sym: [x['shares'].get(c) for x in rows] for c, _, sym in etfs},
        'per_etf_chg': {sym: [x['chg'].get(c) for x in rows] for c, _, sym in etfs},
        'names': {sym: name for _, name, sym in etfs},
        'summary': summary,
        'shares_asof': shares_asof, 'stale_tail': stale_tail,
        'latest_trading_day': latest_trading_day,
    }
    with open(os.path.join(BASE, 'series_%s.json' % key), 'w', encoding='utf-8') as fp:
        json.dump(pack, fp, ensure_ascii=False)
    print('[%s] %s | %s | Spread %+.1f | 净5日 %+.2f 亿份 | %d 天'
          % (key, summary['date'], status, cur_spread, net5, len(rows)))
    return summary, pack


def main():
    out = {'tracks': {}, 'order': []}
    for key in ORDER:
        s, _ = analyze_track(key)
        if s:
            out['tracks'][key] = s
            out['order'].append(key)
    if not out['tracks']:
        print('!! 两条赛道均无有效数据')
        sys.exit(1)
    out['asof'] = max(t['date'] for t in out['tracks'].values())
    with open(SUMMARY, 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False, indent=2)
    print('已写入 %s（赛道：%s）' % (SUMMARY, '、'.join(out['order'])))


if __name__ == '__main__':
    main()

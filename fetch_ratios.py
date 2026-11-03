# -*- coding: utf-8 -*-
"""
模块二 · 三大风格 / 股债比价（周K全周期百分位）

统一口径：三个比值都是「防御性资产 ÷ 进攻性资产」
  ① style_cyb ：中证红利低波(000922) ÷ 创业板指(399006)
  ② style_star：中证红利(000922)     ÷ 科创50(000688)
  ③ bond      ：十年国债ETF(511260)  ÷ 沪深300ETF(510300)

接口单次最多返回约 1210 根日K（≈5年），故改用周K：
按 4 年一段分段抓取拼接成全周期序列。已实测分段重叠处数值 100% 一致，
接口返回即前复权价，拼接安全、无分红除息假跳空。

输出：ratios.json
"""
import json, os, sys, time, bisect, statistics, datetime
from concurrent.futures import ThreadPoolExecutor

import common
from config import RATIO_PAIRS

OUT = os.path.join(common.BASE, 'ratios.json')

SEG_FROM = int(os.environ.get('RATIO_SEG_FROM', '2010'))
SEG_YEARS = 4
PERIOD = os.environ.get('RATIO_PERIOD', 'week')
TAIL = int(os.environ.get('RATIO_TAIL', '260'))

# 周K口径下的回顾窗口：4周≈1个月、12周≈1季、52周≈1年
W_M, W_Q, W_Y = 4, 12, 52


def get_series(code, fq=None):
    """周K全周期：按 4 年一段拼接"""
    segs, out, empty = [], {}, []
    y = SEG_FROM
    today = datetime.date.today().isoformat()
    this_year = datetime.date.today().year
    while y <= this_year:
        s, e = '%d-01-01' % y, '%d-12-31' % (y + SEG_YEARS - 1)
        # 最后一段天然跨到未来（2026-01-01 ~ 2029-12-31）。传未来日期这一段偶发整段返回空，
        # 2026-11-03 06:49 那次就是这样把 2026 全年丢掉的：序列停在 2025-12-31，
        # 比值拿去年的值当“当前值”，分位从 52% 掉到 16.5%，结论从“均衡”变成“红利低波性价比更高”。
        # 截到今天只影响最后一段，前面几段 end 都早于今天，行为不变。
        if e > today:
            e = today
        args = ['kline', code, '--period', PERIOD, '--start', s, '--end', e, '--limit', '500']
        if fq:
            args += ['--fq', fq]
        rows = common.parse_kline(common.run(args, retry=4, timeout=240))
        if not rows:
            time.sleep(1.2)
            rows = common.parse_kline(common.run(args, retry=4, timeout=240))
        if not rows:
            empty.append((s, e))
            print('  !! %s 段 %s~%s 抓空（两次各 4 次重试均无数据）' % (code, s, e), flush=True)
        segs.append((s, e, len(rows)))
        for d, c in rows:
            out[d] = c
        y += SEG_YEARS
    print('  %-10s %s  %d 根  %s ~ %s   分段:%s%s' %
          (code, PERIOD, len(out), min(out) if out else '-', max(out) if out else '-',
           ' '.join('%s:%d' % (a[:4], n) for a, _, n in segs),
           ('   空段:%s' % '、'.join('%s~%s' % x for x in empty)) if empty else ''),
          flush=True)
    return out, empty


def diagnose(pct):
    if pct >= 80:
        return 'high', '极端偏高'
    if pct >= 65:
        return 'high', '偏高'
    if pct > 35:
        return 'mid', '中性'
    if pct > 20:
        return 'low', '偏低'
    return 'low', '极端偏低'


def build(pair, series_map):
    nc, nf, nn = pair['num']
    dc, df, dn = pair['den']
    a = series_map.get(nc) or {}
    b = series_map.get(dc) or {}
    dates = sorted(set(a) & set(b))
    vals, dts = [], []
    for d in dates:
        try:
            v = a[d] / b[d]
        except Exception:
            continue
        vals.append(v)
        dts.append(d)
    if len(vals) < 60:
        print('!! %s 有效数据不足（%d）' % (pair['title'], len(vals)))
        return None

    cur = vals[-1]
    srt = sorted(vals)
    n = len(srt)

    def rank(v):
        return bisect.bisect_right(srt, v) / n * 100.0

    pct = rank(cur)
    level, word = diagnose(pct)

    def chg(k):
        if len(vals) > k and vals[-1 - k]:
            return (vals[-1] / vals[-1 - k] - 1) * 100.0
        return None

    def pct_ago(k):
        return rank(vals[-1 - k]) if len(vals) > k else None

    med = statistics.median(vals)

    def qval(p):
        i = min(n - 1, max(0, int(round(p / 100.0 * (n - 1)))))
        return srt[i]

    if level == 'high':
        label, advice = pair['high']
        tilt = pair['high_tilt']
    elif level == 'low':
        label, advice = pair['low']
        tilt = pair['low_tilt']
    else:
        label = '均衡，无明显性价比优势'
        advice = '比值处于历史中位区，攻守两端性价比接近，维持均衡配置'
        tilt = '均衡配置'

    try:
        d0 = datetime.datetime.strptime(dts[0], '%Y-%m-%d')
        d1 = datetime.datetime.strptime(dts[-1], '%Y-%m-%d')
        years = (d1 - d0).days / 365.25
    except Exception:
        years = None

    return {
        'key': pair['key'], 'title': pair['title'], 'formula': pair['formula'],
        'num_name': '%s(%s)' % (nn, nc[2:]), 'den_name': '%s(%s)' % (dn, dc[2:]),
        'up_word': pair['up_word'], 'down_word': pair['down_word'],
        'high_word': pair['high'][0], 'low_word': pair['low'][0],
        'num_short': nn, 'den_short': dn,
        'low_why': '%s已大幅跑输、性价比更高' % nn,
        'low_act': '买入%s，卖出%s' % (nn, dn),
        'high_why': '%s已大幅跑赢、相对偏贵（到顶）' % nn,
        'high_act': '卖出%s，买入%s' % (nn, dn),
        'asof': dts[-1], 'cur': cur, 'pct': pct, 'level': level, 'word': word,
        'min': min(vals), 'max': max(vals), 'median': med,
        'q20': qval(20), 'q80': qval(80),
        'mean': sum(vals) / len(vals),
        'period': PERIOD,
        'chg_m': chg(W_M), 'chg_q': chg(W_Q), 'chg_y': chg(W_Y),
        'pct_m': pct_ago(W_M), 'pct_q': pct_ago(W_Q), 'pct_y': pct_ago(W_Y),
        'pct20': pct_ago(W_Y), 'pct60': pct_ago(W_Q), 'pct250': pct_ago(W_M),
        'chg20': chg(W_Y), 'chg60': chg(W_Q), 'chg250': chg(W_M),
        'dev_median': (cur / med - 1) * 100.0,
        'label': label, 'advice': advice, 'tilt': tilt,
        'n': len(vals), 'start': dts[0], 'end': dts[-1],
        'years': round(years, 1) if years else None,
        'dates': dts[-TAIL:], 'values': vals[-TAIL:],
    }


def main():
    print('=' * 20, '三大风格 / 股债比价取数（%sK 分段全周期）' % PERIOD, '=' * 20)
    codes = []
    for p in RATIO_PAIRS:
        for c, f, _ in (p['num'], p['den']):
            if (c, f) not in codes:
                codes.append((c, f))
    series, empty_segs = {}, {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=4) as ex:
        for (c, f), (s, emp) in zip(codes, ex.map(lambda x: get_series(x[0], x[1]), codes)):
            series[c] = s
            if emp:
                empty_segs[c] = emp
    if empty_segs:
        for c, emp in empty_segs.items():
            # 空段不等于缺失：科创50 指数 2019-12 才发布、十年国债ETF 2017-08 才上市，
            # 它们 2010~2017 的段本来就该是空的。只有“该标的已经有数据、却在这一段空掉”
            # 才是真的漏抓，那种才会让比值停在旧日期。
            d0 = min(series[c]) if series.get(c) else None
            real = [('%s~%s' % x) for x in emp if not d0 or x[1] >= d0]
            benign = len(emp) - len(real)
            if benign:
                print('  %s 有 %d 个空段在其首个数据日（%s）之前，属上市/发布前正常无数据' %
                      (c, benign, d0 or '-'))
            if real:
                print('!! %s 有分段抓空：%s（该标的序列不完整，相关比值可能停在旧日期）' %
                      (c, '、'.join(real)))

    # 数据新鲜度：某个标的最后一根周K明显落后于同批其他标的 → 说明它某段没抓到，
    # 比值会拿去年甚至前年的值当“当前值”，分位和结论都会错。周K本身落后 7~10 个自然日
    # 是正常的（周末 + 长假），所以用 14 天作阈值，只抓“漏了整段”这种量级的落后。
    lasts = {c: max(s) for c, s in series.items() if s}
    today = datetime.date.today().isoformat()
    lag_abs, stale = 0, set()
    if lasts:
        newest = max(lasts.values())
        for c, d in sorted(lasts.items()):
            try:
                lag = (datetime.datetime.strptime(newest, '%Y-%m-%d') -
                       datetime.datetime.strptime(d, '%Y-%m-%d')).days
            except Exception:
                continue
            if lag > 14:
                stale.add(c)
                print('!! %s 最新数据停在 %s，比本批最新的 %s 落后 %d 天（疑似整段抓空，'
                      '相关分位不可信）' % (c, d, newest, lag))
        # 横向比对有个盲区：四个标的要是“一起”空掉最后一段，谁都不比别人落后，
        # 上面那条一句话都不会说 —— 06:49 那次就接近这种情况。所以再对绝对日期比一次。
        try:
            lag_abs = (datetime.datetime.strptime(today, '%Y-%m-%d') -
                       datetime.datetime.strptime(newest, '%Y-%m-%d')).days
        except Exception:
            lag_abs = 0
        if lag_abs > 14:
            print('!! 全部标的的最新数据都停在 %s，距今 %d 天。周K正常最多落后 10 天'
                  '（周末+长假），这么长基本可以确定最后一段整段抓空，'
                  '下面三行“当前值”其实是旧值，别采信。' % (newest, lag_abs))

    # 数据完整性：周K相邻间隔正常 7 天，超过 60 天视为缺段
    for c, s in series.items():
        ds = sorted(s)
        gaps = []
        for i in range(1, len(ds)):
            try:
                g = (datetime.datetime.strptime(ds[i], '%Y-%m-%d') -
                     datetime.datetime.strptime(ds[i - 1], '%Y-%m-%d')).days
            except Exception:
                continue
            if g > 60:
                gaps.append('%s→%s(%d天)' % (ds[i - 1], ds[i], g))
        if gaps:
            print('!! %s 序列存在缺口：%s' % (c, '，'.join(gaps[:5])))

    # 上一份结果：某个比值对这次不可信时，直接沿用它的旧值而不是整份丢掉
    prev = {}
    try:
        if os.path.exists(OUT):
            with open(OUT, encoding='utf-8') as fp:
                prev = json.load(fp).get('items') or {}
    except Exception:
        prev = {}

    out = {'asof': None, 'period': PERIOD, 'items': {}, 'order': [p['key'] for p in RATIO_PAIRS]}
    for p in RATIO_PAIRS:
        # 一个比值只由两个标的决定，所以“哪个标的陈旧”能精确到“哪一对不可信”。
        # 06:49 那次正是部分标的空掉（399006、510300 为 2026:0），全局检查看不出来。
        pcs = [p['num'][0], p['den'][0]]
        bad = [c for c in pcs if c in stale]
        if bad:
            print('!! %s 暂不更新：%s 数据陈旧，沿用上一份结果' % (p['title'], '、'.join(bad)))
            if p['key'] in prev:
                out['items'][p['key']] = prev[p['key']]
            continue
        it = build(p, series)
        if it:
            out['items'][p['key']] = it
            print('%s：当前 %.4f　近%s年分位 %.1f%%（%s）　%s　[数据截至 %s]' %
                  (p['title'], it['cur'], it['years'], it['pct'], it['word'], it['label'],
                   it['asof']))
    if not out['items']:
        print('!! 未生成任何比值数据')
        sys.exit(1)
    out['asof'] = max(v['asof'] for v in out['items'].values())

    # 数据明显陈旧就别覆盖 ratios.json。workflow 会缓存这个文件，不写就等于沿用上一份
    # 算对了的数据；写下去则等于把“去年 12 月 31 日”当成“今天”，看板上会静悄悄地错。
    # 宁可 ④ 面板停在昨天的正确数字，也不要它给出今天的错误结论。
    if lag_abs > 14:
        print('!! 拒绝写入 %s：最新数据停在 %s（距今 %d 天），沿用上一份结果' %
              (OUT, max(lasts.values()) if lasts else '-', lag_abs))
        sys.exit(1)

    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False)
    print('已写入 %s（%.1fs）' % (OUT, time.time() - t0))


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""
模块三 · 美联储宏观流动性压力指数 (LSI) & 20 项背景颜色报警矩阵

由 TradingView Pine Script v6《AA流动性压力指数（宏观分析）》移植。
数据源：美联储 FRED 官方 API（20 个序列）。

按要求：
  · FRED 官方接口有的数据全部保留；TradingView 私有数据（S5TH / GOLD / SILVER /
    欧中日央行资产负债表）已剔除，不参加本次计算。
  · 全球流动性总量采用美联储净流动性：GLI(T) = WALCL(T) − WTREGEN(T) − RRPONTSYD(T)
  · 所有阈值严格照搬 Pine Script 原代码。

输出：lsi.json
"""
import json, os, sys, time, datetime, bisect

import common
from config import FRED_API_KEY, FRED_SERIES, LSI_TH

OUT = os.path.join(common.BASE, 'lsi.json')
STATUS_OUT = os.path.join(common.BASE, 'lsi_status.json')
FRED_BASE = 'https://api.stlouisfed.org/fred/series/observations'

# 抓取窗口（自然日）：需覆盖 500 日 RRP 峰值 + 250 日分位 + CPI 12 个月同比
FETCH_DAYS = int(os.environ.get('LSI_FETCH_DAYS', '1560'))
CAL_DAYS = int(os.environ.get('LSI_CAL_DAYS', '820'))

# 参与构造交易日历的日频序列
_DAILY = ['SOFR', 'RRPONTSYAWARD', 'EFFR', 'IORB', 'DGS2', 'DGS10',
          'T10YIE', 'DFII10', 'BAMLH0A0HYM2', 'RRPONTSYD']

# 不参与日历构造的日频序列（只影响「日历有哪些天」，不影响取数，值照样进 LSI 计算）：
#   IORB（准备金余额利率）是政策利率，FRED 会对**未来日期**预填同一个值——
#   实测 2026-11-01（周日）就已经拿到 2026-11-02 的 3.90，且序列里含周末行。
#   把它并进交易日历，会把周末和「明天」凭空塞进日历，lsi.asof 就被顶到未来
#   （线上曾出现 A 股口径 asof=2026-10-30、宏观口径 asof=2026-11-02 打架）。
#   它仍然是 LSI 的核心项：compute() 里 iorb = ffill(cal, raw['IORB'])，不受影响。
_CAL_EXCLUDE = {'IORB'}


def fetch_series(sid, on_csv=None):
    """拉取单个 FRED 序列 -> {date: float}（已剔除缺失值 '.'）

    JSON API 重试到底仍失败时，common.http_json 会自动回退 fredgraph.csv，
    并把 on_csv 回调一次，用于统计兜底次数。
    """
    start = (datetime.date.today() - datetime.timedelta(days=FETCH_DAYS)).isoformat()
    url = '%s?series_id=%s&api_key=%s&file_type=json&observation_start=%s' % (
        FRED_BASE, sid, FRED_API_KEY, start)
    d = common.http_json(url, csv_id=sid, observation_start=start, on_csv=on_csv)
    out = {}
    for o in d.get('observations', []):
        v = o.get('value')
        if v in (None, '.', ''):
            continue
        try:
            out[o['date']] = float(v)
        except Exception:
            continue
    meta = FRED_SERIES.get(sid, {})
    print('  %-18s %-24s n=%-5d latest=%s' % (sid, meta.get('label', ''), len(out),
                                              max(out) if out else '-'), flush=True)
    return out


def gather():
    """并发抓取 20 个 FRED 序列（串行约 3 分钟，并发约 40 秒）

    返回 (raw, via)：via[sid] 记录该序列走的是 'api' / 'csv'（兜底）/ 'error'（彻底失败），
    供本轮数据完整性报告使用。
    """
    from concurrent.futures import ThreadPoolExecutor
    raw, via = {}, {}

    def _one(sid):
        box = {'via': 'api'}

        def _mark_csv():
            box['via'] = 'csv'

        try:
            d = fetch_series(sid, on_csv=_mark_csv)
        except Exception as e:
            print('  !! %s 抓取失败：%s' % (sid, e), flush=True)
            d, box['via'] = {}, 'error'
        via[sid] = box['via']
        return sid, d

    with ThreadPoolExecutor(max_workers=6) as ex:
        for sid, d in ex.map(_one, list(FRED_SERIES)):
            raw[sid] = d
    return raw, via


def build_calendar(raw):
    """交易日历 = 日频序列观测日期的并集，取最后 CAL_DAYS 个。

    两道过滤（都只影响日历，不影响取数）：
      ① 跳过 _CAL_EXCLUDE 里的序列（政策利率，含未来预填与周末行）；
      ② 兜底裁掉晚于今天(UTC)的日期——任何序列都不该贡献未来日期。
    """
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    ds = set()
    for sid in _DAILY:
        if sid in _CAL_EXCLUDE:
            continue
        ds |= {d for d in raw.get(sid, {}) if d <= today}
    if not ds:
        raise RuntimeError('FRED 日频序列全部为空，无法构造交易日历。'
                           '常见原因：① FRED_API_KEY 未配置或无效（注意 Actions 未配置 Secret 时会注入空字符串）；'
                           '② 运行环境无法访问 api.stlouisfed.org 与 fred.stlouisfed.org。')
    ds = sorted(ds)
    return ds[-CAL_DAYS:]


def ffill(cal, mapping):
    """按日历前向填充（复刻 Pine 的 gaps=barmerge.gaps_off）。

    ⚠️ 必须是「取不晚于该日的最近一次观测」（二分查找），不能写成 `if d in mapping`。
    FRED 的季度 GDP 日期永远标在每季首日（01-01 / 04-01 / 07-01 / 10-01），
    其中 01-01 是元旦休市日、季首日也常在周末；月度 CPI / 银行总资产同理。
    若用精确日期匹配，这些非交易日发布的数据会被永久跳过，
    导致第 5 项「准备金/GDP」报警用上一期的陈旧 GDP。
    """
    if not mapping:
        return [None] * len(cal)
    keys = sorted(mapping)
    out, last = [], None
    for d in cal:
        i = bisect.bisect_right(keys, d) - 1
        if i >= 0:
            last = mapping[keys[i]]
        out.append(last)
    return out


def to_bps(series):
    """百分比 -> 基点"""
    return [None if v is None else v * 100.0 for v in series]


def to_T_millions(series):
    """百万美元 -> 万亿美元"""
    return [None if v is None else v / 1e6 for v in series]


def to_B_millions(series):
    """百万美元 -> 十亿美元"""
    return [None if v is None else v / 1e3 for v in series]


def to_T_billions(series):
    """十亿美元 -> 万亿美元"""
    return [None if v is None else v / 1e3 for v in series]


def cpi_yoy_bps(cal, cpi_map):
    """CPI 月度指数 -> 12 个月同比（%）-> 基点"""
    cpi_dates = sorted(cpi_map)
    out = []
    for d in cal:
        i = bisect.bisect_right(cpi_dates, d) - 1
        if i < 0:
            out.append(None)
            continue
        cur_d = cpi_dates[i]
        cur_v = cpi_map[cur_d]
        try:
            cd = datetime.datetime.strptime(cur_d, '%Y-%m-%d').date()
            ago = (cd - datetime.timedelta(days=365)).isoformat()
        except Exception:
            out.append(None)
            continue
        j = bisect.bisect_right(cpi_dates, ago) - 1
        if j < 0:
            out.append(None)
            continue
        base = cpi_map[cpi_dates[j]]
        if not base:
            out.append(None)
            continue
        out.append((cur_v / base - 1.0) * 100.0 * 100.0)   # % -> bps
    return out


def safe(v, nd=2):
    return None if v is None else round(v, nd)


def _fmt(v, nd=2, suffix=''):
    if v is None:
        return '—'
    return ('%.*f%s' % (nd, v, suffix))


def compute(cal, raw):
    T = LSI_TH
    # ---------- 原始序列（前向填充） ----------
    sofr = to_bps(ffill(cal, raw.get('SOFR', {})))
    rrp_rate = to_bps(ffill(cal, raw.get('RRPONTSYAWARD', {})))
    effr = to_bps(ffill(cal, raw.get('EFFR', {})))
    iorb = to_bps(ffill(cal, raw.get('IORB', {})))
    us02y = to_bps(ffill(cal, raw.get('DGS2', {})))
    us10y = to_bps(ffill(cal, raw.get('DGS10', {})))
    t10yie = to_bps(ffill(cal, raw.get('T10YIE', {})))
    dfii10 = to_bps(ffill(cal, raw.get('DFII10', {})))
    credit = to_bps(ffill(cal, raw.get('BAMLH0A0HYM2', {})))
    cpi = cpi_yoy_bps(cal, raw.get('CPIAUCSL', {}))

    walcl_T = to_T_millions(ffill(cal, raw.get('WALCL', {})))        # 美联储总资产 T
    wtregen_T = to_T_millions(ffill(cal, raw.get('WTREGEN', {})))    # TGA T
    wdtgal_B = to_B_millions(ffill(cal, raw.get('WDTGAL', {})))      # TGA B
    rrp_B = ffill(cal, raw.get('RRPONTSYD', {}))                     # ON RRP 余额 B（FRED 原单位）
    rrp_T = to_T_billions(rrp_B)                                     # ON RRP 余额 T
    wlrr_B = to_B_millions(ffill(cal, raw.get('WLRRAL', {})))        # 外国官方逆回购 B
    wresbal_T = to_T_millions(ffill(cal, raw.get('WRESBAL', {})))
    wrb_T = to_T_millions(ffill(cal, raw.get('WRBWFRBL', {})))
    wrb_B = to_B_millions(ffill(cal, raw.get('WRBWFRBL', {})))
    assets_B = ffill(cal, raw.get('TLAACBM027SBOG', {}))
    gdp_B = ffill(cal, raw.get('GDP', {}))
    dxy = ffill(cal, raw.get('DTWEXBGS', {}))

    n = len(cal)
    # ---------- GLI 美联储净流动性 ----------
    gli = []
    for i in range(n):
        a, b, c = walcl_T[i], wtregen_T[i], rrp_T[i]
        gli.append(None if (a is None or b is None or c is None) else a - b - c)

    def _at(arr, i, k):
        j = i - k
        return arr[j] if j >= 0 else None

    # ---------- 流动性变化率与冲量 ----------
    mom = T['gli_mom_lookback']
    tlc = []     # total_liq_change %
    for i in range(n):
        cur, prev = gli[i], _at(gli, i, mom)
        if cur is None or prev is None or abs(prev) < 1e-9:
            tlc.append(None)
        else:
            tlc.append((cur - prev) / max(abs(prev), 0.01) * 100.0)
    impulse = []
    for i in range(n):
        a, b = tlc[i], _at(tlc, i, mom)
        impulse.append(None if (a is None or b is None) else a - b)

    # ---------- RRP 枯竭度 ----------
    win = T['rrp_peak_window']
    rrp_pct, rrp_peak = [], []
    for i in range(n):
        seg = [x for x in rrp_T[max(0, i - win + 1):i + 1] if x is not None]
        if not seg or rrp_T[i] is None:
            rrp_pct.append(None)
            rrp_peak.append(None)
        else:
            pk = max(seg)
            rrp_peak.append(pk)
            rrp_pct.append(rrp_T[i] / pk * 100.0 if pk > 0 else None)

    # ---------- 准备金红线 ----------
    r_gdp, r_assets = [], []
    for i in range(n):
        w, g, a = wrb_B[i], gdp_B[i], assets_B[i]
        r_gdp.append(None if (w is None or not g) else w / g)
        r_assets.append(None if (w is None or not a) else w / a)

    # ---------- 收益率曲线（3 日平滑 + 10 日变动） ----------
    s10 = common.sma(us10y, 3)
    s02 = common.sma(us02y, 3)
    sprd = [None if (a is None or b is None) else a - b for a, b in zip(us10y, us02y)]
    ssp = common.sma(sprd, 3)
    lb = T['curve_lookback']
    us10y_chg = [None if (s10[i] is None or _at(s10, i, lb) is None) else s10[i] - _at(s10, i, lb) for i in range(n)]
    us02y_chg = [None if (s02[i] is None or _at(s02, i, lb) is None) else s02[i] - _at(s02, i, lb) for i in range(n)]
    sprd_chg = [None if (ssp[i] is None or _at(ssp, i, lb) is None) else ssp[i] - _at(ssp, i, lb) for i in range(n)]

    # ---------- 信用利差动量 ----------
    crl = T['credit_roc_len']
    credit_roc = []
    for i in range(n):
        a, b = credit[i], _at(credit, i, crl)
        credit_roc.append(None if (a is None or not b) else (a / b - 1.0) * 100.0)

    # ---------- 美元指数 50 日均线 ----------
    dxy_ma = common.sma(dxy, T['dxy_ma_len'])

    # ---------- 美联储流动性代理（黄金到顶 macro 用） ----------
    nw = T['norm_window']
    def _norm(arr):
        lo, hi = None, None
        for v in arr:
            if v is None:
                continue
            lo = v if lo is None else min(lo, v)
            hi = v if hi is None else max(hi, v)
        rng = (hi - lo) if (hi is not None and lo is not None and hi > lo) else 1e-6
        return [None if v is None else (v - lo) / rng for v in arr]
    n_wdtgal, n_wrb = [], []
    for i in range(n):
        seg_d = [x for x in wdtgal_B[max(0, i - nw + 1):i + 1] if x is not None]
        seg_w = [x for x in wrb_B[max(0, i - nw + 1):i + 1] if x is not None]
        vd, vw = wdtgal_B[i], wrb_B[i]
        n_wdtgal.append(None if (vd is None or len(seg_d) < 2) else
                        (vd - min(seg_d)) / max(max(seg_d) - min(seg_d), 1e-6))
        n_wrb.append(None if (vw is None or len(seg_w) < 2) else
                     (vw - min(seg_w)) / max(max(seg_w) - min(seg_w), 1e-6))
    fed_proxy = [None if (a is None or b is None) else a * 0.5 + b * 0.5
                 for a, b in zip(n_wdtgal, n_wrb)]
    fed_proxy_ma = common.sma(fed_proxy, T['ma_period'])

    # ---------- V57 资金流向雷达 ----------
    fl = T['flow_lookback']
    def _delta(arr):
        out = []
        for i in range(n):
            a, b = arr[i], _at(arr, i, fl)
            out.append(None if (a is None or b is None) else a - b)
        return out
    d_tga, d_wlrr, d_rrp = _delta(wdtgal_B), _delta(wlrr_B), _delta(rrp_B)

    # ---------- 逐日布尔量（用于历史序列） ----------
    lsi = []
    for i in range(n):
        a, b, c, d = sofr[i], rrp_rate[i], effr[i], iorb[i]
        lsi.append(None if None in (a, b, c, d) else (a - b) + (c - d))

    gli_hi = [common.percentile_linear_interpolation(gli[:i + 1], T['gli_lookback'], T['gli_high_pct'])
              for i in range(n)]
    gli_lo = [common.percentile_linear_interpolation(gli[:i + 1], T['gli_lookback'], T['gli_low_pct'])
              for i in range(n)]

    def _b(i):
        """计算第 i 日的全部布尔量与派生量"""
        v = lambda arr: arr[i] if i < len(arr) else None
        L = v(lsi)
        cr = v(credit)
        dfx = v(dfii10)
        ty = v(t10yie)
        cp = v(cpi)
        rr_pct = v(rrp_pct)
        rr_T = v(rrp_T)
        G = v(gli)
        r = {
            'lsi': L, 'credit': cr, 'dfii10': dfx, 't10yie': ty, 'cpi_yoy': cp,
            'rrp_pct': rr_pct, 'rrp_T': rr_T, 'gli': G,
            'rrp_peak': v(rrp_peak), 'reserve_gdp': v(r_gdp), 'reserve_assets': v(r_assets),
            'us02y_chg': v(us02y_chg), 'us10y_chg': v(us10y_chg), 'sprd_chg': v(sprd_chg),
            'yield_spread': v(sprd), 'credit_roc': v(credit_roc),
            'tlc': v(tlc), 'impulse': v(impulse),
            'dxy': v(dxy), 'dxy_ma': v(dxy_ma),
            'walcl_T': v(walcl_T), 'wtregen_T': v(wtregen_T), 'rrp_B': v(rrp_B),
            'wresbal_T': v(wresbal_T), 'wrb_T': v(wrb_T),
            'gdp_B': v(gdp_B), 'assets_B': v(assets_B),
            'sofr': v(sofr), 'rrp_rate': v(rrp_rate), 'effr': v(effr), 'iorb': v(iorb),
            'us02y': v(us02y), 'us10y': v(us10y),
            'd_tga': v(d_tga), 'd_wlrr': v(d_wlrr), 'd_rrp': v(d_rrp),
            'fed_proxy': v(fed_proxy), 'fed_proxy_ma': v(fed_proxy_ma),
        }
        # 布尔
        r['is_extreme_tight'] = L is not None and L >= T['threshold_extreme_tight']
        r['is_tight'] = (not r['is_extreme_tight']) and L is not None and L >= T['threshold_tight']
        r['is_rrp_exhausted'] = ((rr_pct is not None and rr_pct < T['rrp_exhaust_pct']) or
                                 (rr_T is not None and rr_T < T['rrp_exhaust_abs']))
        r['is_liquidity_break'] = (L is not None and L > T['threshold_tight']) and r['is_rrp_exhausted']
        r['is_reserve_low_gdp'] = r['reserve_gdp'] is not None and r['reserve_gdp'] < T['reserve_gdp_threshold']
        r['is_reserve_low_assets'] = r['reserve_assets'] is not None and r['reserve_assets'] < T['reserve_assets_threshold']
        r['is_reserve_insufficient'] = r['is_reserve_low_gdp'] and r['is_reserve_low_assets']
        cv = T['curve_lookback']
        valid = (v(us10y) is not None and v(us02y) is not None and
                 i - cv >= 0 and _at(s10, i, cv) is not None and _at(s02, i, cv) is not None)
        r['is_bull_steepener'] = bool(valid and r['sprd_chg'] is not None and
                                      r['sprd_chg'] > T['spread_change_th'] and
                                      r['us02y_chg'] is not None and r['us02y_chg'] <= -T['us02y_drop_th'])
        r['is_bear_steepener'] = bool(valid and r['sprd_chg'] is not None and
                                      r['sprd_chg'] > T['spread_change_th'] and
                                      r['us10y_chg'] is not None and r['us10y_chg'] >= T['us10y_spike_th'])
        r['is_credit_spiking'] = r['credit_roc'] is not None and r['credit_roc'] > T['credit_roc_th']
        r['is_credit_wide'] = cr is not None and cr > T['credit_th']
        r['is_real_tight'] = dfx is not None and dfx > T['th_real_tight'] * 100
        r['is_real_ext_loose'] = dfx is not None and dfx < T['th_real_ext_loose'] * 100
        dev = None if (ty is None or cp is None) else abs(ty - cp)
        r['breakeven_dev'] = dev
        r['is_breakeven_dev_large'] = dev is not None and dev > T['th_breakeven_dev'] * 100
        r['is_breakeven_positive'] = (ty is not None and cp is not None and ty > cp)
        r['is_stagflation_risk'] = bool(dfx is not None and dfx > T['th_stagflation_real'] * 100 and
                                        cr is not None and cr > T['th_stagflation_credit'] * 100)
        r['crisis_signal'] = bool(L is not None and ty is not None and r['us02y'] is not None and
                                  abs(r['effr'] - ty) < T['crisis_rate_infl_delta'] and
                                  abs(r['us02y'] - ty) < T['crisis_rate_infl_delta'] and
                                  cr is not None and cr > T['credit_th'])
        r['is_gli_loose'] = bool(G is not None and gli_hi[i] is not None and G > gli_hi[i])
        r['is_gli_tight'] = bool(G is not None and gli_lo[i] is not None and G < gli_lo[i] and not r['is_gli_loose'])
        r['is_sudden_drain'] = r['tlc'] is not None and r['tlc'] < T['gli_mom_threshold']
        im = [impulse[j] if 0 <= j < n else None for j in (i, i - 1, i - 2, i - 3)]
        r['is_impulse_waning'] = bool(all(x is not None for x in im) and im[0] < im[1] < im[2] < im[3])
        r['is_dxy_strong'] = bool(v(dxy) is not None and v(dxy_ma) is not None and v(dxy) > v(dxy_ma))
        gtd = None if (r['effr'] is None or cp is None) else r['effr'] - cp
        r['gold_top_diff'] = gtd
        r['is_gold_top'] = gtd is not None and gtd < T['gold_th']
        r['fed_liq_top'] = bool(r['fed_proxy'] is not None and r['fed_proxy_ma'] is not None and
                                r['fed_proxy'] < r['fed_proxy_ma'])
        r['is_extreme_loose'] = bool(L is not None and L < T['threshold_extreme_loose'] and r['is_gli_loose'])
        r['is_normal_loose'] = bool(L is not None and L < 0 and not r['is_extreme_loose']
                                    and not r['is_tight'] and not r['is_extreme_tight'])
        r['is_gold_top_macro'] = bool(r['fed_liq_top'] and r['is_breakeven_dev_large'] and
                                      r['is_breakeven_positive'] and
                                      (r['is_gli_loose'] or r['is_extreme_loose']))
        r['state_blackhole'] = bool(r['is_liquidity_break'] and r['is_credit_wide'] and r['is_dxy_strong'])
        r['state_stagflation'] = bool(r['is_stagflation_risk'] and ty is not None and ty > T['th_t10yie'] * 100)
        r['state_supernova'] = bool(r['is_gli_loose'] and r['is_real_ext_loose'] and
                                    cr is not None and cr < 350)
        r['gli_high_th'] = gli_hi[i]
        r['gli_low_th'] = gli_lo[i]
        return r

    latest = _b(n - 1)
    return {
        'cal': cal, 'latest': latest,
        'hist': {
            'lsi': lsi, 'gli': gli, 'rrp_T': rrp_T, 'rrp_pct': rrp_pct,
            'tlc': tlc, 'impulse': impulse, 'credit': credit, 'dfii10': dfii10,
        },
        'raw_latest': {k: (raw.get(k, {}) and None) for k in []},
    }


# ==========================================================================
# 20 项报警明细表（8 列）
# ==========================================================================
def build_alerts(v):
    T = LSI_TH
    g = lambda x, nd=2, s='': _fmt(x, nd, s)
    rows = []

    def add(no, cat, name, raw_txt, formula, result, th, on, extra=None):
        rows.append({'no': no, 'cat': cat, 'name': name, 'raw': raw_txt, 'formula': formula,
                     'result': result, 'threshold': th, 'alert': bool(on), 'extra': extra or ''})

    add(1, '内部压力', 'LSI 极端紧张 (is_extreme_tight)',
        'SOFR=%s bps｜RRP=%s bps｜EFFR=%s bps｜IORB=%s bps'
        % (g(v['sofr']), g(v['rrp_rate']), g(v['effr']), g(v['iorb'])),
        'LSI = (SOFR − RRP) + (EFFR − IORB)，单位 bps',
        'LSI = %s bps' % g(v['lsi']), 'LSI ≥ 50.0 bps', v['is_extreme_tight'])

    add(2, '内部压力', 'LSI 偏紧 (is_tight)',
        'SOFR=%s｜RRP=%s｜EFFR=%s｜IORB=%s（bps）'
        % (g(v['sofr']), g(v['rrp_rate']), g(v['effr']), g(v['iorb'])),
        'LSI = (SOFR − RRP) + (EFFR − IORB)，且未达极端紧张',
        'LSI = %s bps' % g(v['lsi']), '20.0 bps ≤ LSI < 50.0 bps', v['is_tight'])

    add(3, '内部压力', '核心流动性断裂 (is_liquidity_break)',
        'LSI=%s bps｜RRP=%s T (占500日峰值 %s%%)'
        % (g(v['lsi']), g(v['rrp_T'], 3), g(v['rrp_pct'], 1)),
        'LSI > 20.0 bps　且　is_rrp_exhausted == True',
        '断裂=%s' % ('是' if v['is_liquidity_break'] else '否'),
        'LSI > 20.0 bps 且 RRP 枯竭', v['is_liquidity_break'])

    add(4, '缓冲垫', 'RRP 逆回购枯竭 (is_rrp_exhausted)',
        'RRP余额=%s T｜500日峰值=%s T' % (g(v['rrp_T'], 3), g(v['rrp_peak'], 3)),
        'rrp_pct = RRP / Highest(RRP,500) × 100%',
        'rrp_pct = %s%%' % g(v['rrp_pct'], 1), 'rrp_pct < 5.0%% 或 RRP < 0.100 T',
        v['is_rrp_exhausted'])

    add(5, '缓冲垫', '商业银行准备金不足 (is_reserve_insufficient)',
        '准备金=%s T｜GDP=%s T｜银行总资产=%s T'
        % (g(v['wrb_T'], 3), g(v['gdp_B'] / 1000.0 if v['gdp_B'] else None, 3),
           g(v['assets_B'] / 1000.0 if v['assets_B'] else None, 3)),
        '准备金/GDP 与 准备金/银行总资产 双双判定',
        '准备金/GDP=%s%%｜/总资产=%s%%'
        % (g((v['reserve_gdp'] or 0) * 100, 2), g((v['reserve_assets'] or 0) * 100, 2)),
        '两项同时 < 11.0%', v['is_reserve_insufficient'])

    add(6, '动量预警', '⚠️ 曲线牛陡：衰退前兆 (is_bull_steepener)',
        'DGS10=%s bps｜DGS2=%s bps（及其3日均线）' % (g(v['us10y']), g(v['us02y'])),
        'sp_chg = SMA(10Y−2Y,3) − SMA(10Y−2Y,3)[10]；us02y_chg = SMA(2Y,3) − SMA(2Y,3)[10]',
        'sp_chg=%s bps｜us02y_chg=%s bps' % (g(v['sprd_chg']), g(v['us02y_chg'])),
        'sp_chg > +10.0 bps 且 us02y_chg ≤ −20.0 bps', v['is_bull_steepener'])

    add(7, '动量预警', '⚠️ 曲线熊陡：长端杀估值 (is_bear_steepener)',
        'DGS10=%s bps｜DGS2=%s bps（及其3日均线）' % (g(v['us10y']), g(v['us02y'])),
        'us10y_chg = SMA(10Y,3) − SMA(10Y,3)[10]；sp_chg 同上',
        'sp_chg=%s bps｜us10y_chg=%s bps' % (g(v['sprd_chg']), g(v['us10y_chg'])),
        'sp_chg > +10.0 bps 且 us10y_chg ≥ +20.0 bps', v['is_bear_steepener'])

    add(8, '动量预警', '⚠️ 信用利差短期急升 (is_credit_spiking)',
        'BAMLH0A0HYM2 当前=%s bps｜10日前=%s bps'
        % (g(v['credit']), g(credit_ago(v))),
        'credit_roc = (credit / credit[10] − 1) × 100%',
        'credit_roc = %s%%' % g(v['credit_roc'], 2), 'credit_roc > +10.0%',
        v['is_credit_spiking'])

    add(9, '信用与利率', '高收益债信用利差过宽',
        'BAMLH0A0HYM2 = %s%%' % g((v['credit'] or 0) / 100.0, 2),
        'credit_spread = BAMLH0A0HYM2 × 100（bps）',
        'credit_spread = %s bps' % g(v['credit']), 'credit_spread > 400.0 bps (4.00%)',
        v['is_credit_wide'])

    add(10, '信用与利率', '实际利率显著紧缩 (is_real_tight)',
        'DFII10 = %s%%' % g((v['dfii10'] or 0) / 100.0, 2),
        'dfii10_bps = DFII10 × 100',
        'DFII10 = %s bps' % g(v['dfii10']), 'DFII10 > 2.20% (220 bps)',
        v['is_real_tight'])

    add(11, '信用与利率', '通胀预期 vs 现实偏差过大 (is_breakeven_dev_large)',
        'T10YIE=%s%%｜CPI YoY=%s%%' % (g((v['t10yie'] or 0) / 100.0, 2), g((v['cpi_yoy'] or 0) / 100.0, 2)),
        'breakeven_dev = |T10YIE − CPI_YoY|（bps）',
        'breakeven_dev = %s bps' % g(v['breakeven_dev']), '|T10YIE − CPI_YoY| > 0.90% (90 bps)',
        v['is_breakeven_dev_large'])

    add(12, '信用与利率', '滞胀 + 信用压力双杀 (is_stagflation_risk)',
        'DFII10=%s%%｜信用利差=%s%%' % (g((v['dfii10'] or 0) / 100.0, 2), g((v['credit'] or 0) / 100.0, 2)),
        '同时检验 10Y 实际利率与高收益债利差',
        'DFII10=%s bps｜利差=%s bps' % (g(v['dfii10']), g(v['credit'])),
        'DFII10 > 1.80% 且 信用利差 > 4.00%', v['is_stagflation_risk'])

    add(13, '信用与利率', '潜在危机判定（利率收敛 + 高利差）',
        'EFFR=%s bps｜US02Y=%s bps｜T10YIE=%s bps｜利差=%s bps'
        % (g(v['effr']), g(v['us02y']), g(v['t10yie']), g(v['credit'])),
        '|EFFR − T10YIE| 与 |US02Y − T10YIE| 均 < 50 bps 且 信用利差 > 400 bps',
        '|EFFR−T10YIE|=%s bps｜|US02Y−T10YIE|=%s bps'
        % (g(abs((v['effr'] or 0) - (v['t10yie'] or 0))), g(abs((v['us02y'] or 0) - (v['t10yie'] or 0)))),
        '两差值均 < 50 bps 且 利差 > 400 bps', v['crisis_signal'])

    add(14, '总量与动量', 'GLI 总量收缩 (QT低水位) (is_gli_tight)',
        'GLI=%s T｜250日25%%分位=%s T' % (g(v['gli'], 3), g(v['gli_low_th'], 3)),
        'gli_low_th = Percentile(GLI, 250, 25)',
        'GLI = %s T' % g(v['gli'], 3), 'GLI < 250日25%分位', v['is_gli_tight'])

    add(15, '总量与动量', '全球流动性周期环比骤减 (is_sudden_drain)',
        'GLI=%s T｜20日前 GLI 变化率=%s%%' % (g(v['gli'], 3), g(v['tlc'])),
        'total_liq_change = (GLI − GLI[20]) / |GLI[20]| × 100%',
        'total_liq_change = %s%%' % g(v['tlc']), 'total_liq_change < −1.00%',
        v['is_sudden_drain'])

    add(16, '总量与动量', '流动性冲量边际衰竭 (is_impulse_waning)',
        'liq_impulse = %s%%' % g(v['impulse']),
        'liq_impulse = total_liq_change − total_liq_change[20]；连续3日回落',
        'impulse = %s%%' % g(v['impulse']), 'imp[0] < imp[1] < imp[2] < imp[3]',
        v['is_impulse_waning'])

    add(17, '周期与汇率', '强美元潮汐发作 (is_dxy_strong)',
        'DTWEXBGS=%s｜MA50=%s' % (g(v['dxy']), g(v['dxy_ma'])),
        'dxy_ma50 = SMA(DTWEXBGS, 50)',
        'DTWEXBGS = %s' % g(v['dxy']), 'DTWEXBGS > MA50', v['is_dxy_strong'])

    add(18, '周期与汇率', '黄金到顶预警（负实际联邦利率）',
        'EFFR=%s%%｜CPI YoY=%s%%｜fed_liq_proxy=%s（MA10=%s）'
        % (g((v['effr'] or 0) / 100.0, 2), g((v['cpi_yoy'] or 0) / 100.0, 2),
           g(v['fed_proxy'], 3), g(v['fed_proxy_ma'], 3)),
        'gold_top_diff = (EFFR − CPI_YoY) × 100；fed_liq_proxy = 0.5×Norm500(WDTGAL) + 0.5×Norm500(WRBWFRBL)',
        'gold_top_diff = %s bps' % g(v['gold_top_diff']),
        'diff < −350 bps　或　(fed_liq_proxy < SMA10 且 |T10YIE−CPI|>0.9% 且 T10YIE>CPI 且 GLI宽松)',
        v['is_gold_top'] or v['is_gold_top_macro'])

    add(19, '顶级宏观状态', '⭐【宏观状态】流动性黑洞 (state_blackhole)',
        '断裂=%s｜利差=%s bps｜DTWEXBGS=%s > MA50=%s'
        % ('是' if v['is_liquidity_break'] else '否', g(v['credit']), g(v['dxy']), g(v['dxy_ma'])),
        '核心流动性断裂 + 信用利差 > 400 bps + 强美元',
        '黑洞=%s' % ('成立' if v['state_blackhole'] else '不成立'),
        '三项同时成立', v['state_blackhole'])

    add(20, '顶级宏观状态', '⭐【宏观状态】滞胀式危机 (state_stagflation)',
        'DFII10=%s%%｜利差=%s%%｜T10YIE=%s%%'
        % (g((v['dfii10'] or 0) / 100.0, 2), g((v['credit'] or 0) / 100.0, 2),
           g((v['t10yie'] or 0) / 100.0, 2)),
        '滞胀信用双杀 + 通胀预期失控',
        '滞胀危机=%s' % ('成立' if v['state_stagflation'] else '不成立'),
        'DFII10 > 1.80% 且 利差 > 4.00% 且 T10YIE > 2.50%', v['state_stagflation'])

    return rows


def build_loose(v):
    """正面宽松状态指示项（底部展示，保持绿色）"""
    g = lambda x, nd=2, s='': _fmt(x, nd, s)
    return [
        {'name': '内部正常宽松 (is_normal_loose)', 'result': 'LSI = %s bps' % g(v['lsi']),
         'threshold': 'LSI < 0 bps', 'on': bool(v['is_normal_loose'])},
        {'name': 'GLI 总量宽松 (is_gli_loose)', 'result': 'GLI = %s T（75%%分位 %s T）'
         % (g(v['gli'], 3), g(v['gli_high_th'], 3)),
         'threshold': 'GLI > 250日75%分位', 'on': bool(v['is_gli_loose'])},
        {'name': '内外极端双松 (is_extreme_loose)', 'result': 'LSI = %s bps 且 GLI 高位'
         % g(v['lsi']), 'threshold': 'LSI < −30 bps 且 GLI > 75%分位',
         'on': bool(v['is_extreme_loose'])},
        {'name': '实际利率极度宽松 (is_real_ext_loose)', 'result': 'DFII10 = %s%%'
         % g((v['dfii10'] or 0) / 100.0, 2), 'threshold': 'DFII10 < 0.0%',
         'on': bool(v['is_real_ext_loose'])},
        {'name': '⭐【宏观状态】流动性泛滥 (state_supernova)',
         'result': 'GLI宽松=%s｜DFII10=%s%%｜利差=%s bps'
                   % ('是' if v['is_gli_loose'] else '否', g((v['dfii10'] or 0) / 100.0, 2), g(v['credit'])),
         'threshold': 'GLI宽松 且 DFII10 < 0% 且 利差 < 350 bps', 'on': bool(v['state_supernova'])},
    ]


_credit_ago_cache = {}


def credit_ago(v):
    return _credit_ago_cache.get('v')


def build_flow(v):
    """V57 10 日资金流向雷达"""
    T = LSI_TH
    th = T['flow_threshold']
    items = [('TGA', v['d_tga']), ('外国逆回购', v['d_wlrr']), ('国内逆回购', v['d_rrp'])]
    drain = max([x for _, x in items if x is not None], default=None)
    inject = min([x for _, x in items if x is not None], default=None)
    dname = next((k for k, x in items if x is not None and x == drain), '—')
    iname = next((k for k, x in items if x is not None and x == inject), '—')
    net = sum([x for _, x in items if x is not None])
    return {
        'items': [{'name': k, 'delta_b': safe(x, 2)} for k, x in items],
        'drain_name': dname, 'drain_b': safe(drain, 2),
        'inject_name': iname, 'inject_b': safe(inject, 2),
        'net_b': safe(net, 2), 'threshold': th,
        'drain_str': ('%s抽水(-%sB)' % (dname, _fmt(abs(drain), 2))) if (drain is not None and drain > th) else '无明显抽水',
        'inject_str': ('%s放水(+%sB)' % (iname, _fmt(abs(inject), 2))) if (inject is not None and inject < -th) else '无明显放水',
        'net_desc': ('三渠道合计净抽水(-$%sB)，基础货币池边际承压。' % _fmt(net, 2)) if net > th else
                    (('三渠道合计净放水(+$%sB)，短期资金面获得实打实的流动性注入。' % _fmt(abs(net), 2)) if net < -th else
                     '三渠道净流量基本平衡(净变动$%sB)。' % _fmt(net, 2)),
    }


def build_diagnosis(v, flow):
    """四维全景合成诊断（已剔除 S5TH 广度与金银比相关分支）"""
    g = lambda x, nd=2, s='': _fmt(x, nd, s)
    rr = lambda x: (None if x is None else x / 100.0)
    real_rate, credit_v = rr(v['dfii10']), rr(v['credit'])
    t10yie_v, inf_v = rr(v['t10yie']), rr(v['cpi_yoy'])

    # 0. 资金动态
    l0 = ('🔍【资金动态】' +
          (('监测到%s正在密集抽水(-$%sB)，属于%s' % (flow['drain_name'], _fmt(abs(flow['drain_b']), 2),
                                            '货币基金资金回流逆回购池的内部腾挪；' if flow['drain_name'] == '国内逆回购'
                                            else '财政发债/收税或外资清算导致的外部失血；'))
           if (flow['drain_b'] is not None and flow['drain_b'] > flow['threshold'])
           else '近期系统性抽水动能微弱；') +
          (('同时%s正在通过放水(+$%sB)对冲市场压力；' % (flow['inject_name'], _fmt(abs(flow['inject_b']), 2)))
           if (flow['inject_b'] is not None and flow['inject_b'] < -flow['threshold'])
           else '且缺乏显著的单点放水对冲；') + flow['net_desc'])

    # 1. 一阶宏观周期与债务周期
    if v['state_blackhole']:
        base = '当前处于短期债务周期的严重去杠杆阶段，流动性黑洞吞噬一切风险溢价，系统违背安全边际法则，建议转向现金与极短期美债防御。'
    elif v['state_stagflation']:
        base = '进入滞胀式去杠杆期，通胀顽固高企与实体信用恶化共振，股债双杀风险极大，逢低关注具备抗通胀属性的硬资产（如黄金）与高股息类债核心资产。'
    elif v['is_stagflation_risk']:
        base = ('⚠️准滞胀双杀预警：当前10Y实际利率(%s%%)与高收益信用利差(%s%%)已双双突破滞胀红线，'
                '虽长端通胀预期(%s%%)暂未极端失控，但实体融资成本与违约压力已高度共振，宜提前收缩高Beta敞口。'
                % (g(real_rate), g(credit_v), g(t10yie_v)))
    elif v['state_supernova']:
        base = '处于宏观流动性矩阵（MLM）的绝对扩张象限，充裕资金驱动资产价格重估，顺周期、大盘价值以及具备宽阔护城河的优质标的将显著跑赢。'
    else:
        base = '宏观大周期暂未触发极端黑洞或滞胀危机，但需结合以下次级宏观约束审视估值上沿：'
    add = ''
    if v['is_real_tight']:
        add += ' [实际利率紧缩] 10Y实际收益率高达%s%%(>2.2%%)，无风险真实回报率高企，对科技成长股与无息资产形成持续的估值引力压制；' % g(real_rate)
    elif v['is_real_ext_loose']:
        add += ' [实际利率极宽] 10Y实际收益率跌入负值/极低区间(%s%%)，真实资金成本极低，极大利好黄金与长久期成长资产；' % g(real_rate)
    if v['is_breakeven_dev_large']:
        add += (' [通胀预期撕裂] 10Y盈亏平衡通胀(%s%%)与现实CPI(%s%%)偏差达%s%%，%s'
                % (g(t10yie_v), g(inf_v), g(v['breakeven_dev'] / 100.0 if v['breakeven_dev'] else None),
                   '市场隐含通胀预期显著高于现实，警惕二次通胀定价；' if v['is_breakeven_positive']
                   else '现实通胀显著高于长期预期，短期物价黏性尚未出清；'))
    if v['is_dxy_strong']:
        add += ' [强美元潮汐] 广义美元指数(%s)运行于50日均线上方，全球美元回流对非美市场及大宗商品构成汇率抽水压制；' % g(v['dxy'])
    if v['is_gold_top'] or v['is_gold_top_macro']:
        add += (' [贵金属周期提示] 触发%s，追高贵金属需注意盈亏比；'
                % ('美联储救市QE放缓与高通胀预期背离的黄金冲顶回落信号，' if v['is_gold_top_macro']
                   else '有效利率远低于通胀的极端负利率黄金见顶阈值，'))
    if not add and not (v['state_blackhole'] or v['state_stagflation'] or v['is_stagflation_risk']
                        or v['state_supernova']):
        add = ' 实际利率、汇率与通胀预期均处于温和区间，投资主线回归企业盈利与CAPE内在价值中枢。'
    l1 = '【一阶宏观周期与债务周期】' + base + add

    # 2. 二阶流动性矩阵与底层水位
    if v['is_liquidity_break']:
        b2 = ('🚨底层管道破裂：美元体系核心流动性断裂(LSI达%sBP)，隔夜逆回购(RRP仅剩%sT)彻底耗尽，'
              '准备金失去缓冲垫，休克危机一触即发！' % (g(v['lsi'], 1), g(v['rrp_T'], 3)))
    elif v['is_gli_tight']:
        b2 = ('⚠️总量收缩：美联储处于实质性去杠杆周期(GLI=%sT处于近250日低位分位)，宏观水位退潮将压制权益市场估值扩张倍数。'
              % g(v['gli'], 2))
    elif v['is_gli_loose']:
        b2 = ('🟢总量扩张：美联储净流动性(GLI=%sT)处于历史百分位高点，为底层水位提供充足托底，流动性溢出效应明显。'
              % g(v['gli'], 2))
    else:
        b2 = '🟡水位中立：宏观流动性(GLI=%sT)处于中性平衡带，资本市场由结构性摩擦和存量资金博弈主导。' % g(v['gli'], 2)
    p2 = (' [内部管道与缓冲垫] LSI内部压力为%sBP(%s)；'
          % (g(v['lsi'], 1),
             '极端紧张，回购市场显著缺钱' if v['is_extreme_tight'] else
             '偏紧，短端资金摩擦升温' if v['is_tight'] else
             '极端宽松，内外双松共振' if v['is_extreme_loose'] else
             '正常宽松，货币市场拆借顺畅' if v['is_normal_loose'] else '中性平衡'))
    if v['is_rrp_exhausted'] and not v['is_liquidity_break']:
        p2 += ('⚠️注意：虽LSI暂未突破断裂阈值，但RRP逆回购余额已枯竭至%sT(峰值占比%s%%)，财政抽水将直接消耗商业银行准备金(%sT)；'
               % (g(v['rrp_T'], 3), g(v['rrp_pct'], 1), g(v['wrb_T'], 2)))
    if v['is_reserve_insufficient']:
        p2 += ('🚨准备金红线警报：准备金/GDP(%s%%)与准备金/银行总资产(%s%%)双双跌破11%%安全线，银行体系极易发生2019年9月式回购利率脉冲！'
               % (g((v['reserve_gdp'] or 0) * 100, 1), g((v['reserve_assets'] or 0) * 100, 1)))
    elif v['is_reserve_low_gdp'] or v['is_reserve_low_assets']:
        p2 += ('⚠️准备金偏薄：准备金/GDP(%s%%)或占银行资产比(%s%%)已有一项跌破11%%警戒线，需密切跟踪美联储缩表(QT)节奏；'
               % (g((v['reserve_gdp'] or 0) * 100, 1), g((v['reserve_assets'] or 0) * 100, 1)))
    if v['is_sudden_drain']:
        p2 += '🚨异常闪崩警报：监测到总资金池周期环比骤降(%s%%)，警惕流动性真空引发的极速闪崩！' % g(v['tlc'])
    elif v['is_impulse_waning']:
        p2 += '⚠边际动能衰竭：流动性冲量(%s%%)连续3日回落，二阶扩张加速度放缓，高弹性资产易出现高位震荡。' % g(v['impulse'])
    elif v['impulse'] is not None and v['impulse'] > 0:
        p2 += '🟢冲量正向加速：流动性冲量(+%s%%)处于正值扩张区间，边际资金推力良好。' % g(v['impulse'])
    l2 = '【二阶流动性矩阵与底层水位】' + b2 + p2

    # 3. 三阶微观定价与风险溢价（曲线 + 信用；S5TH 广度已剔除）
    if v['is_bull_steepener']:
        c3 = ('🚨【牛陡/衰退预警】短端2Y美债周期内暴跌(%sBP)，10Y-2Y利差迅速走阔(+%sBP)，'
              '市场正恐慌性抢跑美联储紧急降息与经济硬着陆，立即转向现金与短债防御！'
              % (g(v['us02y_chg'], 1), g(v['sprd_chg'], 1)))
    elif v['is_bear_steepener']:
        c3 = ('🚨【熊陡/杀估值警报】长端10Y美债失控飙升(+%sBP)，期限溢价爆表，'
              '高估值科技股与长久期资产面临折现率上行带来的惨烈杀估值！' % g(v['us10y_chg'], 1))
    elif v['yield_spread'] is not None and v['yield_spread'] < -50:
        c3 = '⚠️【深度倒挂】10Y-2Y利差深度倒挂(%sBP)，隐含中长期衰退引力，切忌在周期顶部过度加杠杆；' % g(v['yield_spread'], 1)
    elif v['yield_spread'] is not None and v['yield_spread'] < 0:
        c3 = '🟡【浅度倒挂】10Y-2Y利差处于%sBP浅度倒挂区间，观察向正斜率修复的路径(牛陡或熊陡)；' % g(v['yield_spread'], 1)
    else:
        c3 = '🟢【正斜率】10Y-2Y利差为+%sBP平稳正斜率，期限结构常态化；' % g(v['yield_spread'], 1)
    if v['crisis_signal']:
        c3 += (' 🔥【危机传导打通】短端利率与通胀预期高度收敛叠加高收益债信用利差破位(%s%% > 4.00%%)，'
               '违约风险正在冲击权益定价，切勿逆势接飞刀！' % g(credit_v))
    elif v['is_credit_wide'] and v['is_credit_spiking']:
        c3 += (' ⚠️【信用双警】垃圾债利差不仅绝对水位过宽(%s%%)，且短期ROC动量急升(+%s%%)，企业再融资环境急速恶化！'
               % (g(credit_v), g(v['credit_roc'], 1)))
    elif v['is_credit_wide']:
        c3 += ' ⚠️【信用利差过宽】高收益债利差达%s%%(高于4.0%%警戒线)，脆弱资产违约溢价偏高；' % g(credit_v)
    elif v['is_credit_spiking']:
        c3 += (' ⚠️【信用动量飙升】虽绝对利差(%s%%)尚在阈值内，但近10日ROC急升+%s%%，聪明钱在债券市场开始定价风险！'
               % (g(credit_v), g(v['credit_roc'], 1)))
    else:
        c3 += ' [信用温和] 高收益债利差(%s%%)处于安全水位，未见系统性违约挤兑；' % g(credit_v)
    l3 = '【三阶微观定价与风险溢价】' + c3 + '（S5TH 广度与金银比为 TradingView 私有数据，已按需求剔除）'

    return {'flow': l0, 'level1': l1, 'level2': l2, 'level3': l3}


def macro_state(v):
    if v['state_blackhole']:
        return '⭐ 流动性黑洞', 'danger'
    if v['state_stagflation']:
        return '⭐ 滞胀式危机', 'danger'
    if v['is_bull_steepener']:
        return '🚨 衰退前兆(极速牛陡)', 'danger'
    if v['is_bear_steepener']:
        return '🚨 长端崩盘(极速熊陡)', 'warn'
    if v['state_supernova']:
        return '⭐ 流动性泛滥', 'good'
    if v['is_extreme_tight']:
        return '⚠️ LSI 极端紧张', 'danger'
    if v['is_tight']:
        return '⚠️ LSI 偏紧', 'warn'
    if v['is_extreme_loose']:
        return '💚 内外极端双松', 'good'
    if v['is_normal_loose']:
        return '✅ 内部正常宽松', 'ok'
    return '✅ 风平浪静', 'ok'


def _gh_annot(level, msg):
    """在 GitHub Actions 里打注解（会显示在 run 页面的 Annotations 区块）。
    本地控制台不加 ::warning:: 这种噪音。"""
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        print('::%s::%s' % (level, msg), flush=True)


def _report_completeness(via):
    """本轮数据完整性报告：写 lsi_status.json + 打 Actions 注解，返回空序列个数。

    为什么要有这一步：以前序列抓空只体现在 print 的 n=0 上，退出码仍是 0，
    Action 一路绿 ✅，但看板里 GLI / RRP / DXY 已经整条变 null，没人发现。
    """
    _ALL = FRED_SERIES
    csv_ids = [s for s in _ALL if via.get(s) == 'csv']
    err_ids = [s for s in _ALL if via.get(s) == 'error']
    st = {
        'total': len(_ALL),
        'api_ok': sum(1 for s in _ALL if via.get(s) == 'api'),
        'csv_fallback': csv_ids,
        'empty': err_ids,
        'checked_at': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
    }
    st['ok'] = st['api_ok'] + len(csv_ids)
    try:
        with open(STATUS_OUT, 'w', encoding='utf-8') as fp:
            json.dump(st, fp, ensure_ascii=False, indent=1)
    except Exception as e:
        print('  !! 写 %s 失败：%s' % (STATUS_OUT, e))

    print('-' * 62)
    print('数据完整性：%d/%d 个序列拿到数据（API %d / CSV 兜底 %d / 空 %d）'
          % (st['ok'], st['total'], st['api_ok'], len(csv_ids), len(err_ids)))
    if csv_ids:
        print('  CSV 兜底救回：%s' % '、'.join(csv_ids))
        _gh_annot('warning', 'FRED JSON 接口本轮失败、已用 fredgraph.csv 兜底（%d 个）：%s'
                  % (len(csv_ids), '、'.join(csv_ids)))
    if err_ids:
        print('  !! 两个通道都失败：%s' % '、'.join(err_ids))
        _gh_annot('error', '本轮有 %d 个 FRED 序列两个通道都没拿到数据，相关指标会是 null：%s'
                  % (len(err_ids), '、'.join(err_ids)))
    return len(err_ids)


def main():
    print('=' * 20, '模块三：FRED 宏观流动性压力指数 (LSI)', '=' * 20)
    raw, via = gather()
    n_empty = _report_completeness(via)
    cal = build_calendar(raw)
    print('交易日历：%d 个观测日（%s ~ %s）' % (len(cal), cal[0], cal[-1]))
    res = compute(cal, raw)
    v = res['latest']

    # 供第 8 项显示「10 日前信用利差」
    crl = LSI_TH['credit_roc_len']
    _credit_ago_cache['v'] = (v['credit'] / (1 + v['credit_roc'] / 100.0)
                              if (v['credit'] and v['credit_roc'] is not None) else None)

    alerts = build_alerts(v)
    loose = build_loose(v)
    flow = build_flow(v)
    diag = build_diagnosis(v, flow)
    st, lv = macro_state(v)

    n_alert = sum(1 for a in alerts if a['alert'])
    out = {
        'asof': cal[-1],
        'state': st, 'level': lv, 'alert_count': n_alert, 'total': len(alerts),
        'core': {
            'lsi': safe(v['lsi']), 'sofr': safe(v['sofr']), 'rrp_rate': safe(v['rrp_rate']),
            'effr': safe(v['effr']), 'iorb': safe(v['iorb']),
            'us02y': safe(v['us02y']), 'us10y': safe(v['us10y']),
            'yield_spread': safe(v['yield_spread']),
            't10yie': safe(v['t10yie']), 'dfii10': safe(v['dfii10']),
            'credit': safe(v['credit']), 'credit_roc': safe(v['credit_roc']),
            'cpi_yoy': safe(v['cpi_yoy']),
            'gli': safe(v['gli'], 3), 'walcl_T': safe(v['walcl_T'], 3),
            'wtregen_T': safe(v['wtregen_T'], 3), 'rrp_T': safe(v['rrp_T'], 4),
            'rrp_pct': safe(v['rrp_pct'], 1), 'wresbal_T': safe(v['wresbal_T'], 3),
            'wrb_T': safe(v['wrb_T'], 3),
            'reserve_gdp': safe((v['reserve_gdp'] or 0) * 100, 2),
            'reserve_assets': safe((v['reserve_assets'] or 0) * 100, 2),
            'tlc': safe(v['tlc']), 'impulse': safe(v['impulse']),
            'dxy': safe(v['dxy']), 'dxy_ma': safe(v['dxy_ma']),
            'gli_high_th': safe(v['gli_high_th'], 3), 'gli_low_th': safe(v['gli_low_th'], 3),
        },
        'alerts': alerts, 'loose': loose, 'flow': flow, 'diag': diag,
        'hist': {k: [safe(x, 4) for x in arr] for k, arr in res['hist'].items()},
        'cal': cal,
        'thresholds': LSI_TH,
        'excluded': [
            'INDEX:S5TH（标普500广度）—— TradingView 私有，FRED 无免费日频接口，已剔除',
            'TVC:GOLD / TVC:SILVER（金银比）—— TradingView 私有，已剔除（含 state_gold_regime）',
            'ECONOMICS:EUCBBS/CNCBBS/JPCBBS（欧/中/日央行）—— 已剔除，GLI 改用美联储净流动性口径',
        ],
    }
    with open(OUT, 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False)
    print('宏观状态：%s（%d/%d 项报警触发）' % (st, n_alert, len(alerts)))
    print('LSI = %s bps｜GLI = %s T｜RRP = %s T (%s%%)｜信用利差 = %s bps'
          % (safe(v['lsi']), safe(v['gli'], 3), safe(v['rrp_T'], 4), safe(v['rrp_pct'], 1), safe(v['credit'])))
    print('已写入 %s' % OUT)

    # lsi.json 已经落盘（看板先用这份数据渲染），最后才用退出码表态：
    # 有序列彻底抓空 -> 非 0，让上游明确知道这一轮宏观数据不完整，而不是静默绿灯。
    # daily_run.py 里本模块是「失败仅降级不阻断」，所以不会影响 ETF 主报告与邮件；
    # workflow 末尾的完整性检查步骤会据此把整轮标红。
    if n_empty:
        print('!! 有 %d 个序列为空，本轮宏观数据不完整（lsi.json 已按现有数据写出）' % n_empty)
        sys.exit(1)


if __name__ == '__main__':
    main()

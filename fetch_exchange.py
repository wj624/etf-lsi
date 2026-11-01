# -*- coding: utf-8 -*-
"""
交易所官方 ETF 份额 / 净值取数（用于替代 westock 的滞后份额）

背景：
  westock(腾讯自选股) 的 ETF 份额/净值由基金公司 T+1~T+2 披露，行情商对「尚未披露日」
  返回最近一次已披露值，导致看板尾部 1~2 个交易日的 shares / nav / size 被冻结。
  交易所官方披露是 T+0（当日收盘后即公布当日份额），可以彻底消除这个滞后。

数据源：
  沪市份额 : akshare fund_etf_scale_sse(date=YYYYMMDD)        逐日
  深市份额 : akshare fund_scale_daily_szse(start,end,'ETF')   区间批量
  单位净值 : akshare fund_open_fund_info_em(indicator=单位净值走势)  全历史，约 0.15s/只

输出：_exchange_shares.json
  {
    "shares": {"YYYY-MM-DD": {"510300": 38866990000.0, ...}},
    "nav":    {"510300": {"YYYY-MM-DD": 4.0609, ...}},
    "meta":   {"updated": "...", "window_days": 250, "tail": 10, "sse_fail": 0}
  }

失败不影响主流程：取不到就返回 None，上层回退 westock 原值。
"""
import json, os, sys, time, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

CACHE = os.path.join(BASE, '_exchange_shares.json')

# 首次回填窗口（交易日数）与每次强制刷新的尾部天数
WINDOW_DAYS = int(os.environ.get('ETF_EXCHANGE_DAYS', '250'))
TAIL = int(os.environ.get('ETF_EXCHANGE_TAIL', '10'))
SSE_WORKERS = int(os.environ.get('ETF_SSE_WORKERS', '4'))
MAX_SSE_CALLS = int(os.environ.get('ETF_MAX_SSE_CALLS', '320'))
# 深交所接口单次返回上限约 65535 行（16-bit），全市场 ETF 约 770 行/交易日，
# 超过上限时接口不报错而是直接返回空表 —— 必须分段请求，每段留足余量
SZSE_CHUNK = int(os.environ.get('ETF_SZSE_CHUNK', '20'))

SH_CODES, SZ_CODES = [], []


def load_etfs():
    """从 config.TRACKS 解析出 {带前缀代码: (纯数字代码, 市场)}"""
    global SH_CODES, SZ_CODES
    from config import TRACKS
    mapping = {}
    for tk in TRACKS:
        for key in TRACKS[tk]['etfs']:
            mapping[key] = (key[2:], key[:2])
    SH_CODES = [c for c, m in mapping.values() if m == 'sh']
    SZ_CODES = [c for c, m in mapping.values() if m == 'sz']
    return mapping


def _retry(fn, tries=3, gap=2):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = '%s: %s' % (type(e).__name__, str(e)[:90])
            time.sleep(gap * (i + 1))
    raise RuntimeError(last)


def get_trade_days(days=520):
    """A 股交易日历 -> ['YYYY-MM-DD', ...] 升序"""
    import akshare as ak
    df = _retry(lambda: ak.tool_trade_date_hist_sina())
    out = []
    for x in df['trade_date']:
        s = str(x)[:10].replace('/', '-')
        if len(s) == 10 and s[4] == '-':
            out.append(s)
    out = sorted(set(out))
    return out[-days:]


def fetch_sse(date_compact):
    """上交所单日全部 ETF 份额 -> {code: shares}"""
    import akshare as ak
    df = _retry(lambda: ak.fund_etf_scale_sse(date=date_compact), tries=2, gap=2)
    if df is None or len(df) == 0:
        return {}
    code_col = '基金代码' if '基金代码' in df.columns else df.columns[0]
    share_col = '基金份额' if '基金份额' in df.columns else df.columns[-1]
    out = {}
    for _, row in df.iterrows():
        c = str(row[code_col]).strip()
        if c in SH_CODES:
            try:
                out[c] = float(row[share_col])
            except Exception:
                pass
    return out


def fetch_szse(start_compact, end_compact):
    """深交所区间批量 ETF 份额 -> {date: {code: shares}}"""
    import akshare as ak
    df = _retry(lambda: ak.fund_scale_daily_szse(start_date=start_compact,
                                                 end_date=end_compact, symbol='ETF'),
                tries=3, gap=3)
    if df is None or len(df) == 0:
        return {}
    out = {}
    for _, row in df.iterrows():
        c = str(row['基金代码']).strip()
        if c not in SZ_CODES:
            continue
        d = str(row['日期'])[:10]
        try:
            out.setdefault(d, {})[c] = float(row['基金份额'])
        except Exception:
            pass
    return out


def fetch_nav(codes):
    """天天基金单位净值全历史 -> {code: {date: nav}}"""
    import akshare as ak
    out = {}
    for c in codes:
        try:
            info = _retry(lambda c=c: ak.fund_open_fund_info_em(symbol=c, indicator='单位净值走势'),
                          tries=3, gap=2)
            m = {}
            for _, row in info.iterrows():
                d = str(row.get('净值日期'))[:10]
                try:
                    m[d] = float(row.get('单位净值'))
                except Exception:
                    pass
            if m:
                out[c] = m
                print('  nav %s ok (%d 天)' % (c, len(m)), flush=True)
        except Exception as e:
            print('  nav %s FAIL %s' % (c, str(e)[:80]), flush=True)
    return out


def load_cache():
    if not os.path.exists(CACHE):
        return {'shares': {}, 'nav': {}, 'meta': {}}
    try:
        with open(CACHE, encoding='utf-8') as f:
            d = json.load(f)
        d.setdefault('shares', {})
        d.setdefault('nav', {})
        d.setdefault('meta', {})
        return d
    except Exception as e:
        print('缓存损坏，重建:', e)
        return {'shares': {}, 'nav': {}, 'meta': {}}


def pick_todo(trade_days, have):
    """需要抓取的日期：窗口内缺失的 + 最后 TAIL 个交易日（强制刷新，接住晚披露）"""
    window = trade_days[-WINDOW_DAYS:]
    todo = set(d for d in window if not have.get(d))
    todo |= set(window[-TAIL:])
    return sorted(todo)


def main():
    from concurrent.futures import ThreadPoolExecutor, as_completed
    mapping = load_etfs()
    codes = sorted(set(c for c, _ in mapping.values()))
    print('标的数量: %d（沪 %d / 深 %d）' % (len(codes), len(SH_CODES), len(SZ_CODES)))

    cache = load_cache()
    # 交易日历含未来日期（新浪会推到年底），必须截断到今天，否则会去抓尚未发生的交易日
    today = datetime.date.today().isoformat()
    trade_days = [d for d in get_trade_days() if d <= today]
    print('交易日历: %s ~ %s（已截断至今日 %s）' % (trade_days[0], trade_days[-1], today))
    todo = pick_todo(trade_days, cache['shares'])
    print('待抓日期: %d 天（窗口 %d，尾部强制 %d）' % (len(todo), WINDOW_DAYS, TAIL))
    if todo:
        print('  %s ~ %s' % (todo[0], todo[-1]))

    sse_fail = 0
    if todo:
        # ---- 深交所：区间批量，但必须分段（单次上限 65535 行）----
        if SZ_CODES:
            got = {}
            for i in range(0, len(todo), SZSE_CHUNK):
                part = todo[i:i + SZSE_CHUNK]
                s, e = part[0].replace('-', ''), part[-1].replace('-', '')
                try:
                    got.update(fetch_szse(s, e))
                except Exception as ex:
                    print('深交所 %s~%s FAIL: %s' % (part[0], part[-1], str(ex)[:80]), flush=True)
                time.sleep(0.3)
            for d, m in got.items():
                cache['shares'].setdefault(d, {}).update(m)
            print('深交所: %d 天（分 %d 段）'
                  % (len(got), (len(todo) + SZSE_CHUNK - 1) // SZSE_CHUNK), flush=True)

        # ---- 上交所：逐日 ----
        if SH_CODES:
            todo_c = [d.replace('-', '') for d in todo][-MAX_SSE_CALLS:]
            t0 = time.time()
            got = 0
            with ThreadPoolExecutor(max_workers=SSE_WORKERS) as ex:
                futs = {ex.submit(fetch_sse, d): d for d in todo_c}
                for f in as_completed(futs):
                    dc = futs[f]
                    d = '%s-%s-%s' % (dc[:4], dc[4:6], dc[6:])
                    try:
                        m = f.result()
                        if m:
                            cache['shares'].setdefault(d, {}).update(m)
                            got += 1
                    except Exception:
                        sse_fail += 1
            print('上交所: %d/%d 天成功，失败 %d，耗时 %.0fs'
                  % (got, len(todo_c), sse_fail, time.time() - t0), flush=True)

    # ---- 净值：全历史，便宜，每次都刷 ----
    nav = fetch_nav(codes)
    for c, m in nav.items():
        cache['nav'].setdefault(c, {}).update(m)

    cache['meta'] = {
        'updated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'window_days': WINDOW_DAYS,
        'tail': TAIL,
        'sse_fail': sse_fail,
        'days': len(cache['shares']),
    }
    with open(CACHE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)

    latest = max(cache['shares']) if cache['shares'] else '-'
    print('已写入 %s | 份额 %d 天，最新 %s | 净值 %d 只'
          % (CACHE, len(cache['shares']), latest, len(cache['nav'])))
    return 0


# ---- 供 fetch_data.py 调用的只读接口 ----
def shares_of(ex, date, code):
    return (ex.get('shares') or {}).get(date, {}).get(code)


def nav_of(ex, date, code):
    return (ex.get('nav') or {}).get(code, {}).get(date)


if __name__ == '__main__':
    sys.exit(main())

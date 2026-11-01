# -*- coding: utf-8 -*-
"""
模块一 + 模块二 · 取数
一次运行并发拉取两条赛道：
  沪深300：sh000300 + 510300/510310/510330/159919
  创业板 ：sz399006 + 159915/159949/159957/159948
数据源：westock-data (腾讯自选股) CLI
输出：raw_data.json
"""
import json, os, time, datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import common
from config import TRACKS, ORDER

CACHE = os.path.join(common.BASE, 'raw_data.json')

# ETF 份额/净值由基金公司在 T+1~T+2 披露，行情商对「尚未披露日」返回最近一次已披露值。
# 因此最后 REFRESH_TAIL 个交易日每次都强制重抓，等真实份额披露后自动回填，避免陈旧值被缓存固化。
# 现在份额/净值改由交易所官方源（fetch_exchange.py，T+0）覆盖，滞后天数大幅缩短，
# 故尾部重抓窗口从 8 缩到 5，省下 westock 的调用开销。
REFRESH_TAIL = int(os.environ.get('ETF_REFRESH_TAIL', '5'))
DAYS = int(os.environ.get('ETF_DAYS', '250'))


def get_trade_days(end=None, days=520):
    """A 股交易日历（沪深300 与创业板共用）"""
    end = end or datetime.date.today().isoformat()
    start = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    out = common.run(['kline', 'sh000300', '--start', start, '--end', end, '--limit', '400'])
    rows = common.parse_kline(out)
    if not rows:
        raise RuntimeError('kline failed：取不到交易日历')
    return rows


def fetch_one(date, track):
    """抓取某赛道单个交易日的指数 + 4 只 ETF"""
    cfg = TRACKS[track]
    rec = {'date': date}
    o = common.run(['quote', cfg['index_code'], '--date', date])
    t = common.first_table(o)
    rec['idx_close'] = common.fnum(t.get('price'))
    rec['idx_float_mv'] = common.fnum(t.get('circulating_market_cap')) or common.fnum(t.get('total_market_cap'))
    o2 = common.run(['etf', 'detail', ','.join(cfg['etfs'].keys()), '--date', date])
    parts = common.split_by_code(o2)
    for code in cfg['etfs']:
        p = parts.get(code, '')
        tb = common.first_table(p) if p else {}
        rec[code] = {
            'close': common.fnum(tb.get('closePrice')),
            'nav': common.fnum(tb.get('nav')),
            'size': common.fnum(tb.get('size')),
            'shares': common.fnum(tb.get('shares')),
            'sharesChg': common.fnum(tb.get('sharesChg')),
            'sharesChgRatio': common.fnum(tb.get('sharesChgRatio')),
        }
    return rec


def apply_exchange(track, results):
    """用交易所官方份额/净值覆盖 westock 的滞后值。

    westock 的 ETF 份额/净值在基金公司披露前会冻结成上一次披露值（T+1~T+2），
    交易所官方披露是 T+0（当日收盘后即出当日份额），因此优先采用交易所值。
    取不到时保留 westock 原值 —— 只会变好，不会变差。
    份额被覆盖后，sharesChg / sharesChgRatio / size 必须按新份额重算。
    """
    try:
        import fetch_exchange
        ex = fetch_exchange.load_cache()
    except Exception as e:
        print('  [%s] 交易所缓存不可用，沿用 westock: %s' % (track, str(e)[:80]))
        return 0, 0
    if not ex.get('shares') and not ex.get('nav'):
        print('  [%s] 交易所缓存为空，沿用 westock' % track)
        return 0, 0

    codes = list(TRACKS[track]['etfs'].keys())
    n_sh = n_nv = 0
    for d in sorted(results):
        rec = results[d]
        for key in codes:
            e = rec.get(key) or {}
            v = fetch_exchange.shares_of(ex, d, key[2:])
            if v is not None and v != e.get('shares'):
                e['shares'] = v
                n_sh += 1
            nv = fetch_exchange.nav_of(ex, d, key[2:])
            if nv is not None and nv != e.get('nav'):
                e['nav'] = nv
                n_nv += 1
            rec[key] = e

    days = sorted(results)
    for i in range(1, len(days)):
        prev, cur = results[days[i - 1]], results[days[i]]
        for key in codes:
            c = cur.get(key) or {}
            p = prev.get(key) or {}
            cs, ps = c.get('shares'), p.get('shares')
            if cs is not None and ps is not None:
                c['sharesChg'] = cs - ps
                c['sharesChgRatio'] = (cs - ps) / ps * 100 if ps else None
            if cs and c.get('nav'):
                c['size'] = cs * c['nav']
            cur[key] = c
    return n_sh, n_nv


def build_track(track, days, jobs):
    cfg = TRACKS[track]
    dates = [d for d, _ in days]
    kline_close = {d: c for d, c in days}
    results = {}
    old = {}
    if os.path.exists(CACHE):
        try:
            with open(CACHE, encoding='utf-8') as fp:
                old = json.load(fp).get(track, {}).get('daily', {}) or {}
        except Exception:
            old = {}
    results = dict(old)
    print('[%s] cache loaded %d days' % (track, len(results)))

    todo = set(d for d in dates if d not in results)
    tail = dates[-REFRESH_TAIL:]
    todo |= set(tail)
    todo = sorted(todo)
    print('[%s] to fetch %d (含尾部强制刷新 %d 天: %s ~ %s)'
          % (track, len(todo), len(tail), tail[0], tail[-1]))

    done, t0 = 0, time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, d, track): d for d in todo}
        for f in as_completed(futs):
            d = futs[f]
            try:
                r = f.result()
                r['idx_close'] = r.get('idx_close') or kline_close.get(d)
                results[d] = r
                done += 1
                if done % 25 == 0:
                    print('  [%s] %d/%d  %.0fs' % (track, done, len(todo), time.time() - t0), flush=True)
            except Exception as e:
                print('  [%s] FAIL %s %s' % (track, d, e))
    print('[%s] fetched %d days, %.0fs' % (track, len(results), time.time() - t0))

    n_sh, n_nv = apply_exchange(track, results)
    print('[%s] 交易所源覆盖：份额 %d 处、净值 %d 处' % (track, n_sh, n_nv), flush=True)
    return {'kline_close': kline_close, 'daily': results}


def main():
    alldays = sorted(get_trade_days(), key=lambda x: x[0])
    print('trading days total:', len(alldays), alldays[0][0], '->', alldays[-1][0])
    days = alldays[-DAYS:]
    print('use last %d: %s -> %s' % (len(days), days[0][0], days[-1][0]))

    out = {}
    if os.path.exists(CACHE):
        try:
            with open(CACHE, encoding='utf-8') as fp:
                out = json.load(fp)
        except Exception:
            out = {}
    for tk in ORDER:
        out[tk] = build_track(tk, days, None)

    with open(CACHE, 'w', encoding='utf-8') as fp:
        json.dump(out, fp, ensure_ascii=False)
    print('saved', CACHE, '->', {k: len(v.get('daily', {})) for k, v in out.items()})


if __name__ == '__main__':
    main()

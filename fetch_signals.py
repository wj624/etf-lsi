# -*- coding: utf-8 -*-
"""抓取「市场环境」六件套：指数估值 / 境内资金面 / ETF 折溢价 / 市场宽度 / 国债曲线 / 跨资产比价。

这六个端点都是 2026-11 加（或改造）到 a-stock-api Worker 的，**彼此完全独立**：
任何一个失败都只让对应面板消失，不影响主看板、ETF 背离、宏观 LSI。

设计原则（与 fetch_exchange.py 一致）：
  - 不引入任何新依赖（只用 requests）
  - 失败可见：错误写进 signals.json 的 errors，Actions 打 ::warning::，但不抛异常中断整轮
  - 宽度数据上游不提供历史，只能每天抓一次快照，在本仓库 `_breadth_history.json` 里自建序列
"""
import json
import os


# 自建 Worker 鉴权：密钥只从环境变量读取，绝不写进代码或提交历史
def _worker_headers(extra=None):
    h = dict(extra or {})
    k = os.environ.get("A_STOCK_API_KEY", "")
    if k:
        h["X-API-Key"] = k
    return h

import sys
import time
from datetime import datetime, timedelta, timezone

import requests

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)
import config as C  # noqa: E402

OUT = os.path.join(BASE, 'signals.json')
BREADTH_HIST = os.path.join(BASE, '_breadth_history.json')
API_BASE = (os.environ.get('ETF_API_BASE') or 'https://a-stock-api.wj4020410.workers.dev').rstrip('/')
TIMEOUT = float(os.environ.get('ETF_API_TIMEOUT', '30'))
BJT = timezone(timedelta(hours=8))

# 本地联调时（ETF_API_BASE 指向 127.0.0.1 的 mock Worker）必须绕过系统代理，
# 否则 requests 会把回环地址也发给 HTTP_PROXY，得到 "目标计算机积极拒绝"。
# 线上跑（Actions / 真实域名）保持默认，照常走环境代理。
_SESS = requests.Session()
if any(h in API_BASE for h in ('127.0.0.1', 'localhost')):
    _SESS.trust_env = False


def now_bj():
    return datetime.now(BJT).strftime('%Y-%m-%d %H:%M')


def _get(path, params=None, tries=3):
    """GET Worker 端点。5xx / {"error":...} / 网络异常都算失败并重试。"""
    last = None
    for i in range(tries):
        try:
            r = _SESS.get(API_BASE + path, params=params or {}, timeout=TIMEOUT, headers=_worker_headers())
            if r.status_code >= 500:
                raise RuntimeError('HTTP %d' % r.status_code)
            j = r.json()
            if isinstance(j, dict) and j.get('error'):
                raise RuntimeError(str(j.get('error')))
            return j
        except Exception as e:
            last = e
            if i + 1 < tries:
                time.sleep(1.2 * (i + 1))
    raise RuntimeError('%s 失败: %s' % (path, last))


def warn(msg):
    print('::warning::%s' % msg)
    print('  !! %s' % msg, flush=True)


# ── 1. 指数估值 ────────────────────────────────────────────────
def get_valuation(out):
    j = _get('/api/index-valuation', {'codes': 'SH000300,SZ399006'})
    rows = j.get('data') or []
    if not rows:
        raise RuntimeError('估值返回空表')
    out['valuation'] = {
        'unit': j.get('unit') or {},
        'note': j.get('note') or '',
        'data': rows,
    }
    if j.get('upstream_error'):
        warn('估值部分失败: %s' % j['upstream_error'])
    print('  估值: %s' % ', '.join(
        '%s PE %s(分位 %s)' % (r.get('name'), r.get('pe'),
                              None if r.get('pe_pct') is None else round(r['pe_pct'] * 100, 1))
        for r in rows), flush=True)


# ── 2. 境内资金面 ──────────────────────────────────────────────
def get_liquidity(out, days=250):
    j = _get('/api/cn-liquidity', {'days': days})
    rows = j.get('data') or []
    if not rows:
        raise RuntimeError('资金面返回空表')
    out['liquidity'] = {
        'unit': j.get('unit') or '%',
        'derived_unit': j.get('derived_unit') or 'bp',
        'fields': j.get('fields') or {},
        'latest': j.get('latest') or {},
        'derived': j.get('derived') or {},
        'data': rows,
    }
    if j.get('upstream_error'):
        warn('资金面部分失败: %s' % j['upstream_error'])
    lt = out['liquidity']['latest']
    print('  资金面: %s  DR007=%s  SHIBOR3M=%s  (%d 条)'
          % (lt.get('date'), lt.get('dr007'), lt.get('shibor_3m'), len(rows)), flush=True)


# ── 3. ETF 折溢价 ──────────────────────────────────────────────
def get_premium(out):
    codes = []
    for k in C.ORDER:
        for code, _name, _disp in C.TRACKS[k]['etf_list']:
            digits = ''.join(ch for ch in code if ch.isdigit())
            if digits and digits not in codes:
                codes.append(digits)
    j = _get('/api/etf-premium', {'codes': ','.join(codes)})
    rows = j.get('data') or []
    if not rows:
        raise RuntimeError('折溢价返回空表')
    out['premium'] = {
        'unit': j.get('unit') or '%',
        'note': j.get('note') or '',
        'codes': codes,
        'data': rows,
    }
    if j.get('upstream_error'):
        warn('折溢价部分失败: %s' % j['upstream_error'])
    print('  折溢价: %s' % ', '.join(
        '%s %s%%' % (r.get('code'), r.get('premium_pct')) for r in rows), flush=True)


# ── 4. 市场宽度（当日快照 + 本地自建历史） ─────────────────────
def get_breadth(out):
    j = _get('/api/market-breadth')
    if not j.get('total'):
        raise RuntimeError('宽度返回空分布')
    keep = ('date', 'up', 'down', 'flat', 'total', 'up_pct',
            'limit_up', 'limit_down', 'max_streak', 'streak_dist', 'is_today')
    row = {k: j.get(k) for k in keep}
    out['breadth'] = {
        'unit': j.get('unit') or 'counts',
        'note': j.get('note') or '',
        'today': row,
        'history': [],
    }
    if j.get('upstream_error'):
        warn('宽度部分失败: %s' % j['upstream_error'])

    # 上游不支持按日期查询，只能每天抓一次当日快照、在本仓库累积成序列。
    # 同一交易日重复运行会覆盖而不是追加（避免一天多个点）。
    hist = {'rows': []}
    if os.path.exists(BREADTH_HIST):
        try:
            with open(BREADTH_HIST, encoding='utf-8') as f:
                hist = json.load(f)
        except Exception:
            hist = {'rows': []}
    rows = [r for r in (hist.get('rows') or []) if r.get('date')]
    if row.get('date'):
        rows = [r for r in rows if r.get('date') != row['date']]
        rows.append({k: row.get(k) for k in keep if k != 'streak_dist'})
    rows.sort(key=lambda r: r['date'])
    rows = rows[-250:]          # 一年足够，别让文件越长越胖
    hist = {'updated': now_bj(), 'rows': rows}
    with open(BREADTH_HIST, 'w', encoding='utf-8') as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)
    out['breadth']['history'] = rows
    print('  宽度: %s 涨%d/跌%d/平%d 涨停%s 跌停%s 最高%d连板（历史 %d 天）'
          % (row.get('date'), row.get('up'), row.get('down'), row.get('flat'),
             row.get('limit_up'), row.get('limit_down'), row.get('max_streak'),
             len(rows)), flush=True)


# ── 5. 国债收益率曲线（尾部窗口，派生期限利差） ────────────────
def get_rates(out, days=250):
    """无风险利率曲线。

    与 ⑨ 的 DR007/SHIBOR 是两回事：那两个是「银行间资金价格」（短端、政策驱动），
    这里是「国债到期收益率」（整条曲线、含增长与通胀预期）。
    股债性价比真正该比的分子/分母里，分母用的是 10Y 国债，不是 DR007。
    """
    j = _get('/api/cn-rates', {'days': days})
    rows = j.get('data') or []
    if not rows:
        raise RuntimeError('国债曲线返回空表')
    out['rates'] = {
        'unit': j.get('unit') or '%',
        'fields': j.get('fields') or {},
        'note': j.get('note') or '',
        'latest': j.get('latest') or {},
        'derived': j.get('derived') or {},
        'data': rows,
    }
    if j.get('upstream_error'):
        warn('国债曲线部分失败: %s' % j['upstream_error'])
    lt = out['rates']['latest']
    b = lambda v: '—' if v is None else '%+.1f' % (v * 100)
    print('  国债: %s  2Y=%s%% 10Y=%s%% 30Y=%s%%  10Y-2Y=%s bp（%d 条）'
          % (lt.get('date'), lt.get('cn_2y'), lt.get('cn_10y'), lt.get('cn_30y'),
             b(lt.get('cn_10y_2y')), len(rows)), flush=True)


def get_macro_ratios(out):
    """跨资产比价：金银比 / 金油比 / 铜金比 + KOSPI/GOLD 固定阈值信号。

    上游是 a-stock-api 的 /api/macro-ratios（服务端已拉 6 条外盘日K算好分位），
    这里只做字段校验与精简，不在本仓库重算任何比值。
    """
    j = _get('/api/macro-ratios')
    keys = ('gold_silver', 'gold_oil', 'copper_gold', 'kospi_gold')
    if not all(j.get(k) for k in keys):
        raise RuntimeError('/api/macro-ratios 字段不全: %s' % ','.join(k for k in keys if not j.get(k)))
    r = {k: j[k] for k in keys}
    r['asof'] = j.get('asof', '')
    r['gold_close'] = j.get('gold_close')
    r['kospi'] = j.get('kospi')
    r['source'] = 'a-stock-api /api/macro-ratios'
    if j.get('errs'):
        r['upstream_error'] = j['errs']
    out['macro_ratios'] = r

STEPS = [
    ('valuation', '指数估值', get_valuation),
    ('liquidity', '境内资金面', get_liquidity),
    ('premium', 'ETF 折溢价', get_premium),
    ('breadth', '市场宽度', get_breadth),
    ('rates', '国债曲线', get_rates),
    ('macro_ratios', '跨资产比价', get_macro_ratios),
]


def main():
    out = {'updated': now_bj(), 'source': API_BASE, 'errors': []}
    print('== 抓取市场环境六件套 ==', flush=True)
    for key, label, fn in STEPS:
        try:
            fn(out)
        except Exception as e:
            msg = '%s: %s' % (label, e)
            out['errors'].append(msg)
            warn(msg)
    # 全部失败时不写文件，避免把上一份完整数据覆盖成空壳
    if not any(k in out for k in ('valuation', 'liquidity', 'premium', 'breadth', 'rates')):
        print('!! 四项全失败，保留上一份 signals.json 不动', flush=True)
        return 1
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    ok = [k for k, _l, _f in STEPS if k in out]
    print('== 完成: %s ；失败: %s ==' % (', '.join(ok) or '无', ', '.join(out['errors']) or '无'),
          flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())

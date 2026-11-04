# -*- coding: utf-8 -*-
"""
交易所官方 ETF 份额 / 净值取数（用于替代 westock 的滞后份额）

背景：
  westock(腾讯自选股) 的 ETF 份额/净值由基金公司 T+1~T+2 披露，行情商对「尚未披露日」
  返回最近一次已披露值，导致看板尾部 1~2 个交易日的 shares / nav / size 被冻结。
  交易所官方披露是 T+0（当日收盘后即公布当日份额），可以彻底消除这个滞后。

数据源（2026-11 起不再依赖 akshare，统一走自建 a-stock-api Worker）：
  沪市份额 : Worker /api/etf-shares?exchange=SH&date=YYYY-MM-DD  -> 上交所 query.sse.com.cn
             直连 query.sse.com.cn 保留为第 2 通道（同源、自带 timeout 与重试）
  深市份额 : 深交所官方 xlsx（www.szse.cn/api/report/ShowReport, CATALOGID=scsj_fund_jjgm）
             区间批量，等价于原 akshare.fund_scale_daily_szse（列名 基金规模(份) 即「份」）
  单位净值 : Worker /api/fund-nav?code=XXX -> 东财 pingzhongdata 全历史
             直连东财 pingzhongdata 保留为第 2 通道
  交易日历 : Worker /api/trade-calendar -> 派生自上证指数日K

为什么改成 Worker：
  2026-11-01 云端实测，GitHub runner 出口 IP 会被 query.sse.com.cn 限流（本机 248/248 全过，
  runner 10/10 全挂，服务端直接回空/HTML 而非超时）。Worker 走 Cloudflare 出口，不受 runner
  IP 影响，且带 KV 缓存，250 天回填从「分钟级 + 高失败率」变成「秒级 + 稳定」。
  同时去掉 akshare 这层重依赖（其内部 http.get 既无 timeout 也无重试）。

单位约定（错一个数量级就会静默毁掉全部份额指标）：
  上交所接口 TOT_VOL 的原始单位是「万份」，必须 × 10000 才是「份」；
  深交所 xlsx 的「基金规模(份)」本身已是「份」，不得再乘。

输出：_exchange_shares.json
  {
    "shares": {"YYYY-MM-DD": {"510300": 38866990000.0, ...}},
    "nav":    {"510300": {"YYYY-MM-DD": 4.0609, ...}},
    "meta":   {"updated": "...", "window_days": 250, "tail": 10, "sse_fail": 0}
  }

失败不影响主流程：取不到就返回 None，上层回退 westock 原值。
"""
import io, json, os, random, sys, threading, time, datetime

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

CACHE = os.path.join(BASE, '_exchange_shares.json')

# 自建数据代理（Cloudflare Worker）。国内本地调试可覆盖为其它地址。
API_BASE = (os.environ.get('ETF_API_BASE') or 'https://a-stock-api.wj4020410.workers.dev').rstrip('/')
API_TIMEOUT = float(os.environ.get('ETF_API_TIMEOUT', '30'))

# 首次回填窗口（交易日数）与每次强制刷新的尾部天数
WINDOW_DAYS = int(os.environ.get('ETF_EXCHANGE_DAYS', '250'))
TAIL = int(os.environ.get('ETF_EXCHANGE_TAIL', '10'))
SSE_WORKERS = int(os.environ.get('ETF_SSE_WORKERS', '4'))
MAX_SSE_CALLS = int(os.environ.get('ETF_MAX_SSE_CALLS', '320'))
# 上交所单日重试次数；失败项第二轮补抓的间隔秒数；连续失败多少天后熔断
SSE_RETRY = int(os.environ.get('ETF_SSE_RETRY', '3'))
SSE_PASS2_GAP = float(os.environ.get('ETF_SSE_PASS2_GAP', '1.5'))
SSE_BREAKER = int(os.environ.get('ETF_SSE_BREAKER', '12'))
# 深交所接口单次返回上限约 65535 行（16-bit），全市场 ETF 约 770 行/交易日，
# 超过上限时接口不报错而是直接返回空表 —— 必须分段请求，每段留足余量
SZSE_CHUNK = int(os.environ.get('ETF_SZSE_CHUNK', '20'))

# 上交所份额直连参数（与 Worker 里用的是完全同一接口，只是我们自带 timeout 与重试）
SSE_URL = 'https://query.sse.com.cn/commonQuery.do'
SSE_HEADERS = {
    'Referer': 'https://www.sse.com.cn/',
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
    'Accept': '*/*',
}

# 深交所基金规模 xlsx（区间查询，一次拿回 start~end 内每个交易日的全市场 ETF 规模）
SZSE_URL = 'https://www.szse.cn/api/report/ShowReport'
SZSE_HEADERS = {
    'Host': 'www.szse.cn',
    'Referer': 'https://www.szse.cn/market/fund/volume/etf/index.html',
    'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
}

# 东财净值 js（Worker 通道失败时的兜底）
EM_NAV_URL = 'https://fund.eastmoney.com/pingzhongdata/%s.js'
EM_NAV_HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Referer': 'https://fund.eastmoney.com/',
}

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


def _retry(fn, tries=3, gap=2, jitter=0.5, label=''):
    """带退避重试。

    jitter：每轮延迟乘上一个 [1-jitter, 1+jitter] 的随机系数。
      **多线程必须加**：4 个 worker 同时失败、同时 sleep 同样时长，
      下一轮就会同时回到服务端形成重试风暴，反而更容易被限流。
    """
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last = '%s: %s' % (type(e).__name__, str(e)[:90])
            if i == tries - 1:      # 最后一次不再空等
                break
            d = gap * (i + 1)
            if jitter:
                d *= random.uniform(1.0 - jitter, 1.0 + jitter)
            time.sleep(d)
    raise RuntimeError(('%s ' % label if label else '') + str(last))


def _api_get(path, params=None, tries=3):
    """GET 自建 Worker。内部已自带重试，调用方不必再套 _retry。"""
    import requests
    last = None
    for i in range(tries):
        try:
            r = requests.get(API_BASE + path, params=(params or {}), timeout=API_TIMEOUT)
            r.raise_for_status()
            j = r.json()
            if isinstance(j, dict) and j.get('error'):
                # Worker 把上游失败包成 200 + {"error": ...} 的情况也要当失败重试
                raise RuntimeError('%s: %s' % (j.get('error'), str(j.get('message'))[:80]))
            return j
        except Exception as e:
            last = '%s: %s' % (type(e).__name__, str(e)[:90])
            if i == tries - 1:
                break
            time.sleep(1.5 * (i + 1))
    raise RuntimeError('[Worker %s] %s' % (path, last))


def get_trade_days(days=520):
    """A 股交易日历 -> ['YYYY-MM-DD', ...] 升序"""
    j = _api_get('/api/trade-calendar', {'start': '2010-01-01'})
    out = []
    for x in (j.get('data') or []):
        s = str(x)[:10].replace('/', '-')
        if len(s) == 10 and s[4] == '-':
            out.append(s)
    out = sorted(set(out))
    if not out:
        raise RuntimeError('交易日历为空（Worker 返回 0 条）')
    return out[-days:]


class _Breaker:
    """简易熔断器：连续失败达到阈值就认定「接口整段不可用」，后续日期直接跳过。

    为什么需要：首次回填要抓 250 天，每天 3 次重试 × 退避(2/4s) ≈ 6 秒。
    如果上游整段挂掉（不是偶发），250 天 ÷ 4 线程 × 6s ≈ 6 分钟纯白等，
    加上第二轮补抓更久。熔断后直接跳完，1 分钟内结束，缺口交给下一轮补。
    """

    def __init__(self, limit):
        self.limit, self.streak, self.tripped = limit, 0, False
        self._lock = threading.Lock()

    def ok(self):
        with self._lock:
            self.streak = 0

    def bad(self):
        with self._lock:
            self.streak += 1
            if self.streak >= self.limit and not self.tripped:
                self.tripped = True
                print('  !! 上交所接口连续失败 %d 次，判定整段不可用，本轮熔断跳过剩余日期'
                      % self.streak, flush=True)


_BREAKER = _Breaker(SSE_BREAKER)


def _sse_via_worker(date_compact):
    """通道 1：自建 Worker 代理上交所（Cloudflare 出口 IP，不受 runner IP 限流影响）。

    Worker 返回的 shares_10k 单位是「万份」，这里 × 10000 换成「份」，
    与 _exchange_shares.json 的历史口径保持一致。
    """
    j = _api_get('/api/etf-shares', {'exchange': 'SH', 'date': _compact2dash(date_compact)})
    out = {}
    for it in (j.get('data') or []):
        c = str(it.get('code') or '').strip()
        if c not in SH_CODES:
            continue
        v = it.get('shares_10k')
        if v is None:
            continue
        try:
            # 万份 -> 份。round 只为抹掉 float 噪声（4458738.77*1e4 会算出 ...99.99999），
            # 否则 592KB 的份额缓存每天都会产生「值没变但末位抖了」的无意义 diff
            out[c] = round(float(v) * 10000.0, 2)
        except Exception:
            pass
    return out


def _sse_via_http(date_compact):
    """通道 2：直连 query.sse.com.cn 的同一个接口（与 Worker 同源），
    但我们自带 timeout=25s、自带重试，且不依赖 Worker 是否在线。

    实测两者结果完全一致（510300：TOT_VOL 3886698.77 × 1e4 = 38,866,987,700）；
    上交所原始单位是「万份」，必须 × 10000。
    """
    import requests
    d = _compact2dash(date_compact)
    params = {
        'isPagination': 'true', 'pageHelp.pageSize': '10000',
        'pageHelp.pageNo': '1', 'pageHelp.beginPage': '1',
        'pageHelp.cacheSize': '1', 'pageHelp.endPage': '1',
        'sqlId': 'COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L',
        'STAT_DATE': d,
    }

    def _once():
        r = requests.get(SSE_URL, params=params, headers=SSE_HEADERS, timeout=25)
        r.raise_for_status()
        rows = r.json().get('result') or []
        out = {}
        for it in rows:
            c = str(it.get('SEC_CODE', '')).strip()
            if c in SH_CODES:
                try:
                    out[c] = round(float(it['TOT_VOL']) * 10000.0, 2)    # 万份 -> 份
                except Exception:
                    pass
        return out

    return _retry(_once, tries=SSE_RETRY, gap=2, label='[直连]')


def fetch_sse(date_compact):
    """上交所单日全部 ETF 份额 -> {code: shares}

    三个层次（依次降级）：
      1. 自建 Worker（Cloudflare 出口，绕开 runner IP 被限流的老问题）
      2. 直连 query.sse.com.cn（同源、自带 timeout）
      3. 熔断跳过 —— 两个通道连续失败达阈值时直接放弃，避免整轮回填卡死
    空表（接口正常但当天无数据）不算失败，返回 {}。
    """
    if _BREAKER.tripped:
        raise RuntimeError('接口熔断中，本轮跳过')
    err1 = None
    try:
        out = _sse_via_worker(date_compact)
        _BREAKER.ok()
        return out
    except Exception as e1:
        # 注意：except 子句里的 e1 出了块就会被释放，必须先另存一份给下面拼接报错用
        err1 = e1
        print('  ~ sse %s Worker 通道失败（%s），改直连' % (date_compact, str(e1)[:80]), flush=True)
    try:
        out = _sse_via_http(date_compact)
        _BREAKER.ok()
        return out
    except Exception as e2:
        # 两条通道都挂才算真失败，记一笔给熔断器
        _BREAKER.bad()
        raise RuntimeError('%s｜直连也失败: %s' % (err1, e2))


def fetch_szse(start_compact, end_compact):
    """深交所区间批量 ETF 份额 -> {date: {code: shares}}

    直连官方 xlsx（等价于原 akshare.fund_scale_daily_szse）：
      CATALOGID=scsj_fund_jjgm / TABKEY=tab1 / jjlb=ETF
      列：日期 | 基金代码 | 基金简称 | 基金规模(份)
    「基金规模(份)」已是「份」，不再乘 10000。
    注意 SHOWTYPE=JSON 对该接口返回 HTTP 500，只有 xlsx 可用。
    """
    import requests
    from openpyxl import load_workbook
    params = {
        'SHOWTYPE': 'xlsx',
        'CATALOGID': 'scsj_fund_jjgm',
        'TABKEY': 'tab1',
        'txtStart': _compact2dash(start_compact),
        'txtEnd': _compact2dash(end_compact),
        'jjlb': 'ETF',
        'random': str(random.random()),
    }

    def _once():
        r = requests.get(SZSE_URL, params=params, headers=SZSE_HEADERS, timeout=90)
        r.raise_for_status()
        if r.content[:2] != b'PK':
            # 服务端出错时回的是 HTML/JSON 错误页，这里给它一个可读的报错
            raise RuntimeError('非 xlsx 响应（前 80 字节: %r）' % r.content[:80])
        wb = load_workbook(io.BytesIO(r.content), data_only=True)
        ws = wb[wb.sheetnames[0]]
        rows = ws.iter_rows(values_only=True)
        head = next(rows, None) or ()
        idx = {}
        for i, h in enumerate(head):
            if h:
                idx[str(h).strip()] = i
        ci = idx.get('基金代码', 1)
        di = idx.get('日期', 0)
        si = idx.get('基金份额', idx.get('基金规模(份)', 3))
        out = {}
        for row in rows:
            if not row:
                continue
            c = str(row[ci] if ci < len(row) else '').strip()
            if c not in SZ_CODES:
                continue
            d = str(row[di] if di < len(row) else '')[:10].replace('/', '-')
            if len(d) != 10 or d[4] != '-':
                continue
            try:
                out.setdefault(d, {})[c] = float(row[si])
            except Exception:
                pass
        return out

    return _retry(_once, tries=3, gap=3, label='[深交所]')


def _nav_extract(text, var):
    """从 pingzhongdata js 里抠出 `var = [...];` 的数组字面量"""
    i = text.find(var)
    if i < 0:
        return []
    a = text.find('[', i)
    if a < 0:
        return []
    b = text.find('];', a)
    if b < 0:
        return []
    try:
        return json.loads(text[a:b + 1])
    except Exception:
        return []


def _nav_via_em_direct(code):
    """通道 2：直连东财 pingzhongdata。

    与 Worker 内的 fetchFundNav 逐字对齐：x 是「北京零点」的时间戳（等价 UTC-16:00），
    必须先 +8h 再取日期，否则整段净值会错位一天、和交易日历/份额对不上。
    """
    import requests
    r = requests.get(EM_NAV_URL % code, headers=EM_NAV_HEADERS, timeout=25)
    r.raise_for_status()
    m = {}
    for it in _nav_extract(r.text, 'Data_netWorthTrend'):
        if not isinstance(it, dict) or it.get('x') is None:
            continue
        try:
            ts = int(it['x']) + 8 * 3600 * 1000
            d = (datetime.datetime(1970, 1, 1)
                 + datetime.timedelta(milliseconds=ts)).strftime('%Y-%m-%d')
            m[d] = float(it.get('y'))
        except Exception:
            pass
    return m


def fetch_nav(codes):
    """单位净值全历史 -> {code: {date: nav}}"""
    out = {}
    for c in codes:
        err = None
        try:
            j = _api_get('/api/fund-nav', {'code': c})
            m = {}
            for it in (j.get('data') or []):
                d = str(it.get('date') or '')[:10]
                if len(d) != 10 or d[4] != '-':
                    continue
                try:
                    m[d] = float(it['nav'])
                except Exception:
                    pass
            if m:
                out[c] = m
                print('  nav %s ok (%d 天)' % (c, len(m)), flush=True)
                continue
            err = 'Worker 返回 0 条'
        except Exception as e:
            err = str(e)[:80]
        # Worker 不可用（或空表）时退到东财直连
        try:
            m = _retry(lambda c=c: _nav_via_em_direct(c), tries=2, gap=2, label='[东财直连]')
            if m:
                out[c] = m
                print('  nav %s ok (%d 天，东财直连兜底；Worker: %s)'
                      % (c, len(m), err), flush=True)
                continue
            err = '%s / 东财直连也空' % err
        except Exception as e:
            err = '%s / 东财直连失败: %s' % (err, str(e)[:80])
        print('  nav %s FAIL %s' % (c, err), flush=True)
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


def _gh_annot(level, msg):
    """GitHub Actions 注解（本地运行不打印 :: 噪音）"""
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        print('::%s::%s' % (level, msg), flush=True)


def _compact2dash(dc):
    """20261030 -> 2026-10-30"""
    return '%s-%s-%s' % (dc[:4], dc[4:6], dc[6:])


def _sse_run(dates, cache, workers, gap=0.0):
    """跑一轮上交所抓取 -> (成功天数, 仍失败日期列表)

    dates 一律用**紧凑格式 YYYYMMDD**（与 fetch_sse 入参一致），返回的失败清单也是紧凑格式，
    这样第 2 轮可以直接把失败清单回灌进来；转成带横线只为写缓存 key。
    接口正常但当天无该 ETF 份额时返回 {}，这种情况既不算成功也不算失败。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    ok, failed = 0, []
    with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        futs = {ex.submit(fetch_sse, dc): dc for dc in dates}
        for f in as_completed(futs):
            dc = futs[f]
            try:
                m = f.result()
            except Exception:
                failed.append(dc)
            else:
                if m:
                    cache['shares'].setdefault(_compact2dash(dc), {}).update(m)
                    ok += 1
            if gap:
                time.sleep(gap)
    return ok, sorted(failed)


def main():
    mapping = load_etfs()
    codes = sorted(set(c for c, _ in mapping.values()))
    print('标的数量: %d（沪 %d / 深 %d）' % (len(codes), len(SH_CODES), len(SZ_CODES)))
    print('数据源: %s' % API_BASE)

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
    sse_failed_dates = []
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

        # ---- 上交所：逐日（开工探测 + 第 1 轮并发 + 第 2 轮失败项串行补抓）----
        if SH_CODES:
            todo_c = [d.replace('-', '') for d in todo][-MAX_SSE_CALLS:]
            t0 = time.time()

            # 开工前先探最近一个交易日：既然第 1 通道是 Worker，探测失败基本等于
            # 「网络整体不通」或「Worker 挂了且直连也被限流」，此时整段跳过比逐日白等划算
            # （2026-11-01 实测：runner 出口 IP 被 query.sse.com.cn 限流时，
            #  每个日期都要烧 3 次 Worker 重试 + 3 次直连重试 ≈ 12s）。
            probe = todo_c[-1]
            try:
                pm = fetch_sse(probe)
                if pm:
                    cache['shares'].setdefault(_compact2dash(probe), {}).update(pm)
                probed = True
            except Exception as e:
                probed = False
                print('  !! 开工探测失败（%s）' % str(e)[:120], flush=True)

            if not probed:
                print('上交所: 接口当前不可用，本轮整体跳过 %d 天（保留已有缓存，下轮自动补抓）'
                      % len(todo_c), flush=True)
                _gh_annot('warning', '上交所份额接口本轮不可用，%d 天未刷新（沿用仓库里的缓存份额）'
                          % len(todo_c))
                sse_failed_dates = [_compact2dash(x) for x in todo_c]
                sse_fail += len(todo_c)
            else:
                got, failed = _sse_run(todo_c[:-1], cache, SSE_WORKERS)
                print('上交所: 第 1 轮 %d/%d 天成功，失败 %d，耗时 %.0fs'
                      % (got, len(todo_c) - 1, len(failed), time.time() - t0), flush=True)

                # 第 2 轮：只补失败的那几天，**单线程串行** + 拉长间隔。
                # 为什么降并发：上交所接口对同 IP 的并发很敏感，4 个线程同时失败大概率是被限流了；
                # 再用 4 个线程重试只会继续撞墙，串行 + 1.5s 间隔才是能恢复的姿势。
                if failed and not _BREAKER.tripped:
                    print('  第 2 轮：串行补抓 %d 天（间隔 %.1fs）...' % (len(failed), SSE_PASS2_GAP), flush=True)
                    ok2, still = _sse_run(failed, cache, 1, gap=SSE_PASS2_GAP)
                    print('  第 2 轮：救回 %d 天，仍失败 %d 天（累计 %.0fs）'
                          % (ok2, len(still), time.time() - t0), flush=True)
                    got += ok2
                    failed = still

                sse_fail += len(failed)
                sse_failed_dates = [_compact2dash(x) for x in failed]
                if failed:
                    print('  !! 仍失败 %d 天：%s%s'
                          % (len(failed), ' '.join(sse_failed_dates[:10]),
                             ' ...' if len(failed) > 10 else ''), flush=True)
                    print('  !! 这些日期沿用 _exchange_shares.json 里已有的份额（不会用前一天冒充）；'
                          '完全没有缓存的日期才由 fetch_data.py 回退 westock 旧值。'
                          '下一轮会自动重新补抓（尾部 %d 天强制刷新 + 窗口内缺失全部重抓）' % TAIL, flush=True)
                    _gh_annot('warning', '上交所份额有 %d 天两轮抓取均失败（沿用缓存份额）：%s'
                              % (len(failed), '、'.join(sse_failed_dates[:10])))

    # ---- 净值：全历史，便宜，每次都刷 ----
    nav = fetch_nav(codes)
    for c, m in nav.items():
        cache['nav'].setdefault(c, {}).update(m)

    # ---- 滚动裁剪：份额缓存只保留最近 KEEP_DAYS 个交易日 ----
    # 交易所源在这里的角色是「给最近一段时间做 T+0 精确覆盖」，更早的历史由 westock 兜着。
    # 不裁剪的话这个文件会一年年变大（也是唯一会被提交回仓库的大文件），
    # 裁到窗口大小后体积恒定，github 上不会累积垃圾。
    KEEP_DAYS = WINDOW_DAYS + TAIL
    if len(cache['shares']) > KEEP_DAYS:
        drop = sorted(cache['shares'])[:-KEEP_DAYS]
        for d in drop:
            cache['shares'].pop(d, None)
        print('  份额缓存滚动裁剪：丢弃 %d 天窗口外旧数据，保留 %d 天（%s ~ %s）'
              % (len(drop), len(cache['shares']), min(cache['shares']), max(cache['shares'])))

    cache['meta'] = {
        'updated': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'window_days': WINDOW_DAYS,
        'tail': TAIL,
        'sse_fail': sse_fail,
        # 明细留在产物里，方便事后判断「哪天缺、缺了几次、是不是同一批日期反复失败」
        'sse_failed_dates': sse_failed_dates[:60],
        'sse_breaker_tripped': _BREAKER.tripped,
        'days': len(cache['shares']),
        'source': API_BASE,
    }
    with open(CACHE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)

    latest = max(cache['shares']) if cache['shares'] else '-'
    print('已写入 %s | 份额 %d 天，最新 %s | 净值 %d 只'
          % (CACHE, len(cache['shares']), latest, len(cache['nav'])))
    if sse_fail:
        print('提示：上交所 %d 天未取到，这些日期在报告中会自动回退 westock 旧值' % sse_fail)
    return 0


# ---- 供 fetch_data.py 调用的只读接口 ----
def shares_of(ex, date, code):
    return (ex.get('shares') or {}).get(date, {}).get(code)


def nav_of(ex, date, code):
    return (ex.get('nav') or {}).get(code, {}).get(date)


if __name__ == '__main__':
    sys.exit(main())

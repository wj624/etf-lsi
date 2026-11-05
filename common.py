# -*- coding: utf-8 -*-
"""公共工具：node / westock-data 定位、子进程取数、表格解析、中文字体、HTTP JSON。

被 fetch_data.py / fetch_ratios.py / render.py 共用，避免三处重复实现。
"""
import os, re, json, subprocess, time, shutil, urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
_PKG = os.path.dirname(BASE) if os.path.basename(BASE).lower() == 'app' else BASE

# 不再硬编码任何本机绝对路径（含用户名）：换机器 / CI 时不会误命中，也不泄露本机信息。
# 优先仓库内 runtime，其次 PATH 里的 node，最后环境变量 NODE_BIN。
_NODE_CANDIDATES = [
    os.path.join(_PKG, 'runtime', 'node', 'node.exe'),
    os.path.join(BASE, 'runtime', 'node', 'node.exe'),
]
_SKILL_CANDIDATES = [
    os.path.join(BASE, 'westock-data'),
    os.path.join(_PKG, 'westock-data'),
]


def find_node():
    n = os.environ.get('NODE_BIN')
    if n and os.path.exists(n):
        return n
    for c in _NODE_CANDIDATES:
        if os.path.exists(c):
            return c
    w = shutil.which('node') or shutil.which('node.exe')
    if w:
        return w
    # 导入期不抛错：render.py 等只想用字体 / 表格工具也会 import common，
    # 缺 node 不该让整轮崩溃；真正需要取数时由 run() 显式报错终止。
    return ''


def find_skill():
    for c in _SKILL_CANDIDATES:
        if os.path.exists(os.path.join(c, 'scripts', 'index.js')):
            return c
    return ''


NODE = find_node()
_SKILL = find_skill()
IDX = os.path.join(_SKILL, 'scripts', 'index.js') if _SKILL else ''
CWD = os.path.dirname(IDX) if IDX else BASE


def run(args, retry=3, timeout=180):
    """调用 westock-data CLI；stdout 为空视为失败并重试"""
    if not NODE or not IDX or not os.path.isfile(IDX):
        # 导入期不抛错；真正取数时缺依赖必须显式失败，绝不静默返回空串
        # （空串会让下游 parse_kline / first_table 写出空值，违背 README 防 Bug 铁律）
        raise RuntimeError('westock-data 不可用：node 或技能目录缺失，无法取数（检查 runtime/ 与 westock-data/，或设置 NODE_BIN）')
    for i in range(retry):
        try:
            r = subprocess.run([NODE, IDX] + args, cwd=CWD, capture_output=True,
                               text=True, encoding='utf-8', errors='ignore', timeout=timeout)
            if r.stdout and r.stdout.strip():
                return r.stdout
        except Exception:
            pass
        time.sleep(1.0 * (i + 1))
    return ''


def first_table(text):
    """取第一段 markdown 表格的首行 -> dict"""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if ln.startswith('|'):
            hdr = [c.strip() for c in ln.strip().strip('|').split('|')]
            if i + 1 < len(lines) and re.match(r'^\|[\s\-|]+\|$', lines[i + 1].strip()):
                if i + 2 < len(lines) and lines[i + 2].startswith('|'):
                    row = [c.strip() for c in lines[i + 2].strip().strip('|').split('|')]
                    return dict(zip(hdr, row))
    return {}


def split_by_code(text):
    """按 '#### <code>' 切分为 {code: 段落文本}"""
    parts, cur = {}, None
    for ln in text.splitlines():
        m = re.match(r'^####\s+(\S+)', ln)
        if m:
            cur = m.group(1)
            parts[cur] = []
            continue
        if cur:
            parts[cur].append(ln)
    return {k: '\n'.join(v) for k, v in parts.items()}


def parse_kline(text):
    """markdown K线表格 -> [(date, close), ...] 升序"""
    rows = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln.startswith('|'):
            continue
        p = [x.strip() for x in ln.strip('|').split('|')]
        if len(p) < 3:
            continue
        if not (len(p[0]) == 10 and p[0][4] == '-' and p[0][7] == '-'):
            continue
        try:
            c = float(p[2])
        except Exception:
            continue
        if c > 0:
            rows.append((p[0], c))
    rows.sort(key=lambda x: x[0])
    return rows


def fnum(v):
    try:
        return float(str(v).replace(',', ''))
    except Exception:
        return None


# ---------------- 中文字体 ----------------
_FONT_CACHE = {'p': None}


def find_cjk_font():
    """跨平台中文字体探测：GitHub Actions(Linux) / Windows / macOS"""
    if _FONT_CACHE['p'] is not None:
        return _FONT_CACHE['p']
    cands = []
    # 随包字体
    cands += [
        os.path.join(_PKG, 'fonts', 'msyh.ttc'),
        os.path.join(BASE, 'fonts', 'msyh.ttc'),
    ]
    # Linux（GitHub Actions 通过 apt 安装 fonts-noto-cjk）
    for d in ['/usr/share/fonts/opentype/noto',
              '/usr/share/fonts/truetype/noto',
              '/usr/share/fonts/noto-cjk',
              '/usr/share/fonts/truetype/wqy',
              '/usr/share/fonts/wqy-zenhei']:
        if os.path.isdir(d):
            for root, _, files in os.walk(d):
                for fn in files:
                    if fn.lower().endswith(('.ttf', '.otf', '.ttc')) and ('cjk' in fn.lower() or 'wqy' in fn.lower()):
                        cands.append(os.path.join(root, fn))
    # Windows
    cands += [
        r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\msyhbd.ttc',
        r'C:\Windows\Fonts\simhei.ttf', r'C:\Windows\Fonts\simsun.ttc',
    ]
    # macOS
    cands += [
        '/System/Library/Fonts/PingFang.ttc',
        '/Library/Fonts/Arial Unicode.ttf',
        '/System/Library/Fonts/STHeiti Light.ttc',
    ]
    import matplotlib.font_manager as fm
    seen = set()
    for p in cands:
        if p and os.path.exists(p) and p not in seen:
            seen.add(p)
            try:
                fm.FontProperties(fname=p)
                _FONT_CACHE['p'] = p
                return p
            except Exception:
                continue
    # 兜底：matplotlib 自带字体里找含 CJK 的
    try:
        for p in fm.findSystemFonts():
            low = p.lower()
            if any(k in low for k in ('cjk', 'notosanssc', 'wqy', 'heiti', 'pingfang', 'msyh')):
                _FONT_CACHE['p'] = p
                return p
    except Exception:
        pass
    _FONT_CACHE['p'] = ''
    return ''


_FRED_CSV_URL = 'https://fred.stlouisfed.org/graph/fredgraph.csv?id=%s'


def fred_csv(series_id, observation_start=None, timeout=60, retry=3):
    """免密钥兜底通道：把 fredgraph.csv 解析成 {date: float}。

    为什么需要它：api.stlouisfed.org 在 runner 的共享出口 IP 下会随机返回 HTTP 500
    （实测同一分钟内 20 个序列有 3 个 500、换一分钟又全部正常），一旦 3 次重试都没
    命中就整条序列变空字典，进而让 GLI / RRP / DXY 整条曲线变成 null。
    fredgraph.csv 是网页图表用的后端，入口不同、不限频、不需要 api_key，实测稳定。

    observation_start: 只保留不早于该日期的观测（等价于 API 的 observation_start）。
    """
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(_FRED_CSV_URL % series_id,
                                         headers={'User-Agent': 'etf-lsi-monitor/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                text = r.read().decode('utf-8', 'replace')
            out = {}
            # 首行是表头 observation_date,<SID>；缺失值在 CSV 里是空串（不是 '.'）
            for ln in text.splitlines()[1:]:
                p = ln.strip().split(',')
                if len(p) < 2:
                    continue
                d, v = p[0].strip(), p[1].strip()
                if not d or v in ('', '.', 'NA'):
                    continue
                if observation_start and d < observation_start:
                    continue
                try:
                    out[d] = float(v)
                except ValueError:
                    continue
            if out:
                return out
            last = RuntimeError('CSV 返回 0 条有效观测')
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError('fred_csv failed: %s -> %s' % (series_id, last))


def http_json(url, timeout=40, retry=3, csv_id=None, observation_start=None, on_csv=None):
    """GET JSON（带重试），用于 FRED API。

    csv_id：传 FRED 序列号后，JSON 通道 retry 次全失败时自动改走 fredgraph.csv，
            并把结果包成 {'observations': [{date, value}, ...]} 返回，
            调用方拿到的数据结构与 API 一致，不需要改解析逻辑。
    on_csv：真正走了兜底通道时回调一次，供调用方统计「本轮有几个序列是靠兜底救回来的」。
    """
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'etf-lsi-monitor/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    if csv_id:
        d = fred_csv(csv_id, observation_start=observation_start)
        print('  ~~ %-18s JSON 通道 %d 次全失败（%s），已回退 fredgraph.csv：%d 条'
              % (csv_id, retry, last, len(d)), flush=True)
        if on_csv:
            on_csv()
        return {'observations': [{'date': k, 'value': str(v)} for k, v in sorted(d.items())]}
    raise RuntimeError('http_json failed: %s -> %s' % (url, last))


def percentile_linear_interpolation(vals, length, pct):
    """复刻 Pine 的 ta.percentile_linear_interpolation(source, length, percentage)"""
    arr = [v for v in vals[-length:] if v is not None]
    if not arr:
        return None
    s = sorted(arr)
    n = len(s)
    if n == 1:
        return s[0]
    k = (n - 1) * (pct / 100.0)
    f = int(k)
    c = min(f + 1, n - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def sma(vals, n):
    """简单移动平均，返回与 vals 等长（前 n-1 位为 None）"""
    out = []
    s = 0.0
    q = []
    for v in vals:
        if v is None:
            out.append(None)
            continue
        q.append(v)
        s += v
        if len(q) > n:
            s -= q.pop(0)
        out.append(s / len(q) if len(q) == n else None)
    return out

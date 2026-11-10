# -*- coding: utf-8 -*-
"""
从看板 HTML（etf_lsi_dashboard.html）内嵌的 const D 生成「给 AI 读」的文档。

产出（默认写到本脚本所在目录，可用 --out 指定）：
  llms.txt   —— 全站数据的人话快照，AI 抓取入口（llms.txt 约定名）
  data.json  —— const D 原样导出，机器可读全量数据

设计边界（改之前先读 README 附录「AI 可读文档」）：
  - 单一真相源 = 看板 HTML 里的 const D。不重新取数、不联网、不新增依赖、
    不读任何密钥、不改任何口径/阈值/单位，AI 读到的与页面看到的完全一致。
  - 降级不阻断：源缺失 / 解析失败只打印 ::warning:: 并以 0 退出，**绝不写空文件**，
    也绝不让主报告失败（daily_run.py 里登记为 fatal=False）。
  - 产物不提交 main：只由 daily.yml 复制进 public/ 发布到 gh-pages / Cloudflare Pages，
    避免在 main 留下一份永不更新的过期副本。
  - 新增/改名字段时同步改本文件的 META_CN 与各段生成器；缺字段一律显示「—」，不抛异常。

用法：
  python make_llm_summary.py                    # 生成 llms.txt / data.json
  python make_llm_summary.py --check            # 只打印 llms.txt，不写文件
  python make_llm_summary.py --out /tmp/xxx     # 写到指定目录
  python make_llm_summary.py --src /path/x.html # 指定源 HTML（本地验证用）
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CF = 'https://etf-lsi.pages.dev'
GH = 'https://wj624.github.io/etf-lsi'

# LSI core 字段中文名（仅用于展示，不参与计算；缺的键原样显示）
CORE_CN = {
    'lsi': 'LSI 内部压力', 'sofr': 'SOFR 担保隔夜融资利率',
    'rrp_rate': 'RRP 隔夜逆回购奖励利率', 'effr': 'EFFR 有效联邦基金利率',
    'iorb': 'IORB 准备金余额利率', 'us02y': '2 年期美债收益率',
    'us10y': '10 年期美债收益率', 'yield_spread': '10Y-2Y 期限利差',
    't10yie': '10Y 盈亏平衡通胀预期', 'dfii10': '10Y 实际利率 (TIPS)',
    'credit': '高收益债信用利差 (OAS)', 'credit_roc': '信用利差变化率',
    'cpi_yoy': '美国 CPI 同比', 'gli': '全球流动性 GLI',
    'walcl_T': '美联储总资产 WALCL', 'wtregen_T': 'TGA 财政部一般账户',
    'rrp_T': 'RRP 逆回购余额', 'rrp_pct': 'RRP 占峰值比例',
    'wresbal_T': '商业银行准备金', 'wrb_T': '准备金（另一口径）',
    'reserve_gdp': '准备金 / GDP', 'reserve_assets': '准备金 / 银行资产',
    'tlc': '总流动性周期环比', 'impulse': '流动性冲量',
    'dxy': '广义美元指数 DTWEXBGS', 'dxy_ma': '美元指数 50 日均线',
    'gli_high_th': 'GLI 高位阈值', 'gli_low_th': 'GLI 低位阈值',
}

RATIO_ORDER = ['style_cyb', 'style_star', 'bond']


def num(x, nd=2, dash='—'):
    if x is None:
        return dash
    try:
        return format(float(x), ',.%df' % nd)
    except (TypeError, ValueError):
        return str(x)


def pctv(x, nd=2, sign=False, dash='—'):
    """x 已经是百分数数值（如 92.31 表示 92.31%），只做格式化，不再乘 100。"""
    if x is None:
        return dash
    try:
        v = float(x)
        return (('%+.' + str(nd) + 'f%%') if sign else ('%.' + str(nd) + 'f%%')) % v
    except (TypeError, ValueError):
        return str(x)


def s(x, dash='—'):
    if x is None or x == '':
        return dash
    return str(x)


def yi(x, nd=2):
    """原始「份」/「元」转「亿份」/「亿元」。None 透传。"""
    if x is None:
        return None
    try:
        return float(x) / 1e8
    except (TypeError, ValueError):
        return None


def kv_table(rows, head=('项目', '数值')):
    out = ['| %s | %s |' % head, '| :--- | :--- |']
    for a, b in rows:
        out.append('| %s | %s |' % (str(a).replace('|', '\\|'), str(b).replace('|', '\\|')))
    return out


def cn_liq_center(liq):
    """与看板 renderCnLiquidity() 内 winStat() 完全同算法：
       末 WIN=20 行内跳过 null，n>=3 才返回 (均值, min, max, n)。
       纯本地计算，不联网、不改口径 —— ⑨ 的 20 日中枢 / 波动区间是浏览器现算的，
       不落 const D，所以这里按同一算法自算一份，让 AI 也能读到这个派生值。
    """
    rows = [r for r in (liq.get('data') or []) if isinstance(r, dict) and r.get('date')]
    if not rows:
        return None
    WIN = 20
    vals = []
    for r in rows:
        v = r.get('dr001')
        vals.append(float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None)
    i = len(rows) - 1
    ssum, n = 0.0, 0
    lo, hi = float('inf'), float('-inf')
    for j in range(max(0, i - WIN + 1), i + 1):
        x = vals[j]
        if x is None:
            continue
        ssum += x
        n += 1
        if x < lo:
            lo = x
        if x > hi:
            hi = x
    return (ssum / n, lo, hi, n) if n >= 3 else None


def load_data(src):
    raw = io.open(src, encoding='utf-8').read()
    key = 'const D = '
    i = raw.find(key)
    if i < 0:
        raise ValueError('未找到 const D = 数据块')
    d, _ = json.JSONDecoder().raw_decode(raw[i + len(key):].lstrip())
    if not isinstance(d, dict) or 'tracks' not in d:
        raise ValueError('const D 结构异常（缺 tracks）')
    return d


def build(d):
    L = []
    A = L.append
    asof = s(d.get('asof'))
    gen = s(d.get('generated_at'))
    tracks = d.get('tracks') or {}
    order = d.get('order') or list(tracks.keys())
    lsi = d.get('lsi') or {}
    ratios = d.get('ratios') or {}
    sig = d.get('signals') or {}

    A('# 三合一全能监测系统（沪深300 ETF + 创业板 ETF + 宏观 LSI）· 数据快照')
    A('')
    A('> 看板数据生成时间：**%s**（北京时间）　最新行情日：**%s**' % (gen, asof))
    A('> 在线看板：%s/　｜　备用：%s/' % (CF, GH))
    A('> 机器可读全量数据：%s/data.json　｜　备用：%s/data.json' % (CF, GH))
    A('> 本文件：%s/llms.txt　｜　备用：%s/llms.txt' % (CF, GH))
    A('')
    A('## 这是什么')
    A('')
    A('一个仓库、一次流水线同时跑三个模块：**① 沪深300 ETF 持仓背离监测**、'
      '**② 创业板 ETF 持仓背离监测**、**③ 美联储宏观流动性压力指数（LSI）与 20 项危机报警**；'
      '另附风格/股债比价、市场环境六件套、跨资产比价等增强卡片。')
    A('每工作日北京时间 21:17 自动跑一次，本页面是**快照**：打开网址不取数、不联网，'
      '所有数值都在生成时烤进 HTML，断网也能看。白天看到的是前一晚的快照，不是实时行情。')
    A('')
    A('## 如果你是接下这段文字的大模型')
    A('')
    A('1. **各模块数据日不同**：A 股两条主线、宏观 LSI、比价、市场环境各有自己的 `asof` / '
      '`date`，不要假设全部是同一天；本页表格里都标了日期。')
    A('2. **表里的数值就是准的**：不要自己重算，不要凭记忆补任何数字，不要拿网上历史文章的'
      '具体数字直接对比（口径与阈值是本项目单独设定的）。需要原始序列请读 `data.json`。')
    A('3. **单位**：LSI 相关多为 **bps**（1bp = 0.01 个百分点）；份额为**亿份**；'
      '市值为**亿元**；分位有的是 0~1 小数、有的是百分数，表头已注明；'
      'GLI / 准备金类为**万亿美元**。拿不准时以 `data.json` 的字段原值和 README 第四章 4.1 换算表为准。')
    A('4. **A 股配色是红涨绿跌**（净申购/正 Spread = 红，净赎回/负 = 绿），与美股相反。')
    A('5. **「—」表示本轮该字段缺失或模块降级隐藏**，不等于「数值为 0」或「没有这个指标」。'
      '任一取数模块失败只隐藏对应区块，不会拖垮整份报告。')
    A('6. 下结论时**同时引用证据与其数据日**，明确写出「不构成投资建议」；'
      '单一方向证据不足时请直接标注「证据不足」，不要下买卖结论。')
    A('')
    A('---')
    A('')
    A('## 一、模块一 & 二：双宽基 ETF 持仓背离')
    A('')
    A('核心逻辑：把头部 ETF 的市值 / 对应指数流通市值视作「持仓占比」，'
      '与指数点位做双轴对比。**指数跌而持仓占比升 = 资金逆势加仓（潜在护盘/吸筹）**；'
      '反之是资金撤离。`Spread` 是两条归一化曲线的差值，「底背离 / 顶背离」由此判定。')
    A('')
    for k in order:
        t = tracks.get(k) or {}
        sm = t.get('summary') or {}
        _name = s(sm.get('name'), k)
        _title = s(sm.get('title'), '')
        # title 通常已含 name（如「沪深300（大盘蓝筹国家队）」），避免拼成重复括号
        _head = _title if (_title and (_name in _title or _title in _name)) else (
            '%s（%s）' % (_name, _title) if _title else _name)
        A('### %s' % _head)
        A('')
        A('- **判定**：%s（level=`%s`）' % (s(sm.get('status')), s(sm.get('level'))))
        A('- **依据**：%s' % s(sm.get('reason')))
        A('- **数据日**：%s（份额披露 asof %s，尾部未披露截断天数 %s）'
          % (s(sm.get('date')), s(sm.get('shares_asof')), s(sm.get('stale_tail'))))
        A('')
        rows = [
            ('持仓占比 `hold_pct`', pctv(sm.get('hold_pct'), 4)),
            ('指数收盘 `idx_close`', num(sm.get('idx_close'))),
            ('近 20 日指数涨跌 `idx_ret20`', pctv(sm.get('idx_ret20'), 2, True)),
            ('近 20 日持仓占比变化 `hold_ret20`', pctv(sm.get('hold_ret20'), 2, True)),
            ('近 5 日份额净申购 `net5`', num(sm.get('net5')) + ' 亿份'),
            ('近 1 日份额净申购 `net1`', num(sm.get('net1')) + ' 亿份'),
            ('Spread', num(sm.get('spread'))),
            ('ETF 总市值 `etf_mv`', num(yi(sm.get('etf_mv'))) + ' 亿元'),
            ('指数流通市值 `idx_mv`', num(yi(sm.get('idx_mv'))) + ' 亿元'),
            ('持仓占比历史分位 `hold_pct_pos`', pctv(sm.get('hold_pct_pos'))),
            ('指数点位历史分位 `idx_pct_pos`', pctv(sm.get('idx_pct_pos'))),
            ('持仓占比斜率 `hold_slope`', num(sm.get('hold_slope'), 4)),
            ('指数斜率 `idx_slope`', num(sm.get('idx_slope'), 4)),
            ('样本天数 / 区间', '%s 日，%s ~ %s' % (
                s(sm.get('n')), s((sm.get('span') or ['—', '—'])[0]),
                s((sm.get('span') or ['—', '—'])[-1]))),
        ]
        L.extend(kv_table(rows, ('指标', '当前读数')))
        A('')
        share_rows = sm.get('share_rows') or []
        names = t.get('names') or {}
        if share_rows:
            codes = list((share_rows[-1].get('shares') or {}).keys())
            A('**近 5 日 ETF 份额明细**（单位：亿份；括号内为当日净申购）')
            A('')
            A('| 日期 | ' + ' | '.join('%s %s' % (c, s(names.get(c), '')) for c in codes) + ' | 合计 |')
            A('| :--- | ' + ' | '.join(['---:'] * (len(codes) + 1)) + ' |')
            for r in share_rows:
                sh = r.get('shares') or {}
                ch = r.get('chg') or {}
                cells = []
                for c in codes:
                    v = num(yi(sh.get(c)))
                    cv = yi(ch.get(c))
                    cells.append('%s (%s)' % (v, ('+' + num(cv)) if (cv or 0) > 0 else num(cv)))
                A('| %s | %s | %s |' % (s(r.get('date')), ' | '.join(cells), num(yi(r.get('total_shares')))))
            A('')
        A('')

    A('---')
    A('')
    A('## 二、模块三：宏观 LSI 压力指数与 20 项报警')
    A('')
    if not lsi:
        A('> 本轮宏观模块降级，`lsi` 数据缺失，以下各段不适用。')
        A('')
    else:
        A('- **当前状态**：%s（level=`%s`）' % (s(lsi.get('state')), s(lsi.get('level'))))
        A('- **报警**：%s / %s 项触发' % (s(lsi.get('alert_count')), s(lsi.get('total'))))
        A('- **数据日**：%s' % s(lsi.get('asof')))
        A('- **核心公式**：`LSI (bps) = (SOFR − RRP利率) + (EFFR − IORB)`；'
          '阈值严格照搬移植源脚本，未做本地调整。')
        A('')
        core = lsi.get('core') or {}
        A('### 核心指标（`lsi.core` 全量）')
        A('')
        A('> 以下为引擎内部原始值，单位换算见 README 第四章 4.1：'
          '利率/利差/通胀类为 **bps**（FRED 原始 %，×100 换算，如 392 = 3.92%）；'
          'GLI / 美联储资产 / 准备金类为**万亿美元**；'
          '`rrp_pct`、`reserve_gdp`、`reserve_assets`、`credit_roc`、`tlc`、`impulse` 为百分数；'
          '`dxy` / `dxy_ma` 为指数点位。')
        A('')
        L.extend(kv_table([('%s `%s`' % (CORE_CN.get(k, k), k), num(v, 4) if isinstance(v, float) else s(v))
                           for k, v in core.items()], ('指标', '原始值')))
        A('')
        alerts = lsi.get('alerts') or []
        if alerts:
            A('### 20 项报警全表')
            A('')
            A('| # | 类别 | 报警项 | 公式 | 结果 | 阈值 | 触发 |')
            A('| ---: | :--- | :--- | :--- | :--- | :--- | :---: |')
            for a in alerts:
                A('| %s | %s | %s | %s | %s | %s | %s |' % (
                    s(a.get('no')), s(a.get('cat')), s(a.get('name')), s(a.get('formula')),
                    s(a.get('result')), s(a.get('threshold')),
                    '**是**' if a.get('alert') else '否'))
            A('')
        loose = lsi.get('loose') or []
        if loose:
            A('### 宽松状态判定')
            A('')
            A('| 状态 | 结果 | 阈值 | 触发 |')
            A('| :--- | :--- | :--- | :---: |')
            for a in loose:
                A('| %s | %s | %s | %s |' % (
                    s(a.get('name')), s(a.get('result')), s(a.get('threshold')),
                    '**是**' if a.get('on') else '否'))
            A('')
        flow = lsi.get('flow') or {}
        if flow:
            A('### 三渠道资金流（TGA / 外国逆回购 / 国内逆回购）')
            A('')
            for it in flow.get('items') or []:
                A('- %s：%s B（十亿美元）' % (s(it.get('name')), num(it.get('delta_b'))))
            A('')
            A('- 最大抽水项：%s %s B；最大放水项：%s %s B；三渠道合计净额 **%s B**（判定阈值 %s B）'
              % (s(flow.get('drain_name')), num(flow.get('drain_b')),
                 s(flow.get('inject_name')), num(flow.get('inject_b')),
                 num(flow.get('net_b')), num(flow.get('threshold'))))
            A('- 结论：%s' % s(flow.get('net_desc')))
            A('')
        diag = lsi.get('diag') or {}
        if diag:
            A('### 三层宏观诊断（引擎原文）')
            A('')
            for key, label in (('flow', '资金动态'), ('level1', '一阶 · 宏观周期与债务周期'),
                               ('level2', '二阶 · 流动性矩阵与底层水位'),
                               ('level3', '三阶 · 微观定价与风险溢价')):
                if diag.get(key):
                    A('**%s**：%s' % (label, s(diag.get(key))))
                    A('')
        hist = lsi.get('hist') or {}
        cal = lsi.get('cal') or []
        if hist:
            A('### 历史序列（`lsi.hist`，全量在 data.json）')
            A('')
            A('区间 %s ~ %s，共 %s 个观测点。各序列末端值：'
              % (s(cal[0] if cal else None), s(cal[-1] if cal else None), len(cal)))
            A('')
            L.extend(kv_table([('`%s`' % k, num(v[-1], 4) if isinstance(v, list) and v else '—')
                               for k, v in hist.items()], ('序列', '末端值')))
            A('')
        th = lsi.get('thresholds') or {}
        if th:
            A('### 阈值表（`lsi.thresholds` 全量）')
            A('')
            L.extend(kv_table([('`%s`' % k, num(v, 4) if isinstance(v, float) else s(v))
                               for k, v in th.items()], ('阈值键', '值')))
            A('')
        excl = lsi.get('excluded') or []
        if excl:
            A('### 明确剔除、不参与计算的项')
            A('')
            for e in excl:
                A('- %s' % s(e))
            A('')

    A('---')
    A('')
    A('## 三、风格 / 股债比价（`ratios`）')
    A('')
    items = ratios.get('items') or {}
    if not items:
        A('> 本轮比价模块降级，数据缺失。')
        A('')
    else:
        A('数据日 %s，周期 `%s`。' % (s(ratios.get('asof')), s(ratios.get('period'))))
        A('')
        keys = [k for k in (ratios.get('order') or RATIO_ORDER) if k in items] or list(items.keys())
        for k in keys:
            r = items.get(k) or {}
            A('### %s' % s(r.get('title'), k))
            A('')
            A('- 公式：%s' % s(r.get('formula')))
            A('- 当前比值 **%s**，历史分位 **%s**，评级 `%s` / %s'
              % (num(r.get('cur'), 4), pctv(r.get('pct')), s(r.get('level')), s(r.get('word'))))
            A('- 判读：%s；建议：**%s**（%s）'
              % (s(r.get('label')), s(r.get('tilt')), s(r.get('advice'))))
            A('- 区间：min %s / 中位 %s / max %s；q20 %s / q80 %s；样本 %s 日（起 %s）'
              % (num(r.get('min'), 4), num(r.get('median'), 4), num(r.get('max'), 4),
                 num(r.get('q20'), 4), num(r.get('q80'), 4), s(r.get('n')), s(r.get('start'))))
            A('- 变动：近 20 日 %s / 近 60 日 %s / 近 250 日 %s'
              % (pctv(r.get('chg20'), 2, True), pctv(r.get('chg60'), 2, True),
                 pctv(r.get('chg250'), 2, True)))
            A('')

    A('---')
    A('')
    A('## 四、市场环境六件套与跨资产比价（`signals`）')
    A('')
    if not sig:
        A('> 本轮市场环境模块降级，`signals` 数据缺失。')
        A('')
    else:
        A('更新时间：%s。六项**各自独立容错**，任一失败只让对应面板消失。' % s(sig.get('updated')))
        A('')
        val = sig.get('valuation') or {}
        if val.get('data'):
            A('### ① 估值')
            A('')
            A('> `pe_pct` 是历史分位（0~1，越小越便宜）；'
              '`pe_over_history` 是其互补值，仅透传备查，**不要混用**。')
            A('')
            A('| 指数 | 日期 | PE(TTM) | PB | PE 分位 | PB 分位 | ROE | 股息率 | PEG | 评级 |')
            A('| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |')
            for v in val['data']:
                A('| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (
                    s(v.get('name')), s(v.get('date')), num(v.get('pe')), num(v.get('pb'), 4),
                    num(v.get('pe_pct'), 4), num(v.get('pb_pct'), 4),
                    pctv((v.get('roe') or 0) * 100), pctv((v.get('dividend_yield') or 0) * 100),
                    num(v.get('peg'), 4), s(v.get('level'))))
            A('')
        liq = sig.get('liquidity') or {}
        if liq.get('latest'):
            A('### ② 境内资金面（DR001 / SHIBOR 隔夜 O/N / FR001，单位 % 年化）')
            A('')
            A('> 派生量为 **bp**（1bp = 0.01 个百分点）。⑨ 面板口径自 **2026-11-10** 起：'
              '主线由 `DR007` **换锚为 `DR001`**（2026-11-02 后央行调控目标），DR007 退居辅助；'
              '灰虚线全名为「**SHIBOR 隔夜 O/N**」，不可简写成「隔夜」。')
            A('')
            A('> **20 日中枢 / 波动区间全自动**：`CENTER` = `dr001` 末 20 行有值点均值，'
              '`LO~HI` = 同窗口 min~max，随每日数据滚动；**不硬编码政策利率**，'
              '央行调息后看板零改动自动跟随。下表按页面 `winStat()` 同一算法自算，'
              '让 AI 也能读到这个「浏览器现算、不落数据文件」的派生值。')
            A('')
            st = cn_liq_center(liq)
            if st:
                c, lo, hi, n = st
                lt = liq.get('latest') or {}
                cur = lt.get('dr001')
                dev = ((float(cur) - c) * 100
                       if isinstance(cur, (int, float)) and not isinstance(cur, bool) else None)
                L.extend(kv_table([
                    ('20 日中枢 `CENTER`（%）', num(c, 4)),
                    ('同窗口波动区间 `LO~HI`（%）', '%s ~ %s' % (num(lo, 4), num(hi, 4))),
                    ('窗口内有值交易日 `n`', str(n)),
                    ('DR001 距中枢（bp）', ('%+.1f' % dev) if dev is not None else '—'),
                ], ('⑨ 面板派生项（本地自算）', '值')))
                A('')
            A('> **两个 bp 基准不同，禁止混读**：「距中枢」= `DR001 − CENTER`（纵向，今天 vs 近期常态）；'
              '「FR001 分层溢价」= `FR001 − DR001`（横向，全市场 vs 银行间）。'
              '副图蓝虚线 `±round(dm/2)` 是**自适应辅助刻度、不是告警阈值**，越过不触发任何动作；'
              '沪深300 归一紫线用于对照「利率松紧 vs 指数涨跌」，不可删。')
            A('')
            A('> DR001 历史仅约 1 个月（上游中国货币网回购定盘只回最近约 21 个交易日），'
              '图上以「DR001 数据起点」竖虚线标注，**不是数据缺失**。')
            A('')
            L.extend(kv_table([('`%s`' % k, num(v, 4) if isinstance(v, float) else s(v))
                               for k, v in (liq.get('latest') or {}).items()],
                              ('字段', '最新值')))
            A('')
            if liq.get('derived'):
                A('> `derived` 里 `dr007_ma20` / `dr007_vs_ma20_bp` 等仍以 DR007 为主，'
                  '是给 ⑨ 第 4 张 DR007 卡片用的，**不是「没跟着换锚」**。')
                A('')
                L.extend(kv_table([('`%s`' % k, num(v, 4) if isinstance(v, float) else s(v))
                                   for k, v in liq['derived'].items()], ('派生字段', '值 (bp)')))
                A('')
        prem = sig.get('premium') or {}
        if prem.get('data'):
            A('### ③ ETF 折溢价')
            A('')
            A('> 折溢价 = (市价 − 净值) / 净值 × 100；`stale=true` 表示价格与净值日期不同，此时只反映相对差异。')
            A('')
            A('| 代码 | 名称 | 市价 | 净值 | 折溢价 | 价格日 | 净值日 | 错日 |')
            A('| :--- | :--- | ---: | ---: | ---: | :--- | :--- | :---: |')
            for v in prem['data']:
                A('| %s | %s | %s | %s | %s | %s | %s | %s |' % (
                    s(v.get('code')), s(v.get('name')), num(v.get('price'), 4),
                    num(v.get('nav'), 4), pctv(v.get('premium_pct'), 4, True),
                    s(v.get('price_date')), s(v.get('nav_date')),
                    '是' if v.get('stale') else '否'))
            A('')
        br = sig.get('breadth') or {}
        if br.get('today'):
            t = br['today']
            A('### ④ 市场宽度（涨跌家数）')
            A('')
            L.extend(kv_table([
                ('日期', s(t.get('date'))), ('上涨 / 下跌 / 平盘', '%s / %s / %s' % (
                    s(t.get('up')), s(t.get('down')), s(t.get('flat')))),
                ('总数 / 上涨占比', '%s / %s' % (s(t.get('total')), pctv(t.get('up_pct')))),
                ('涨停 / 跌停 / 最高连板', '%s / %s / %s' % (
                    s(t.get('limit_up')), s(t.get('limit_down')), s(t.get('max_streak')))),
                ('连板分布', s(t.get('streak_dist'))),
                ('是否当日实时', '是' if t.get('is_today') else '否（上游忽略 date 参数）'),
            ], ('项目', '数值')))
            A('')
            if br.get('history'):
                A('近几日：' + '；'.join('%s 涨 %s / 跌 %s' % (
                    s(x.get('date')), s(x.get('up')), s(x.get('down')))
                    for x in br['history']))
                A('')
        rates = sig.get('rates') or {}
        if rates.get('latest'):
            A('### ⑤ 国债收益率与期限结构（%）')
            A('')
            A('> 利差字段为百分点（×100 即 bp）；派生量为 bp。')
            A('')
            L.extend(kv_table([('`%s`' % k, num(v, 4) if isinstance(v, float) else s(v))
                               for k, v in rates['latest'].items()], ('字段', '最新值')))
            A('')
            if rates.get('derived'):
                L.extend(kv_table([('`%s`' % k, num(v, 4) if isinstance(v, float) else s(v))
                                   for k, v in rates['derived'].items()], ('派生字段', '值')))
                A('')
        mr = sig.get('macro_ratios') or {}
        if mr:
            A('### ⑥ 跨资产比价')
            A('')
            A('数据日 %s；黄金收盘 %s，KOSPI %s；数据源 `%s`。'
              % (s(mr.get('asof')), num(mr.get('gold_close')), num(mr.get('kospi')),
                 s(mr.get('source'))))
            A('')
            A('| 比价 | 当前值 | 近 20 日变动 | 250 日分位 | 250 日 min / max | 数据日 | 样本 |')
            A('| :--- | ---: | ---: | ---: | :--- | :--- | ---: |')
            for k in ('gold_silver', 'gold_oil', 'copper_gold', 'kospi_gold'):
                v = mr.get(k) or {}
                if not v:
                    continue
                A('| %s | %s | %s | %s | %s / %s | %s | %s |' % (
                    k, num(v.get('value'), 4), pctv(v.get('chg20_pct'), 2, True),
                    pctv(v.get('pct250')), num(v.get('min250'), 4), num(v.get('max250'), 4),
                    s(v.get('asof')), s(v.get('n'))))
            A('')
        if sig.get('errors'):
            A('### 本轮降级记录')
            A('')
            A('```')
            A(s(sig.get('errors')))
            A('```')
            A('')

    A('---')
    A('')
    A('## 数据滞后与降级提示')
    A('')
    A('- 各模块发布节奏不同：ETF 份额有 T+1~T+2 披露滞后，'
      '宏观 FRED 序列分日频/周频/月频/季频，比价为周频。'
      '**「—」或整段缺失 = 本轮该模块降级**，不是数值为 0。')
    A('- 打开看板**不会重新计算**，内容每天 21:17 更新一次；'
      '想立刻刷新请到仓库 Actions 手动 Run workflow。')
    A('- 已明确剔除、不参与计算的 TradingView 私有数据项见上文「明确剔除」段。')
    A('')
    A('## 数据来源')
    A('')
    A('| 数据 | 来源 |')
    A('| :--- | :--- |')
    A('| 宏观 LSI 20+ 项序列 | 美联储 FRED 官方 API（JSON 挂自动降级 CSV），需 `FRED_API_KEY` |')
    A('| 上交所 ETF 份额 / 净值 / 交易日历 | 官方披露，经自建 `a-stock-api` Worker `/api/etf-shares`、`/api/fund-nav`、`/api/trade-calendar` |')
    A('| 深交所 ETF 份额 | 深交所官方 xlsx 直连解析 |')
    A('| ETF 单位净值兜底 | 天天基金 pingzhongdata（东财） |')
    A('| 市场环境六件套 / 跨资产比价 | 自建 `a-stock-api` Worker 各端点 |')
    A('| 滞后份额快照 | 腾讯自选股 Node CLI（`westock-data/`） |')
    A('')
    A('> 两条链路完全独立：宏观走 FRED（境外），A 股走自建 Worker（境内），互不影响。')
    A('')
    A('## 名词速查')
    A('')
    A('| 名词 | 含义 |')
    A('| :--- | :--- |')
    A('| LSI | 流动性压力指数，`(SOFR−RRP)+(EFFR−IORB)`，单位 bps，值越大美元体系内部管道越紧 |')
    A('| GLI | 全球流动性指标（美联储净流动性口径），万亿美元 |')
    A('| RRP | 隔夜逆回购余额，常被视作美元体系的「缓冲垫」，枯竭后财政抽水会直接消耗准备金 |')
    A('| SOFR / EFFR / IORB | 担保隔夜融资利率 / 有效联邦基金利率 / 准备金余额利率 |')
    A('| DFII10 / T10YIE | 10 年期实际利率 / 10 年期盈亏平衡通胀预期 |')
    A('| DTWEXBGS | 广义美元指数，上穿 50 日均线视为「强美元潮汐」 |')
    A('| 持仓占比 | 头部 ETF 市值 ÷ 对应指数流通市值，本项目自建口径 |')
    A('| Spread | 持仓占比与指数两条归一化曲线的差值，用于识别背离 |')
    A('| 分位 | 当前值在历史样本中的排名位置；90% 表示只有 10% 的时间更极端 |')
    A('| 折溢价 | (市价−净值)/净值×100，正值溢价、负值折价 |')
    A('')
    A('---')
    A('')
    A('> 本文件由 `make_llm_summary.py` 从看板 HTML 内嵌 `const D` 自动生成，每日随看板一起发布；'
      '**不要手改**。全量原始序列见同目录 `data.json`。内容仅供研究参考，**不构成投资建议**。')
    A('')
    return '\n'.join(L)


def main():
    args = sys.argv[1:]

    def opt(flag, default=None):
        return args[args.index(flag) + 1] if flag in args and args.index(flag) + 1 < len(args) else default

    check = '--check' in args
    src = opt('--src')
    out = opt('--out', HERE)

    if src is None:
        # 线上由 daily_run.py 以 cwd=BASE 调用，HERE 与 cwd 一致；
        # 这里仍按「HERE 优先、cwd 兜底」找，兼容在别处手动运行脚本的场景。
        for base in (HERE, os.getcwd()):
            for cand in ('etf_lsi_dashboard.html', 'index.html'):
                p = os.path.join(base, cand)
                if os.path.exists(p):
                    src = p
                    break
            if src:
                break
    if not src or not os.path.exists(src):
        print('::warning::[make_llm_summary] 未找到看板 HTML（etf_lsi_dashboard.html / index.html），'
              '跳过 AI 文档生成；不写空文件，不影响主报告。')
        return 0
    try:
        d = load_data(src)
    except Exception as e:
        print('::warning::[make_llm_summary] 解析 const D 失败（%s: %s），'
              '跳过 AI 文档生成；不写空文件，不影响主报告。' % (type(e).__name__, e))
        return 0

    try:
        md = build(d)
    except Exception as e:
        print('::warning::[make_llm_summary] 生成 llms.txt 失败（%s: %s），'
              '跳过 AI 文档生成；不写空文件，不影响主报告。' % (type(e).__name__, e))
        return 0

    if check:
        print(md)
        print('\n[--check] llms.txt %d bytes, data.json 将含 %d 个顶层键；未写文件。'
              % (len(md.encode('utf-8')), len(d)))
        return 0

    try:
        if not os.path.isdir(out):
            os.makedirs(out)
        with io.open(os.path.join(out, 'llms.txt'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(md)
        with io.open(os.path.join(out, 'data.json'), 'w', encoding='utf-8', newline='\n') as f:
            f.write(json.dumps(d, ensure_ascii=False, separators=(',', ':')))
    except Exception as e:
        print('::warning::[make_llm_summary] 写文件失败（%s: %s）；不影响主报告。'
              % (type(e).__name__, e))
        return 0

    print('llms.txt   %8d bytes' % len(md.encode('utf-8')))
    print('data.json  %8d bytes (顶层键: %s)' % (
        os.path.getsize(os.path.join(out, 'data.json')), ', '.join(d.keys())))
    return 0


if __name__ == '__main__':
    sys.exit(main())

# -*- coding: utf-8 -*-
"""
三合一汇总日报邮件

标题：[A股双宽基主力 & 宏观LSI日报] YYYY-MM-DD | 沪深300: <状态> | 创业板: <状态> | 宏观: <状态> (LSI: XX.X BP)

正文：① 沪深300 诊断 + 份额明细　② 创业板 诊断 + 份额明细
     ③ 三大风格/股债性价比百分位　④ LSI 核心面板 + 20项报警明细表 + 四维诊断
     ⑤ 市场环境四件套（估值 / 境内资金面 / 折溢价 / 市场宽度）　⑥ 内嵌监测图

凭证优先级：环境变量 ETF_SMTP_USER / ETF_SMTP_PASS / ETF_MAIL_TO（GitHub Actions Secrets）
            > email_config.json
未配置则自动生成邮件正文到本地 mail_preview.html，不发送（便于本地试跑）。
"""
import json, os, re, sys, socket, smtplib, mimetypes
from email.message import EmailMessage

import common
from config import ORDER, UP_COLOR, DOWN_COLOR

BASE = common.BASE
PNG = os.path.join(BASE, 'etf_lsi_monitor_latest.png')
PREVIEW = os.path.join(BASE, 'mail_preview.html')


def load(name, default=None):
    p = os.path.join(BASE, name)
    if not os.path.exists(p):
        return default
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def esc(s):
    return (str(s).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def fmt(v, n=2):
    return '—' if v is None else ('%.*f' % (n, v))


def sgn2(v, n=2):
    if v is None:
        return '—'
    return ('+' if v >= 0 else '') + ('%.*f' % (n, v))


def d100(v):
    """bps -> % 的空值安全转换。

    20 个 FRED 序列中任一偶发超时就会返回 None，
    直接写 `c['sofr'] / 100` 会抛 TypeError 让整个发信脚本崩掉（邮件发不出去）。
    """
    return None if v is None else v / 100.0


CLR_UP, CLR_DOWN = UP_COLOR, DOWN_COLOR


def col(v, pos_up=True):
    if v is None:
        return '#333'
    if pos_up:
        return CLR_UP if v >= 0 else CLR_DOWN
    return CLR_DOWN if v >= 0 else CLR_UP


def track_block(S, title_idx):
    rows = S.get('share_rows') or []
    names = S.get('etf_names') or {}
    syms = list(names.keys())
    h = '<div style="margin:0 0 18px"><h3 style="font-size:15px;margin:0 0 8px">%s %s · %s</h3>' % (
        title_idx, esc(S['title']), esc(S['status']))
    h += '<div style="background:#F4F6F8;border-left:4px solid #4C9AFF;padding:10px 13px;border-radius:6px;font-size:13px;margin-bottom:10px">%s</div>' % esc(S['reason'])
    h += '<table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse;font-size:12px;border-color:#DDD;width:100%">'
    h += '<tr style="background:#EFEFEF"><th>指标</th><th>数值</th><th>指标</th><th>数值</th></tr>'
    h += ('<tr><td>持仓占比</td><td><b>%s%%</b></td><td>%s 收盘</td><td><b>%s</b></td></tr>'
          % (fmt(S['hold_pct'], 4), esc(S['index_name']), fmt(S['idx_close'], 2)))
    h += ('<tr><td>开口差 Spread</td><td style="color:%s"><b>%s</b></td><td>阈值</td><td>±25</td></tr>'
          % (col(S['spread']), sgn2(S['spread'], 1)))
    h += ('<tr><td>近20日占比斜率</td><td>%s</td><td>近20日指数斜率</td><td>%s</td></tr>'
          % (sgn2(S['hold_slope'], 2), sgn2(S['idx_slope'], 2)))
    h += ('<tr><td>近5日份额净变化</td><td style="color:%s"><b>%s 亿份</b></td><td>净变动比例</td><td style="color:%s">%s%%</td></tr>'
          % (col(S['net5']), sgn2(S['net5'], 2), col(S['net5_ratio']), sgn2(S['net5_ratio'], 2)))
    h += ('<tr><td>头部ETF合计市值</td><td>%s 亿元</td><td>%s流通市值</td><td>%s 亿元</td></tr>'
          % (fmt(S['etf_mv'] / 1e8, 1), esc(S['index_name']), fmt(S['idx_mv'] / 1e8, 1)))
    h += '</table>'
    if rows:
        h += '<div style="margin-top:10px;font-size:12.5px;font-weight:600">%s（亿份，括号为当日增减）</div>' % esc(S['labels']['share_tbl'])
        h += '<table border="1" cellspacing="0" cellpadding="5" style="border-collapse:collapse;font-size:11.5px;border-color:#DDD;width:100%;margin-top:5px">'
        h += '<tr style="background:#EFEFEF"><th>日期</th>' + ''.join('<th>%s</th>' % esc(names[s]) for s in syms) + '<th>四只合计</th></tr>'
        for r in rows:
            h += '<tr><td>%s</td>' % r['date']
            for s in syms:
                v, c = r['shares'].get(s), r['chg'].get(s)
                cc = '#333'
                if c is not None:
                    cc = CLR_UP if c >= 0 else CLR_DOWN
                h += '<td>%s <span style="color:%s">%s</span></td>' % (
                    fmt(v / 1e8, 3) if v else '—', cc,
                    (('+' if c >= 0 else '') + fmt(c / 1e8, 3)) if c is not None else '—')
            h += '<td><b>%s</b></td></tr>' % (fmt(r['total_shares'] / 1e8, 2) if r.get('total_shares') else '—')
        h += '</table>'
    if S.get('stale_tail'):
        h += '<div style="color:#B26A00;font-size:11.5px;margin-top:6px">注：份额披露 T+1~T+2 滞后，已剔除尾部 %d 个未披露交易日（份额口径截至 %s）。</div>' % (
            S['stale_tail'], esc(S.get('shares_asof') or '—'))
    h += '</div>'
    return h


def ratio_block(R):
    if not R or not R.get('items'):
        return ''
    h = '<div style="margin:0 0 18px"><h3 style="font-size:15px;margin:0 0 8px">③ 三大风格轮动 &amp; 股债性价比 · 历史百分位（含 20 / 80 分位门槛比值与距离）</h3>'
    h += '<table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse;font-size:12px;border-color:#DDD;width:100%">'
    h += ('<tr style="background:#EFEFEF"><th>比价</th><th>公式（分子 ÷ 分母）</th><th>当前比值</th>'
          '<th>20 分位比值<br><span style="font-weight:400;font-size:10.5px">（进绿区门槛）</span></th>'
          '<th>80 分位比值<br><span style="font-weight:400;font-size:10.5px">（进红区门槛）</span></th>'
          '<th>全周期分位</th><th>距 20 分位</th><th>距 80 分位</th><th>结论</th><th>配置倾向</th></tr>')
    for k in R.get('order', []):
        it = R['items'].get(k)
        if not it:
            continue
        c = CLR_UP if it['level'] == 'high' else (CLR_DOWN if it['level'] == 'low' else '#333')
        cur = it.get('cur') or 0
        q20, q80 = it.get('q20'), it.get('q80')
        # 距 20/80 分位：还需上涨(+)或下跌(-)百分之多少
        d20 = (q20 / cur - 1) * 100 if cur else None
        d80 = (q80 / cur - 1) * 100 if cur else None
        c20 = CLR_DOWN if (d20 is not None and d20 < 0) else '#666'
        c80 = CLR_UP if (d80 is not None and d80 > 0) else '#666'
        h += ('<tr><td>%s</td><td style="font-size:11px">%s</td><td><b>%s</b></td>'
              '<td style="color:%s"><b>%s</b></td><td style="color:%s"><b>%s</b></td>'
              '<td style="color:%s"><b>%.1f%%（%s）</b></td>'
              '<td style="color:%s">%s</td><td style="color:%s">%s</td>'
              '<td>%s</td><td><b>%s</b></td></tr>'
              % (esc(it['title']), esc(it['formula']), fmt(cur, 4),
                 CLR_DOWN, fmt(q20, 4), CLR_UP, fmt(q80, 4),
                 c, it['pct'], esc(it['word']),
                 c20, sgn2(d20, 1) + '%', c80, sgn2(d80, 1) + '%',
                 esc(it['label']), esc(it['tilt'])))
    h += '</table>'
    # 逐项「离门槛还有多远」的文字说明
    h += '<div style="font-size:12px;margin-top:8px;font-weight:600">离 20 / 80 分位门槛还有多远：</div>'
    h += '<ul style="font-size:11.8px;color:#444;margin:5px 0 0 18px;line-height:1.85">'
    for k in R.get('order', []):
        it = R['items'].get(k)
        if not it:
            continue
        cur = it.get('cur') or 0
        q20, q80 = it.get('q20'), it.get('q80')
        d20 = (q20 / cur - 1) * 100 if cur else None
        d80 = (q80 / cur - 1) * 100 if cur else None
        h += ('<li><b>%s</b>（%s ÷ %s）：当前 %s　→　20 分位 %s（需 <b style="color:%s">%s</b>）'
              '　｜　80 分位 %s（需 <b style="color:%s">%s</b>）　覆盖 %s 周（约 %s 年）</li>'
              % (esc(it['title']), esc(it.get('num_short', '')), esc(it.get('den_short', '')),
                 fmt(cur, 4), fmt(q20, 4), CLR_DOWN, sgn2(d20, 1) + '%',
                 fmt(q80, 4), CLR_UP, sgn2(d80, 1) + '%',
                 it.get('n', '—'), it.get('years', '—')))
    h += '</ul>'
    h += '<div style="font-size:11.5px;color:#666;margin-top:6px">口径：周K全周期（%s 起分段拼接）。比值上行 = 防御占优。' \
         '红区（分位≥80）说明分子资产已大幅跑赢、相对变贵，操作上应卖出分子、买入分母（均值回归）；' \
         '绿区（分位≤20）则相反。上表「距 20/80 分位」为当前比值到达该门槛还需变动的百分比。</div>' % esc(str(R.get('asof', '')))
    h += '</div>'
    return h


def lsi_block(L):
    if not L:
        return ''
    c = L['core']
    h = '<div style="margin:0 0 18px"><h3 style="font-size:15px;margin:0 0 8px">④ 美元宏观 LSI 压力指数 &amp; 20 项背景报警</h3>'
    # 核心面板
    h += '<table border="1" cellspacing="0" cellpadding="6" style="border-collapse:collapse;font-size:12px;border-color:#DDD;width:100%">'
    h += '<tr style="background:#EFEFEF"><th>指标</th><th>数值</th><th>指标</th><th>数值</th></tr>'
    _g = lambda k: (c.get(k) if c.get(k) is not None else None)
    _lsi = c.get('lsi')
    lsi_col = '#8B1A1A' if (_lsi is not None and _lsi >= 50) else (CLR_UP if (_lsi is not None and _lsi >= 20) else (CLR_DOWN if (_lsi is not None and _lsi < 0) else '#333'))
    h += '<tr><td><b>LSI 压力指数</b></td><td style="color:%s"><b>%s bp</b></td><td>宏观状态</td><td><b>%s</b></td></tr>' % (
        lsi_col, fmt(c['lsi'], 1), esc(L['state']))
    h += '<tr><td>SOFR / RRP 利率</td><td>%s%% / %s%%</td><td>EFFR / IORB</td><td>%s%% / %s%%</td></tr>' % (
        fmt(d100(c.get('sofr')), 2), fmt(d100(c.get('rrp_rate')), 2), fmt(d100(c.get('effr')), 2), fmt(d100(c.get('iorb')), 2))
    h += '<tr><td>GLI 净流动性</td><td><b>%s T</b></td><td>GLI 20日变化</td><td style="color:%s">%s%%</td></tr>' % (
        fmt(c['gli'], 3), col(c['tlc'], False), sgn2(c['tlc'], 2))
    h += '<tr><td>RRP 余额 / 峰值占比</td><td style="color:%s">%s T / %s%%</td><td>流动性冲量</td><td style="color:%s">%s%%</td></tr>' % (
        CLR_UP if (c.get('rrp_pct') is not None and c['rrp_pct'] < 5) else CLR_DOWN,
        fmt(c.get('rrp_T'), 3), fmt(c.get('rrp_pct'), 1),
        col(c['impulse']), sgn2(c['impulse'], 2))
    h += '<tr><td>10Y实际利率 DFII10</td><td>%s%%</td><td>信用利差 OAS</td><td>%s%%（动量 %s%%）</td></tr>' % (
        fmt(d100(c.get('dfii10')), 2), fmt(d100(c.get('credit')), 2), sgn2(c.get('credit_roc'), 2))
    h += '<tr><td>10Y−2Y 利差</td><td>%s bp</td><td>T10YIE / CPI YoY</td><td>%s%% / %s%%</td></tr>' % (
        sgn2(c.get('yield_spread'), 1), fmt(d100(c.get('t10yie')), 2), fmt(d100(c.get('cpi_yoy')), 2))
    h += '<tr><td>银行准备金</td><td>%s T（占GDP %s%% / 占银行资产 %s%%）</td><td>广义美元指数</td><td>%s（MA50 %s）</td></tr>' % (
        fmt(c['wrb_T'], 3), fmt(c['reserve_gdp'], 2), fmt(c['reserve_assets'], 2),
        fmt(c['dxy'], 2), fmt(c['dxy_ma'], 2))
    h += '</table>'

    # V57 资金流向
    f = L.get('flow') or {}
    if f:
        h += '<div style="margin-top:10px;font-size:12.5px"><b>V57 资金流向雷达（近10观测日）：</b>%s ｜ %s ｜ %s</div>' % (
            esc(f.get('drain_str', '')), esc(f.get('inject_str', '')), esc(f.get('net_desc', '')))

    # 20 项报警表
    h += '<div style="margin-top:12px;font-size:12.5px;font-weight:600">20 项背景颜色报警 · 全量明细（原始数据 / 公式 / 结果 / 阈值 / 状态）</div>'
    h += '<table border="1" cellspacing="0" cellpadding="5" style="border-collapse:collapse;font-size:11px;border-color:#DDD;width:100%;margin-top:5px">'
    h += '<tr style="background:#EFEFEF"><th>#</th><th>分类</th><th>报警项</th><th>原始数据</th><th>计算公式</th><th>当前结果</th><th>报警阈值</th><th>状态</th></tr>'
    for a in L['alerts']:
        cc = '#E8453C' if a['alert'] else '#1FB37A'
        st = '🚨 报警（已触发）' if a['alert'] else '✅ 正常（未触发）'
        h += ('<tr><td>%d</td><td>%s</td><td>%s</td><td style="font-size:10.5px">%s</td>'
              '<td style="font-size:10.5px;color:#555">%s</td><td style="color:%s"><b>%s</b></td>'
              '<td style="font-size:10.5px;color:#555">%s</td><td style="color:%s"><b>%s</b></td></tr>'
              % (a['no'], esc(a['cat']), esc(a['name']), esc(a['raw']), esc(a['formula']),
                 cc, esc(a['result']), esc(a['threshold']), cc, st))
    h += '</table>'

    # 宽松项
    if L.get('loose'):
        h += '<div style="margin-top:10px;font-size:12.5px"><b>正面宽松状态指示：</b>'
        h += '　'.join('%s <span style="color:%s">%s</span>' % (
            esc(x['name']), '#1FB37A' if x['on'] else '#999', '成立' if x['on'] else '未成立')
            for x in L['loose'])
        h += '</div>'

    # 四维诊断
    d = L.get('diag') or {}
    for key, ttl in (('flow', '🔍 资金动态'), ('level1', '【一阶】宏观周期与债务周期'),
                     ('level2', '【二阶】流动性矩阵与底层水位'), ('level3', '【三阶】微观定价与风险溢价')):
        if d.get(key):
            h += '<div style="background:#F4F6F8;border-left:4px solid #22D3EE;padding:9px 12px;border-radius:6px;font-size:12px;margin-top:8px;line-height:1.85"><b>%s</b><br>%s</div>' % (
                ttl, esc(d[key]))
    h += '<div style="font-size:11px;color:#777;margin-top:8px">已剔除的 TradingView 私有序列：' + '；'.join(esc(x) for x in L.get('excluded', [])) + '</div>'
    h += '</div>'
    return h


def _bar(p, color, w=54):
    """0~1 的百分位画成一条小进度条（邮件客户端只认嵌套 inline-block + 百分比宽度）"""
    if p is None:
        return ''
    v = max(0.0, min(1.0, float(p))) * 100
    return ('<span style="display:inline-block;width:%dpx;height:6px;background:#E8EAED;'
            'border-radius:3px;vertical-align:middle;margin-right:5px">'
            '<span style="display:inline-block;width:%.0f%%;height:6px;background:%s;'
            'border-radius:3px;vertical-align:top"></span></span>' % (w, v, color))


def _pct_word(p):
    """分位 -> (文字, 颜色)。红=贵、绿=便宜，沿用 A 股红涨绿跌的直觉。"""
    if p is None:
        return '—', '#333'
    if p >= 0.80:
        return '高估区', CLR_UP
    if p >= 0.60:
        return '偏贵', '#C2410C'
    if p > 0.40:
        return '中性', '#333'
    if p > 0.20:
        return '偏便宜', '#0E9F6E'
    return '低估区', CLR_DOWN


def signals_block(S):
    """⑤ 市场环境四件套：指数估值 / 境内资金面 / ETF 折溢价 / 市场宽度。

    四块彼此独立抓取，任何一块缺失就整块跳过（不留空表头）。
    与看板 ⑨⑩⑪⑫ 面板同源，字段口径见 a-stock-api README §2。
    """
    if not S:
        return ''
    V, Q, P, BR = (S.get('valuation'), S.get('liquidity'),
                   S.get('premium'), S.get('breadth'))
    RT = S.get('rates')
    if not any((V, Q, P, BR, RT)):
        return ''

    TBD = ('border="1" cellspacing="0" cellpadding="6" '
           'style="border-collapse:collapse;font-size:12px;border-color:#DDD;width:100%;margin-top:6px"')
    TH = '<tr style="background:#EFEFEF">'
    bp = lambda v: '—' if v is None else ('%+.1f' % v) + ' bp'
    bp_col = lambda v: '#333' if v is None else (CLR_UP if v > 0 else (CLR_DOWN if v < 0 else '#333'))

    h = ('<div style="margin:0 0 18px"><h3 style="font-size:15px;margin:0 0 8px">'
         '⑤ 市场环境监测 · 指数估值 / 境内资金面 / 国债曲线 / ETF 折溢价 / 市场宽度</h3>')
    h += ('<div style="color:#666;font-size:11.5px;margin-bottom:3px">更新 %s　｜　'
          '数据源：蛋卷基金（估值分位）· 中国货币网（SHIBOR / 银行间回购定盘）· '
          '东财国债到期收益率（曲线）· 腾讯行情 + 东财净值（折溢价）· '
          '东财涨停/跌停池（宽度）</div>'
          % esc(S.get('updated') or '—'))

    notes = []          # 末尾的「一句话综合提示」

    # ── 5.1 规模指数估值 ────────────────────────────────────
    rows = (V or {}).get('data') or []
    if rows:
        h += '<div style="font-size:12.5px;font-weight:600;margin-top:10px">5.1 规模指数估值 · PE / PB 历史分位</div>'
        h += '<table %s>' % TBD
        h += (TH + '<th>指数</th><th>PE</th><th>PE 历史分位</th><th>PB</th>'
              '<th>PB 历史分位</th><th>ROE</th><th>股息率</th><th>估值状态</th></tr>')
        for r in rows:
            pp, bpv = r.get('pe_pct'), r.get('pb_pct')
            wd, wc = _pct_word(pp)
            h += ('<tr><td><b>%s</b><br><span style="color:#888;font-size:10.5px">%s</span></td>'
                  '<td><b>%s</b></td>'
                  '<td>%s<b style="color:%s">%s</b></td>'
                  '<td>%s</td>'
                  '<td>%s<b>%s</b></td>'
                  '<td>%s</td><td>%s</td>'
                  '<td style="color:%s"><b>%s</b></td></tr>'
                  % (esc(r.get('name') or r.get('code') or '—'), esc(r.get('code') or ''),
                     fmt(r.get('pe'), 2),
                     _bar(pp, wc), wc, '—' if pp is None else '%.1f%%' % (pp * 100),
                     fmt(r.get('pb'), 2),
                     _bar(bpv, '#8A93A3'), '—' if bpv is None else '%.1f%%' % (bpv * 100),
                     '—' if r.get('roe') is None else '%.2f%%' % (r['roe'] * 100),
                     '—' if r.get('dividend_yield') is None else '%.2f%%' % (r['dividend_yield'] * 100),
                     wc, wd))
        h += '</table>'
        seg = []
        for r in rows:
            pp = r.get('pe_pct')
            if pp is not None:
                seg.append('%s PE 分位 <b>%.1f%%</b>（%s）' % (
                    esc(r.get('name') or r.get('code')), pp * 100, _pct_word(pp)[0]))
        if seg:
            notes.append('估值：' + '，'.join(seg) + '。分位 &gt;80% 为高估区、&lt;20% 为低估区，中间视为合理。')
        h += ('<div style="font-size:11px;color:#777;margin-top:4px">'
              'PE/PB 分位为「当前值在自身历史中的位置」，0% = 史上最便宜、100% = 史上最贵；'
              'ROE 与股息率为上游原始值（小数已换算成 %）。</div>')

    # ── 5.2 境内资金面 ──────────────────────────────────────
    if Q:
        lt = Q.get('latest') or {}
        dv = Q.get('derived') or {}
        h += '<div style="font-size:12.5px;font-weight:600;margin-top:12px">5.2 境内资金面 · 银行间资金价格（年化 %）</div>'
        h += '<table %s>' % TBD
        h += TH + '<th>指标</th><th>数值</th><th>指标</th><th>数值</th></tr>'
        h += ('<tr><td>DR007 · 7 天回购定盘</td><td style="color:#C2410C"><b>%s%%</b></td>'
              '<td>20 日均 / 偏离</td><td>%s%%　<span style="color:%s">%s</span></td></tr>'
              % (fmt(lt.get('dr007'), 3), fmt(dv.get('dr007_ma20'), 3),
                 bp_col(dv.get('dr007_vs_ma20_bp')), bp(dv.get('dr007_vs_ma20_bp'))))
        h += ('<tr><td>DR001 · 隔夜</td><td><b>%s%%</b></td>'
              '<td>FR001 · 银行间隔夜</td><td>%s%%</td></tr>'
              % (fmt(lt.get('dr001'), 3), fmt(lt.get('fr001'), 3)))
        h += ('<tr><td>SHIBOR 3M · 中期资金成本</td><td style="color:#2563EB"><b>%s%%</b></td>'
              '<td>20 日变化</td><td style="color:%s">%s</td></tr>'
              % (fmt(lt.get('shibor_3m'), 3),
                 bp_col(dv.get('shibor_3m_chg_20d_bp')), bp(dv.get('shibor_3m_chg_20d_bp'))))
        h += ('<tr><td>SHIBOR 1Y</td><td>%s%%</td>'
              '<td>期限利差 3M − 隔夜</td><td style="color:%s">%s</td></tr>'
              % (fmt(lt.get('shibor_1y'), 3),
                 bp_col(dv.get('term_spread_3m_on_bp')), bp(dv.get('term_spread_3m_on_bp'))))
        h += ('<tr><td>DR007 近 5 日变化</td><td style="color:%s">%s</td>'
              '<td>数据日期</td><td>%s</td></tr>'
              % (bp_col(dv.get('dr007_chg_5d_bp')), bp(dv.get('dr007_chg_5d_bp')),
                 esc(lt.get('date') or '—')))
        h += '</table>'
        if lt.get('dr007') is not None:
            d5 = dv.get('dr007_chg_5d_bp')
            tone = '基本持平'
            if d5 is not None:
                tone = ('明显收紧' if d5 >= 10 else '小幅收紧' if d5 > 2
                        else '明显转松' if d5 <= -10 else '小幅转松' if d5 < -2 else '基本持平')
            notes.append('资金面：DR007 报 %.3f%%，近 5 日 %s（%s）—— 境内资金%s。'
                         % (lt['dr007'], bp(d5), tone,
                            '价格上行＝边际收紧，对高估值成长股不利' if (d5 or 0) > 2 else
                            '价格下行＝边际转松，对权益估值有支撑' if (d5 or 0) < -2 else
                            '水位平稳，不构成方向性驱动'))
        h += ('<div style="font-size:11px;color:#777;margin-top:4px">'
              'DR007 = 存款类机构质押式回购 7 天定盘利率，是央行公开市场操作实际盯的锚，比 SHIBOR 更贴近真实资金面；'
              '上行＝收紧（红）、下行＝转松（绿）。</div>')

    # ── 5.3 国债收益率曲线 ──────────────────────────────────
    if RT:
        lt = RT.get('latest') or {}
        dv = RT.get('derived') or {}
        _sp = lambda v: '—' if v is None else '%+.1f bp' % (v * 100)
        h += '<div style="font-size:12.5px;font-weight:600;margin-top:12px">5.3 国债收益率曲线 · 无风险利率与期限利差</div>'
        h += '<table %s>' % TBD
        h += TH + '<th>指标</th><th>数值</th><th>指标</th><th>数值</th></tr>'
        _ma = dv.get('cn_10y_ma20')
        _dev = ((lt.get('cn_10y') - _ma) * 100) if (lt.get('cn_10y') is not None and _ma is not None) else None
        h += ('<tr><td><b>10Y 国债</b>（股债性价比分母）</td><td style="color:#B91C1C"><b>%s%%</b></td>'
              '<td>20 日均 / 偏离</td><td>%s%%　<span style="color:%s">%s</span></td></tr>'
              % (fmt(lt.get('cn_10y'), 3), fmt(_ma, 3), bp_col(_dev), bp(_dev)))
        h += ('<tr><td>2Y 国债（短端，贴政策利率）</td><td><b>%s%%</b></td>'
              '<td>5Y 国债</td><td>%s%%</td></tr>'
              % (fmt(lt.get('cn_2y'), 3), fmt(lt.get('cn_5y'), 3)))
        h += ('<tr><td>30Y 国债（长端，含增长预期）</td><td><b>%s%%</b></td>'
              '<td>10Y 近 20 日变化</td><td style="color:%s">%s</td></tr>'
              % (fmt(lt.get('cn_30y'), 3), bp_col(dv.get('cn_10y_chg_20d_bp')),
                 bp(dv.get('cn_10y_chg_20d_bp'))))
        h += ('<tr><td>10Y − 2Y 期限利差</td><td style="color:%s"><b>%s</b></td>'
              '<td>5Y−2Y / 30Y−10Y</td><td>%s / %s</td></tr>'
              % (bp_col(dv.get('cn_10y_2y_chg_20d_bp')), _sp(lt.get('cn_10y_2y')),
                 _sp(lt.get('cn_5y_2y')), _sp(lt.get('cn_30y_10y'))))
        _shape = '—'
        if dv.get('inverted') is True:
            _shape = '倒挂（10Y &lt; 2Y）'
        elif lt.get('cn_10y_2y') is not None:
            _shape = '正常陡峭' if lt['cn_10y_2y'] > 0.005 else '平坦'
        h += ('<tr><td>曲线形态</td><td>%s</td><td>数据日期</td><td>%s</td></tr>'
              % (_shape, esc(lt.get('date') or '—')))
        h += '</table>'
        if lt.get('cn_10y') is not None:
            _d20 = dv.get('cn_10y_chg_20d_bp')
            notes.append('国债：10Y %s%%（近 20 日 %s），2Y %s%%、30Y %s%%，10Y−2Y 利差 %s —— %s。'
                         '长端下行＝无风险利率走低，对权益估值是分母端的支撑；'
                         '利差走阔多对应宽松预期升温，走平/倒挂则偏谨慎。'
                         % (fmt(lt.get('cn_10y'), 3), bp(_d20), fmt(lt.get('cn_2y'), 3),
                            fmt(lt.get('cn_30y'), 3), _sp(lt.get('cn_10y_2y')),
                            _shape if _shape != '—' else '数据不足'))
        h += ('<div style="font-size:11px;color:#777;margin-top:4px">'
              '与 5.2 的区别：5.2 是银行间「资金价格」（短端、政策驱动，看紧不紧）；'
              '本节是「国债到期收益率」（整条曲线、含增长与通胀预期，看贵不贵）。'
              '算股债性价比时分母用的是 10Y 国债，不是 DR007。</div>')

    # ── 5.4 ETF 折溢价 ──────────────────────────────────────
    rows = (P or {}).get('data') or []
    if rows:
        h += '<div style="font-size:12.5px;font-weight:600;margin-top:12px">5.4 ETF 折溢价 · 二级市场价 vs 单位净值</div>'
        h += '<table %s>' % TBD
        h += TH + '<th>代码</th><th>名称</th><th>现价</th><th>单位净值</th><th>溢价率</th><th>提示</th></tr>'
        for r in rows:
            pv = r.get('premium_pct')
            if pv is None:
                pc, tag = '#333', '净值缺失'
            elif pv >= 1:
                pc, tag = CLR_UP, '明显溢价'
            elif pv >= 0.3:
                pc, tag = '#C2410C', '小幅溢价'
            elif pv <= -1:
                pc, tag = CLR_DOWN, '明显折价'
            elif pv <= -0.3:
                pc, tag = '#0E9F6E', '小幅折价'
            else:
                pc, tag = '#333', '贴近净值'
            if r.get('stale'):
                tag += ' · 净值滞后'
            h += ('<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td>'
                  '<td style="color:%s"><b>%s%%</b></td><td style="color:%s">%s</td></tr>'
                  % (esc(r.get('code') or ''), esc(r.get('name') or ''),
                     fmt(r.get('price'), 3), fmt(r.get('nav'), 3),
                     pc, sgn2(pv, 3), pc, esc(tag)))
        h += '</table>'
        hot = [r for r in rows if r.get('premium_pct') is not None and abs(r['premium_pct']) >= 1]
        if hot:
            notes.append('折溢价：%d 只 ETF 偏离净值超 1%%（%s）—— 溢价买入等于多付钱，'
                         '折价则可能是流动性不足或事件冲击，下单前先看这一列。'
                         % (len(hot), '、'.join('%s %s%%' % (r.get('code'), sgn2(r.get('premium_pct'), 2))
                                                for r in hot)))
        else:
            notes.append('折溢价：全部 %d 只 ETF 均贴近净值（偏离 &lt;1%%），场内买贵/买便宜的风险可忽略。' % len(rows))
        h += ('<div style="font-size:11px;color:#777;margin-top:4px">'
              '溢价率 =（现价 − 单位净值）÷ 单位净值。正值＝场内更贵，负值＝场内更便宜；'
              '净值按 T 日收盘计算，若标的当日停牌或 QDII 涉及时差会标注「净值滞后」。</div>')

    # ── 5.4 市场宽度 ────────────────────────────────────────
    t = (BR or {}).get('today') or {}
    if t.get('total'):
        up, dn, fl, tot = t.get('up') or 0, t.get('down') or 0, t.get('flat') or 0, t.get('total') or 0
        up_pct = t.get('up_pct')
        if up_pct is None and tot:
            up_pct = up / tot * 100
        h += '<div style="font-size:12.5px;font-weight:600;margin-top:12px">5.5 市场宽度 · 涨跌家数 / 涨停跌停 / 连板高度</div>'
        # 红涨绿跌的三段占比条
        wu = up / tot * 100 if tot else 0
        wf = fl / tot * 100 if tot else 0
        wd = dn / tot * 100 if tot else 0
        h += ('<div style="margin-top:6px;height:9px;border-radius:5px;overflow:hidden;'
              'background:#E8EAED;font-size:0">'
              '<span style="display:inline-block;height:9px;width:%.2f%%;background:%s"></span>'
              '<span style="display:inline-block;height:9px;width:%.2f%%;background:#BFC5CE"></span>'
              '<span style="display:inline-block;height:9px;width:%.2f%%;background:%s"></span></div>'
              % (wu, CLR_UP, wf, wd, CLR_DOWN))
        h += '<table %s>' % TBD
        h += TH + '<th>上涨</th><th>下跌</th><th>平盘</th><th>合计</th><th>涨停</th><th>跌停</th><th>最高连板</th></tr>'
        h += ('<tr><td style="color:%s"><b>%d</b></td><td style="color:%s"><b>%d</b></td>'
              '<td>%d</td><td>%d</td><td style="color:%s"><b>%s</b></td>'
              '<td style="color:%s"><b>%s</b></td><td><b>%s 板</b></td></tr>'
              % (CLR_UP, up, CLR_DOWN, dn, fl, tot,
                 CLR_UP, t.get('limit_up') if t.get('limit_up') is not None else '—',
                 CLR_DOWN, t.get('limit_down') if t.get('limit_down') is not None else '—',
                 t.get('max_streak') if t.get('max_streak') is not None else '—'))
        h += '</table>'
        # 最近若干个交易日的自建序列（上游不支持按日查询，只能本仓库逐日累积）
        hist = ((BR or {}).get('history') or [])[-6:]
        if len(hist) > 1:
            h += '<div style="font-size:12px;font-weight:600;margin-top:10px">近期宽度序列（本仓库逐日累积，共 %d 个交易日）</div>' % len(
                (BR or {}).get('history') or [])
            h += '<table %s>' % TBD
            h += TH + '<th>日期</th><th>上涨</th><th>下跌</th><th>上涨占比</th><th>涨停</th><th>跌停</th><th>最高连板</th></tr>'
            for r in hist:
                rp = r.get('up_pct')
                if rp is None and r.get('total'):
                    rp = (r.get('up') or 0) / r['total'] * 100
                h += ('<tr><td>%s</td><td style="color:%s">%s</td><td style="color:%s">%s</td>'
                      '<td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
                      % (esc(r.get('date') or '—'),
                         CLR_UP, r.get('up', '—'), CLR_DOWN, r.get('down', '—'),
                         '—' if rp is None else '%.1f%%' % rp,
                         r.get('limit_up', '—'), r.get('limit_down', '—'),
                         r.get('max_streak', '—')))
            h += '</table>'
        if up_pct is not None:
            mood = ('普涨' if up_pct >= 70 else '多数上涨' if up_pct >= 55
                    else '多空拉锯' if up_pct >= 45 else '多数下跌' if up_pct >= 30 else '普跌')
            lu, ld = t.get('limit_up') or 0, t.get('limit_down') or 0
            notes.append('宽度：%s 上涨 %d / 下跌 %d（上涨占比 <b>%.1f%%</b>，%s），'
                         '涨停 %s / 跌停 %s、最高 %s 连板 —— %s。'
                         % (esc(t.get('date') or ''), up, dn, up_pct, mood, lu, ld,
                            t.get('max_streak', '—'),
                            '赚钱效应扩散' if (up_pct >= 55 and lu > ld)
                            else '个股承接弱，指数上涨未必有广泛基础' if up_pct < 45
                            else '结构性行情，分化为主'))
        h += ('<div style="font-size:11px;color:#777;margin-top:4px">'
              '涨跌家数由东财「涨跌幅分布直方图」求和（与 push2 的 f104/f105/f106 交叉校验，差异 &lt;2%，'
              '源于是否含北交所与停牌股）；涨停/跌停取对应池子的 tc 字段，连板高度取池内 lbc 最大值。'
              '<b>上游三个接口只返回当日快照、忽略日期参数</b>，因此历史序列从接入当天起逐日累积，无法回填。</div>')
        if up_pct is not None:
            notes.append('宽度与 LSI 的组合用法：指数（① ②）在涨、但上涨占比 &lt;40%，说明是权重股撑指数、'
                         '个股在跌 —— 这种分化最适合减仓而非加仓；反之指数横盘而宽度回升，往往是底部特征。')

    # ── 5.5 一句话综合 ──────────────────────────────────────
    if notes:
        h += '<div style="background:#F4F6F8;border-left:4px solid #22D3EE;padding:10px 13px;' \
             'border-radius:6px;font-size:12px;margin-top:11px;line-height:1.9">' \
             '<b>⑤ 一句话综合</b><br>'
        h += '<br>'.join('· ' + n for n in notes)
        h += '</div>'

    errs = S.get('errors') or []
    if errs:
        h += ('<div style="color:#B26A00;font-size:11px;margin-top:6px">'
              '本次抓取有 %d 项失败（对应小节已省略）：%s</div>'
              % (len(errs), esc('；'.join(errs))))
    h += '</div>'
    return h


def build_message(subject, html, sender, recipients):
    """构造一封带内嵌图片的 HTML 邮件（收件人支持逗号分隔的多个地址）"""
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipients
    msg.set_content('本邮件含 HTML 内容，请使用支持 HTML 的客户端查看。')
    msg.add_alternative(html, subtype='html')
    if os.path.exists(PNG):
        ctype, _ = mimetypes.guess_type(PNG)
        mt, st = (ctype or 'image/png').split('/', 1)
        with open(PNG, 'rb') as fp:
            msg.get_payload()[1].add_related(fp.read(), maintype=mt, subtype=st, cid='<monitor>')
    return msg


def _safe_local_hostname():
    """EHLO 用的本机名必须是纯 ASCII。

    中文 Windows 电脑的「计算机名」常常是中文，smtplib 发 EHLO 时会
    UnicodeEncodeError 直接崩掉（表现为「邮件发送失败：'ascii' codec ...」）。
    这里做一次 ASCII 校验，非 ASCII 就退回 localhost。
    """
    try:
        h = socket.gethostname() or ''
        h.encode('ascii')
        return h or 'localhost'
    except Exception:
        return 'localhost'


def split_addrs(s):
    """把 'a@x.com,b@x.com'（也兼容分号/空格）拆成地址列表"""
    if not s:
        return []
    out = []
    for part in re.split(r'[,;\s]+', s.strip()):
        p = part.strip()
        if p:
            out.append(p)
    return out


def smtp_send(host, port, user, pwd, msg, to_list=None):
    """按端口自动选 SSL(465) 或 STARTTLS(587)"""
    lh = _safe_local_hostname()
    if port == 465:
        s = smtplib.SMTP_SSL(host, port, timeout=60, local_hostname=lh)
    else:
        s = smtplib.SMTP(host, port, timeout=60, local_hostname=lh)
        try:
            s.starttls()
        except smtplib.SMTPException:
            pass          # 少数服务器不声明 STARTTLS，忽略即可
    try:
        s.login(user, pwd)
        # 显式给出收件人列表：不依赖 smtplib 从 To 头反解析，
        # 逗号/分号混写或带中文显示名时才不会漏发
        if to_list:
            s.send_message(msg, from_addr=user, to_addrs=to_list)
        else:
            s.send_message(msg)
    finally:
        try:
            s.quit()
        except Exception:
            pass


def main():
    summary = load('summary.json')
    if not summary or not summary.get('tracks'):
        print('!! 缺少 summary.json')
        sys.exit(1)
    R = load('ratios.json')
    L = load('lsi.json')
    S = load('signals.json')

    tk = summary['tracks']
    asof = summary.get('asof', '')
    h300 = tk.get('hs300', {})
    cyb = tk.get('cyb', {})
    macro_txt = L['state'] if L else '—'
    lsi_txt = fmt(L['core']['lsi'], 1) if L else '—'
    subject = ('[A股双宽基主力 & 宏观LSI日报] %s | 沪深300: %s | 创业板: %s | 宏观: %s (LSI: %s BP)'
               % (asof, h300.get('status', '—'), cyb.get('status', '—'), macro_txt, lsi_txt))

    H = '<div style="font-family:Microsoft YaHei,PingFang SC,Arial,sans-serif;font-size:13px;color:#222;max-width:1000px">'
    H += '<h2 style="font-size:18px;margin:0 0 10px">A股双宽基 ETF + 宏观 LSI 三合一日报 · %s</h2>' % esc(asof)
    # 顶部摘要额外带一眼宽度与估值分位：这两项是「指数涨但个股跌」这类背离的判据，
    # 放在最上面比埋在 ⑤ 里更容易被看到。
    _bt = (S or {}).get('breadth', {}).get('today') or {}
    _extra = ''
    if _bt.get('total'):
        _up = _bt.get('up') or 0
        _rp = _bt.get('up_pct')
        if _rp is None:
            _rp = _up / _bt['total'] * 100
        _extra = '　｜　宽度：涨 %d / 跌 %d（上涨占比 %.1f%%，涨停 %s）' % (
            _up, _bt.get('down') or 0, _rp,
            _bt.get('limit_up') if _bt.get('limit_up') is not None else '—')
    H += '<div style="color:#666;font-size:12px;margin-bottom:6px">沪深300：%s　｜　创业板：%s　｜　宏观：%s（报警 %s/%s 项）%s</div>' % (
        esc(h300.get('status', '—')), esc(cyb.get('status', '—')), esc(macro_txt),
        L.get('alert_count', 0) if L else 0, L.get('total', 20) if L else 20, _extra)

    # 标题区追加：③ 三大风格轮动 & 股债性价比 · 历史百分位 的配置倾向
    if R and R.get('items'):
        chips = []
        for k in R.get('order', []):
            it = R['items'].get(k)
            if not it:
                continue
            cc = CLR_UP if it['level'] == 'high' else (CLR_DOWN if it['level'] == 'low' else '#666')
            chips.append(
                '<span style="display:inline-block;margin:0 6px 6px 0;padding:5px 10px;border:1px solid %s;'
                'border-radius:7px;background:#FAFBFC;font-size:11.8px">'
                '<b>%s</b>：分位 <b style="color:%s">%.1f%%</b>　→　<b style="color:%s">%s</b></span>'
                % (cc, esc(it['title']), cc, it['pct'], cc, esc(it['tilt'])))
        H += ('<div style="font-size:12px;margin-bottom:14px">'
              '<div style="color:#666;margin-bottom:4px">③ 三大风格轮动 &amp; 股债性价比 · 历史百分位 · 配置倾向：</div>'
              + ''.join(chips) + '</div>')
    idx = 0
    for k in ORDER:
        if k in tk:
            idx += 1
            H += track_block(tk[k], '①②③④⑤'[idx - 1] if idx <= 5 else str(idx))
    H += ratio_block(R)
    H += lsi_block(L)
    H += signals_block(S)
    if os.path.exists(PNG):
        H += '<div style="margin-top:16px"><div style="font-size:13px;font-weight:600;margin-bottom:6px">⑥ 高清三合一监测图</div><img src="cid:monitor" style="max-width:100%;border:1px solid #DDD;border-radius:8px"></div>'
    H += '<div style="margin-top:18px;color:#888;font-size:11px;line-height:1.8">本邮件由 GitHub Actions 自动生成，数据源：腾讯自选股 westock-data（A股 ETF 份额/净值/指数）、美联储 FRED（宏观序列），以及 a-stock-api Worker 中转的蛋卷基金（估值）、中国货币网（SHIBOR/回购定盘）、东财（折溢价/涨停池）。仅供个人研究参考，不构成任何投资建议。</div>'
    H += '</div>'

    with open(PREVIEW, 'w', encoding='utf-8') as f:
        f.write(H)
    print('邮件正文已生成：', PREVIEW)

    def _env(k):
        return (os.environ.get(k) or '').strip()

    user, pwd, to = _env('ETF_SMTP_USER'), _env('ETF_SMTP_PASS'), _env('ETF_MAIL_TO')
    cfg = {}
    cfg_p = os.path.join(BASE, 'email_config.json')
    if os.path.exists(cfg_p):
        try:
            cfg = json.load(open(cfg_p, encoding='utf-8')) or {}
        except Exception:
            cfg = {}
    if not (user and pwd and to):
        user = user or (cfg.get('sender') or '')
        pwd = pwd or (cfg.get('auth_code') or '')
        rc = cfg.get('receivers')
        to = to or (','.join(rc) if isinstance(rc, list) else (rc or ''))

    # 第二发件账号（如 Gmail）：环境变量优先，其次 email_config.json 的 "second" 段
    u2 = _env('ETF_SMTP_USER_2')
    p2 = _env('ETF_SMTP_PASS_2')
    to2 = _env('ETF_MAIL_TO_2')
    c2 = cfg.get('second') or {}
    if not (u2 and p2) and c2:
        u2 = u2 or (c2.get('sender') or '')
        p2 = p2 or (c2.get('auth_code') or '')
        r2 = c2.get('receivers')
        to2 = to2 or (','.join(r2) if isinstance(r2, list) else (r2 or ''))
    if not (user and pwd and to):
        print('未配置邮箱凭证，仅生成本地预览（不发送）')
        return

    if os.environ.get('ETF_DRY_RUN') == '1':
        print('ETF_DRY_RUN=1：仅预览，不发送')
        return

    msg = build_message(subject, H, user, to)
    host = os.environ.get('ETF_SMTP_HOST', 'smtp.qq.com')
    port = int(os.environ.get('ETF_SMTP_PORT', '465'))
    try:
        smtp_send(host, port, user, pwd, msg, split_addrs(to))
        print('✅ 主账号（%s）已发送 → %s' % (user, split_addrs(to)))
    except Exception as e:
        print('!! 主账号邮件发送失败：%s' % e)
        sys.exit(1)

    # ---- 可选：第二个发件账号（如 Gmail）同时发送一份 ----
    to2 = to2 or to
    if u2 and p2:
        h2 = os.environ.get('ETF_SMTP_HOST_2', 'smtp.gmail.com')
        p2port = int(os.environ.get('ETF_SMTP_PORT_2', '587'))
        try:
            m2 = build_message(subject, H, u2, to2)
            smtp_send(h2, p2port, u2, p2, m2, split_addrs(to2))
            print('✅ 第二账号（%s）已发送 → %s' % (u2, split_addrs(to2)))
        except Exception as e:
            # 第二账号失败不阻断：主账号那封已经送达，仅告警
            print('!! 第二账号（%s）发送失败：%s' % (u2, e))
            print('   （主账号邮件已送达，本条仅为备用通道告警，不影响整体流程）')
    else:
        print('（未配置第二发件账号 ETF_SMTP_USER_2 / ETF_SMTP_PASS_2，只走主账号）')


if __name__ == '__main__':
    main()

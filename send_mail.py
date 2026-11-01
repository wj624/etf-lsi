# -*- coding: utf-8 -*-
"""
三合一汇总日报邮件

标题：[A股双宽基主力 & 宏观LSI日报] YYYY-MM-DD | 沪深300: <状态> | 创业板: <状态> | 宏观: <状态> (LSI: XX.X BP)

正文：① 沪深300 诊断 + 份额明细　② 创业板 诊断 + 份额明细
     ③ 三大风格/股债性价比百分位　④ LSI 核心面板 + 20项报警明细表 + 四维诊断　⑤ 内嵌监测图

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
    H += '<div style="color:#666;font-size:12px;margin-bottom:6px">沪深300：%s　｜　创业板：%s　｜　宏观：%s（报警 %s/%s 项）</div>' % (
        esc(h300.get('status', '—')), esc(cyb.get('status', '—')), esc(macro_txt),
        L.get('alert_count', 0) if L else 0, L.get('total', 20) if L else 20)

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
    if os.path.exists(PNG):
        H += '<div style="margin-top:16px"><div style="font-size:13px;font-weight:600;margin-bottom:6px">⑤ 高清三合一监测图</div><img src="cid:monitor" style="max-width:100%;border:1px solid #DDD;border-radius:8px"></div>'
    H += '<div style="margin-top:18px;color:#888;font-size:11px;line-height:1.8">本邮件由 GitHub Actions 自动生成，数据源：腾讯自选股 westock-data（A股 ETF 份额/净值/指数）与美联储 FRED（宏观序列）。仅供个人研究参考，不构成任何投资建议。</div>'
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

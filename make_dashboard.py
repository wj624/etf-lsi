# -*- coding: utf-8 -*-
"""
三合一交互式 HTML 总控看板（自包含、无外部依赖、离线可用）

区块：
  ① 顶部三张状态卡（沪深300 / 创业板 / 宏观 LSI）
  ② 沪深300 双轴交互图（悬停看每日明细）
  ③ 创业板 双轴交互图
  ④ 三大风格 / 股债比价全周期百分位
  ⑤ 宏观 LSI 核心面板 + V57 资金流向雷达
  ⑥ 20 项背景报警全量明细表（原始数据 / 公式 / 结果 / 阈值 / 红绿报警）
  ⑦ 正面宽松状态指示
  ⑧ 四维全景合成诊断
  ⑨ 近 5 日 ETF 份额明细表（两条赛道）
"""
import json, os, sys, datetime

import common
from config import ORDER

BASE = common.BASE
HTML = os.path.join(BASE, 'etf_lsi_dashboard.html')


def load(name, default=None):
    p = os.path.join(BASE, name)
    if not os.path.exists(p):
        return default
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def write_icons():
    """生成「添加到主屏幕」用的应用图标与 manifest.json。

    图标用 matplotlib 现画（深色底 + 橙/紫双线，与看板配色一致）；
    matplotlib 不可用时静默跳过——网页本身仍完全可用，只是主屏幕图标会退化为浏览器默认图标。
    """
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except Exception:
        print('（跳过图标生成：matplotlib 不可用）')
        return []

    # 「剪刀差」构图：两线自左侧同一点出发、向右分道扬镳
    xs = [0.12, 0.27, 0.42, 0.57, 0.72, 0.88]
    up = [0.50, 0.55, 0.61, 0.67, 0.73, 0.80]     # 橙线：ETF 持仓占比（上行）
    dn = [0.50, 0.45, 0.40, 0.35, 0.29, 0.22]     # 紫线：指数收盘（下行）
    files = []
    for size in (180, 192, 512):
        dpi = 100
        fig = plt.figure(figsize=(size / dpi, size / dpi), dpi=dpi)
        ax = fig.add_axes([0, 0, 1, 1])
        ax.set_axis_off()
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        fig.patch.set_facecolor('#181A20')
        ax.set_facecolor('#181A20')
        ax.plot(xs, dn, color='#9B6BFF', lw=size / 30.0, solid_capstyle='round', zorder=3)
        ax.plot(xs, up, color='#FF8A1F', lw=size / 24.0, solid_capstyle='round', zorder=4)
        p = os.path.join(common.BASE, 'icon-%d.png' % size)
        fig.savefig(p, dpi=dpi, facecolor='#181A20')
        plt.close(fig)
        files.append('icon-%d.png' % size)

    manifest = {
        'name': 'A股双宽基 ETF + 宏观 LSI 三合一监测',
        'short_name': 'ETF监测',
        'description': '沪深300 / 创业板 ETF 持仓背离 + 美联储宏观 LSI 流动性压力指数',
        'start_url': './index.html',
        'scope': './',
        'display': 'standalone',
        'orientation': 'portrait',
        'background_color': '#181A20',
        'theme_color': '#181A20',
        'icons': [
            {'src': 'icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': 'icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
            {'src': 'icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
    }
    with open(os.path.join(common.BASE, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    files.append('manifest.json')
    print('已生成图标与 manifest：%s' % '、'.join(files))
    return files


def main():
    summary = load('summary.json')
    if not summary or not summary.get('tracks'):
        print('!! 缺少 summary.json，请先运行 analyze_report.py')
        sys.exit(1)

    tracks = {}
    for k in ORDER:
        pk = load('series_%s.json' % k)
        if not pk:
            continue
        syms = list(pk['names'].keys())
        tracks[k] = {
            'dates': pk['dates'],
            'hold': [round(v, 5) for v in pk['hold']],
            'idx': [round(v, 2) for v in pk['idx']],
            'spread': [round(v, 2) for v in pk['spread']],
            'shares': {s: [round(v / 1e8, 3) if v else None for v in pk['per_etf_shares'][s]] for s in syms},
            'chg': {s: [round(v / 1e8, 3) if v is not None else None for v in pk['per_etf_chg'][s]] for s in syms},
            'names': pk['names'],
            'summary': pk['summary'],
        }
    DATA = {'tracks': tracks, 'order': [k for k in ORDER if k in tracks],
            'asof': summary.get('asof', ''),
            'generated_at': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}
    R = load('ratios.json')
    if R and R.get('items'):
        DATA['ratios'] = R
    L = load('lsi.json')
    if L:
        DATA['lsi'] = L
    S = load('signals.json')
    if S:
        # 只做「有就传、没有就整块不出现」的处理：任一子项缺失都不影响其它面板。
        sig = {'updated': S.get('updated', '')}
        for k in ('valuation', 'liquidity', 'premium', 'breadth'):
            if S.get(k):
                sig[k] = S[k]
        if S.get('errors'):
            sig['errors'] = S['errors']
        if len(sig) > 1:
            DATA['signals'] = sig

    JS = json.dumps(DATA, ensure_ascii=False)

    TPL = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>A股双宽基 ETF + 宏观 LSI · 三合一监测看板</title>
<!-- 添加到主屏幕（PWA）相关：iOS Safari / Android Chrome 均支持独立图标启动 -->
<meta name="theme-color" content="#181A20">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="ETF监测">
<meta name="application-name" content="ETF监测">
<meta name="format-detection" content="telephone=no">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="icon" type="image/png" sizes="192x192" href="icon-192.png">
<link rel="manifest" href="manifest.json">
<style>
:root{--bg:#181A20;--panel:#1E2128;--panel2:#23272F;--grid:#2A2F39;--txt:#D6DAE1;--sub:#8A93A3;
--orange:#FF8A1F;--purple:#9B6BFF;--up:#E8453C;--down:#1FB37A;--blue:#4C9AFF;--cyan:#22D3EE;}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--txt);font:14px/1.65 "Microsoft YaHei","PingFang SC",-apple-system,"Segoe UI",sans-serif;padding:24px 20px 46px}
.wrap{max-width:1240px;margin:0 auto}
h1{font-size:22px;letter-spacing:.5px}
h2{font-size:15px;font-weight:600;margin-bottom:4px}
.meta{color:var(--sub);font-size:12.5px}
.bar{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start;justify-content:space-between;margin-bottom:16px}
.badges{display:flex;gap:10px;flex-wrap:wrap}
.badge{padding:7px 15px;border-radius:9px;font-size:14px;font-weight:700;border:1px solid}
.badge.good{color:var(--down);border-color:var(--down);background:rgba(31,179,122,.10)}
.badge.warn{color:#F5A623;border-color:#F5A623;background:rgba(245,166,35,.10)}
.badge.danger{color:var(--up);border-color:var(--up);background:rgba(232,69,60,.10)}
.badge.ok{color:var(--blue);border-color:var(--blue);background:rgba(76,154,255,.10)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(162px,1fr));gap:12px;margin:14px 0 18px}
.card{background:var(--panel);border:1px solid var(--grid);border-radius:12px;padding:13px 15px}
.card .k{color:var(--sub);font-size:12px;margin-bottom:5px}
.card .v{font-size:20px;font-weight:700;font-family:Consolas,monospace}
.card .d{font-size:11.5px;color:var(--sub);margin-top:3px}
.panel{background:var(--panel);border:1px solid var(--grid);border-radius:14px;padding:16px 16px 12px;margin-bottom:18px;position:relative}
.panel .hint{color:var(--sub);font-size:11.8px;margin-bottom:9px;line-height:1.75}
svg{display:block;width:100%;height:auto}
.tip{position:absolute;pointer-events:none;background:#0E1014f2;border:1px solid var(--grid);border-radius:9px;
padding:9px 12px;font-size:12px;min-width:210px;display:none;z-index:9;line-height:1.8;box-shadow:0 8px 24px #0008}
.tip b{font-family:Consolas,monospace}
table{width:100%;border-collapse:collapse;font-size:12.6px}
th,td{padding:7px 9px;text-align:right;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--sub);font-weight:600;background:var(--panel2);text-align:right;white-space:nowrap}
th:nth-child(-n+3),td:nth-child(-n+3){text-align:left}
td{font-family:Consolas,monospace}
td.raw,td.fm{font-family:"Microsoft YaHei",sans-serif;font-size:11.6px;color:var(--sub);text-align:left}
.pos{color:var(--up)} .neg{color:var(--down)}
.alert-on{color:#E8453C;font-weight:700}
.alert-off{color:#1FB37A;font-weight:700}
.foot{color:var(--sub);font-size:11.6px;margin-top:8px;line-height:1.85}
.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12px;color:var(--sub);margin:2px 0 6px}
.legend i{display:inline-block;width:20px;height:3px;border-radius:2px;vertical-align:middle;margin-right:6px}
/* 缩放工具条（三张图共用） */
.zbar{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:2px 0 8px}
.zbtn{background:var(--panel2);border:1px solid var(--grid);color:var(--sub);font-size:11.5px;
padding:3px 9px;border-radius:7px;cursor:pointer;user-select:none;font-family:inherit;line-height:1.6}
.zbtn:hover{border-color:#4a5160;color:var(--txt)}
.zbtn.on{background:#2A3140;border-color:#4a5160;color:#fff}
.zhint{color:#6b7484;font-size:11px;margin-left:4px}
.zrange{color:#6b7484;font-size:11px;margin-left:auto;font-family:Consolas,monospace}
svg.zc{cursor:crosshair;touch-action:none}
svg.zc.drag{cursor:grabbing}
.reason{background:var(--panel);border:1px solid var(--grid);border-left:3px solid var(--blue);
border-radius:10px;padding:12px 15px;margin-bottom:16px;font-size:13px}
.rgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(400px,1fr));gap:14px}
.rbox{background:var(--panel2);border:1px solid var(--grid);border-radius:11px;padding:12px 14px}
.rbox .t{font-size:13px;font-weight:600;margin-bottom:2px}
.rbox .fm{color:var(--sub);font-size:11.4px;margin-bottom:8px}
.barwrap{position:relative;height:26px;background:#15181D;border-radius:5px;overflow:hidden;margin:6px 0 4px}
.barwrap .lo{position:absolute;left:0;top:0;bottom:0;width:20%;background:rgba(31,179,122,.20)}
.barwrap .hi{position:absolute;right:0;top:0;bottom:0;width:20%;background:rgba(232,69,60,.20)}
.barwrap .mk{position:absolute;top:-3px;bottom:-3px;width:3px;background:#fff;border-radius:2px}
.rbox .kv{display:flex;justify-content:space-between;font-size:11.8px;color:var(--sub)}

/* ── ⑨~⑫ 市场环境面板 ─────────────────────────────── */
.mgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px}
.mbox{background:var(--panel2);border:1px solid var(--grid);border-radius:11px;padding:13px 15px}
.mbox .t{font-size:13px;font-weight:600;margin-bottom:3px;display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.mbox .t .tag{font-size:11px;font-weight:400;color:var(--sub);font-family:Consolas,monospace}
.hl{height:9px;border-radius:5px;margin:9px 0 6px;position:relative;
background:linear-gradient(90deg,#1FB37A 0%,#5FA83A 30%,#C9A227 55%,#E0713C 78%,#E8453C 100%)}
.hl i{position:absolute;top:-4px;width:3px;height:17px;background:#fff;border-radius:2px;box-shadow:0 0 0 1px #0006}
.hlscale{display:flex;justify-content:space-between;font-size:10.5px;color:#6b7484;font-family:Consolas,monospace}
.mrow{display:flex;justify-content:space-between;font-size:12px;padding:3px 0;border-bottom:1px dashed #262B34}
.mrow:last-child{border-bottom:none}
.mrow span:first-child{color:var(--sub)}
.mrow b{font-family:Consolas,monospace;font-weight:600}
.wbar{display:flex;height:30px;border-radius:6px;overflow:hidden;margin:10px 0 6px;font-size:11.5px;line-height:30px;color:#0d0f13;font-weight:700}
.wbar div{text-align:center;overflow:hidden;white-space:nowrap}
.wleg{display:flex;gap:16px;font-size:11.5px;color:var(--sub);flex-wrap:wrap}
.wleg i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:-1px}
.prow{display:grid;grid-template-columns:88px 1fr 66px;align-items:center;gap:9px;font-size:12px;padding:3px 0}
.prow .nm{color:var(--sub);font-family:Consolas,monospace}
.ptrack{position:relative;height:16px;background:#15181D;border-radius:4px;overflow:hidden}
.ptrack .zero{position:absolute;top:0;bottom:0;width:1px;background:#3a4150}
.ptrack .fill{position:absolute;top:2px;bottom:2px;border-radius:3px}
.prow .vv{text-align:right;font-family:Consolas,monospace;font-weight:600}

.diag{background:var(--panel2);border:1px solid var(--grid);border-left:3px solid var(--cyan);
border-radius:10px;padding:12px 15px;margin-bottom:10px;font-size:12.8px;line-height:1.9;white-space:pre-wrap}
.diag .h{color:var(--cyan);font-weight:700}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:14px}
@media(max-width:680px){
  body{padding:12px 8px 30px;-webkit-text-size-adjust:100%}
  h1{font-size:17px;line-height:1.4}
  h2{font-size:13.5px}
  .panel{padding:12px 10px 10px;border-radius:12px}
  .cards{grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:9px}
  .card{padding:10px 11px}.card .v{font-size:17px}
  table{font-size:11.4px}
  th,td{padding:6px 6px}
  .rgrid,.grid2{grid-template-columns:1fr}
  .badge{font-size:12.5px;padding:6px 11px}
  .diag{font-size:12px;line-height:1.8}
  .tip{min-width:170px;font-size:11.4px}
}
</style>
</head>
<body><div class="wrap">

<div class="bar">
  <div>
    <h1>A股双宽基 ETF 持仓背离 + 宏观 LSI 流动性压力 · 三合一监测</h1>
    <div class="meta" id="subMeta"></div>
  </div>
  <div class="badges" id="badges"></div>
</div>

<div class="cards" id="topCards"></div>

<div id="trackBlocks"></div>

<div class="panel" id="ratioPanel" style="display:none">
  <h2>④ 三大风格 / 股债比价 · 全周期历史百分位</h2>
  <div class="hint">三个比值均为「防御性资产 ÷ 进攻性资产」，故 <b>比值上行 = 防御占优</b>，可直接横向对比。
  曲线为周K；百分位基于各标的上市以来<b>全周期</b>全样本（按周分段抓取拼接）。
  绿区 = 分位 0~20，红区 = 分位 80~100。<b style="color:#F5A623">注意：</b>「谁占优」说的是过去谁跑赢，
  操作看的是性价比——红区说明分子资产已大幅跑赢、相对变贵（到顶），结论反而是<b>卖出分子、买入分母</b>（均值回归）。</div>
  <div class="rgrid" id="ratioCards"></div>
</div>

<div class="panel" id="lsiPanel" style="display:none">
  <h2>⑤ 宏观 LSI 核心面板（美联储流动性压力指数）</h2>
  <div class="hint" id="lsiHint"></div>
  <h2 style="margin-top:8px">⑤-1 美元宏观流动性压力指数 LSI vs 美联储净流动性 GLI（悬停查看每日数值 · 可缩放查看近 5 年）</h2>
  <div class="legend"><span><i style="background:var(--orange)"></i>LSI 压力指数（左轴，bps）</span>
  <span><i style="background:var(--blue)"></i>GLI 净流动性（右轴，万亿美元 T）</span>
  <span><i style="background:#F5A623"></i>阈值线：+20 / +50 / −30 bps</span></div>
  <div class="zbar" id="lsiZbar"></div>
  <svg id="lsiChart" viewBox="0 0 1000 360"></svg>
  <div class="tip" id="lsiTip"></div>
  <div class="cards" id="lsiCards"></div>
  <div id="flowBox"></div>
</div>

<div class="panel" id="alertPanel" style="display:none">
  <h2>⑥ 20 项背景颜色报警 · 全量明细表</h2>
  <div class="hint">下表列出每一项报警的<b>原始数据 → 计算公式 → 当前结果 → 代码阈值 → 是否报警</b>。
  <b class="alert-on">红色加粗</b> = 当前已触发报警；<b class="alert-off">绿色</b> = 当前正常未触发。所有阈值严格照搬 TradingView Pine Script 原代码。</div>
  <div style="overflow-x:auto"><table id="alertTbl"></table></div>
  <div class="foot" id="excludedNote"></div>
</div>

<div class="panel" id="loosePanel" style="display:none">
  <h2>⑦ 正面宽松状态指示</h2>
  <div style="overflow-x:auto"><table id="looseTbl"></table></div>
</div>

<div class="panel" id="diagPanel" style="display:none">
  <h2>⑧ 四维全景合成诊断（资金动态 → 一阶宏观周期 → 二阶流动性水位 → 三阶微观定价）</h2>
  <div id="diagBox"></div>
</div>

<div class="panel" id="liqCnPanel" style="display:none">
  <h2>⑨ 境内资金面（DR007 / SHIBOR）· 与 ⑤ 的境外流动性互为对照</h2>
  <div class="hint" id="liqCnHint"></div>
  <svg id="liqCnChart" viewBox="0 0 1000 300"></svg>
  <div class="cards" id="liqCnCards"></div>
</div>

<div class="panel" id="breadthPanel" style="display:none">
  <h2>⑩ 市场宽度（涨跌家数 / 涨停跌停 / 连板高度）</h2>
  <div class="hint" id="breadthHint"></div>
  <div class="cards" id="breadthCards"></div>
  <div id="breadthBar"></div>
  <svg id="breadthChart" viewBox="0 0 1000 220"></svg>
</div>

<div class="panel" id="valPanel" style="display:none">
  <h2>⑪ 指数估值分位（PE / PB · 数据源：蛋卷基金）</h2>
  <div class="hint" id="valHint"></div>
  <div id="valBox"></div>
</div>

<div class="panel" id="premPanel" style="display:none">
  <h2>⑫ ETF 折溢价（二级市场价 vs 单位净值）</h2>
  <div class="hint" id="premHint"></div>
  <div id="premBox"></div>
</div>

<div id="shareBlocks"></div>

<div class="foot" id="footNote"></div>
</div>

<script>
const D = __DATA__;
const $ = id => document.getElementById(id);
const fmt = (v,n) => (v===null||v===undefined) ? '—' : Number(v).toFixed(n);
/* 空值安全：单个 FRED 序列偶发超时返回 null 时，
   null/100 会被算成 0 并误显示成 0.00%（还会误判红字），这里统一挡掉 */
const d100 = v => (v===null||v===undefined) ? null : v/100;
const gt = (v,t) => (v!==null&&v!==undefined) && v>t;
const lt = (v,t) => (v!==null&&v!==undefined) && v<t;
const sign = (v,n) => (v===null||v===undefined) ? '—' : (v>=0?'+':'') + Number(v).toFixed(n);
const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');

/* ---------- 顶部 ---------- */
const parts = [];
for (const k of D.order) parts.push(D.tracks[k].summary.name + ' ' + D.tracks[k].summary.date);
if (D.lsi) parts.push('宏观 ' + D.lsi.asof);
$('subMeta').textContent = '数据截至：' + parts.join('　｜　') +
  '　｜　A股数据源：腾讯自选股 westock-data　宏观数据源：美联储 FRED' +
  (D.generated_at ? '　｜　本页生成时间：' + D.generated_at : '');

let bh = '';
for (const k of D.order) {
  const s = D.tracks[k].summary;
  bh += '<div class="badge ' + s.level + '">' + s.name + '：' + esc(s.status) + '</div>';
}
if (D.lsi) bh += '<div class="badge ' + D.lsi.level + '">宏观：' + esc(D.lsi.state) + '（' + D.lsi.alert_count + '/' + D.lsi.total + ' 报警）</div>';
$('badges').innerHTML = bh;

/* ---------- 顶部卡片 ---------- */
let ch = '';
for (const k of D.order) {
  const s = D.tracks[k].summary;
  const c = s.net5 >= 0 ? 'var(--up)' : 'var(--down)';
  ch += '<div class="card"><div class="k">' + s.name + ' · 持仓占比</div><div class="v" style="color:var(--orange)">' + fmt(s.hold_pct,4) + '%</div><div class="d">' + esc(s.labels.hold_card) + '</div></div>' +
        '<div class="card"><div class="k">' + s.name + ' · 开口差 Spread</div><div class="v" style="color:var(--blue)">' + sign(s.spread,1) + '</div><div class="d">阈值 ±25｜近20日斜率 ' + sign(s.hold_slope,2) + '</div></div>' +
        '<div class="card"><div class="k">' + s.name + ' · 近5日净申赎</div><div class="v" style="color:' + c + '">' + sign(s.net5,2) + ' 亿份</div><div class="d">净变动 ' + sign(s.net5_ratio,2) + '%｜' + s.index_name + ' ' + fmt(s.idx_close,2) + '</div></div>';
}
if (D.lsi) {
  const c = D.lsi.core;
  const lsiCol = (gt(c.lsi,49.999)?'#8B1A1A':(gt(c.lsi,19.999)?'var(--up)':(lt(c.lsi,0)?'var(--down)':'var(--txt)')));
  ch += '<div class="card"><div class="k">宏观 LSI 压力指数</div><div class="v" style="color:' + lsiCol + '">' + fmt(c.lsi,1) + ' bp</div><div class="d">紧张 ≥20｜极端 ≥50</div></div>' +
        '<div class="card"><div class="k">美联储净流动性 GLI</div><div class="v" style="color:var(--blue)">' + fmt(c.gli,3) + ' T</div><div class="d">WALCL−TGA−RRP｜20日 ' + sign(c.tlc,2) + '%</div></div>' +
        '<div class="card"><div class="k">RRP 缓冲垫 / 信用利差</div><div class="v" style="color:' + (lt(c.rrp_pct,5)?'var(--up)':'var(--down)') + '">' + fmt(c.rrp_pct,1) + '%</div><div class="d">RRP ' + fmt(c.rrp_T,3) + ' T｜利差 ' + fmt(c.credit,0) + ' bp</div></div>';
}
$('topCards').innerHTML = ch;

/* ---------- 双宽基交互图（滚轮缩放 / 拖拽平移 / 区间按钮） ---------- */
const ZMIN = 15;                                  /* 窗口最窄保留 15 个点 */
const RANGES = [['1M',21],['3M',63],['6M',126],['1Y',250],['5Y',0]];

function zRange(arr,i0,i1){                       /* 窗口内 min/max，跳过 null */
  let m=Infinity,M=-Infinity;
  for(let i=i0;i<=i1;i++){const v=arr[i];
    if(v===null||v===undefined||isNaN(v))continue;
    if(v<m)m=v; if(v>M)M=v;}
  if(!isFinite(m)){m=0;M=1;}
  if(M-m<1e-9)M=m+1;
  return [m,M];
}

/* 通用缩放控制器：滚轮以光标位置为锚点缩放 / 按住拖拽平移 / 双击回到 1 年 */
function attachZoom(el,view,N,render,padL,padR){
  const pL=(padL===undefined?64:padL), pR=(padR===undefined?64:padR);
  el.addEventListener('wheel',ev=>{
    ev.preventDefault();
    const n=view.i1-view.i0+1;
    const rc=el.getBoundingClientRect();
    const px=(ev.clientX-rc.left)/rc.width*1000;
    const frac=Math.min(1,Math.max(0,(px-pL)/Math.max(1,(1000-pL-pR))));
    const anchor=view.i0+frac*(n-1);
    let nn=Math.round(n*(ev.deltaY>0?1.25:0.8));
    nn=Math.max(Math.min(ZMIN,N),Math.min(N,nn));
    const r=n>1?(anchor-view.i0)/(n-1):0.5;
    let i0=Math.round(anchor-r*(nn-1)), i1=i0+nn-1;
    if(i0<0){i0=0;i1=nn-1;}
    if(i1>N-1){i1=N-1;i0=i1-nn+1;}
    view.i0=Math.max(0,i0); view.i1=Math.min(N-1,i1); render();
  },{passive:false});

  let drag=null;
  el.addEventListener('mousedown',ev=>{
    drag={x:ev.clientX,i0:view.i0,i1:view.i1};
    el.classList.add('drag'); ev.preventDefault();
  });
  window.addEventListener('mousemove',ev=>{
    if(!drag)return;
    const rc=el.getBoundingClientRect();
    const per=(1000-pL-pR)/Math.max(1,(drag.i1-drag.i0));
    const dn=Math.round((drag.x-ev.clientX)/rc.width*1000/per);
    let a=drag.i0+dn, b=drag.i1+dn;
    if(a<0){b-=a;a=0;}
    if(b>N-1){a-=b-(N-1);b=N-1;}
    view.i0=Math.max(0,a); view.i1=Math.min(N-1,b); render();
  });
  window.addEventListener('mouseup',()=>{ if(drag){drag=null; el.classList.remove('drag');} });
  el.addEventListener('dblclick',()=>{ view.i1=N-1; view.i0=Math.max(0,N-250); render(); });
}

function drawTrack(key){
  const T = D.tracks[key];
  const S = T.summary, N = T.dates.length;
  const W=1000,H=380,L=64,R=64,Tp=14,B=30;
  const W2=1000,H2=170,L2=64,R2=64,T2=10,B2=26;
  const view={i0:Math.max(0,N-250),i1:N-1};

  const blk = document.createElement('div');
  blk.className='panel';
  let btns='';
  for(const rg of RANGES) btns+='<button class="zbtn" data-len="'+rg[1]+'">'+rg[0]+'</button>';
  btns+='<button class="zbtn" data-len="-1" title="回到最近一年">复位</button>';
  blk.innerHTML =
    '<h2>' + esc(S.title) + ' · ' + esc(S.labels.div_title) + '（悬停查看每日明细）</h2>' +
    '<div class="legend"><span><i style="background:var(--orange)"></i>' + esc(S.labels.hold) + '（左轴）</span>' +
    '<span><i style="background:var(--purple)"></i>' + S.index_name + ' 收盘价（右轴）</span></div>' +
    '<div class="zbar">' + btns + '<span class="zhint">滚轮缩放 · 按住拖拽平移 · 双击复位</span>' +
    '<span class="zrange"></span></div>' +
    '<svg class="zc tracksvg" viewBox="0 0 1000 380"></svg>' +
    '<div class="tip"></div>' +
    '<h2 style="margin-top:10px">开口差值 Spread = 占比分位 − 指数分位</h2>' +
    '<div class="hint">红柱：橙线强于紫线（持仓相对抬升）　绿柱：紫线强于橙线（指数相对虚高）　橙虚线：±25 劈叉预警阈值</div>' +
    '<svg class="zc spsvg" viewBox="0 0 1000 170"></svg>' +
    '<div class="reason" style="margin:12px 0 0"><b>今日诊断（' + S.date + '）：</b>' + esc(S.reason) + '</div>';
  $('trackBlocks').appendChild(blk);

  const svg=blk.querySelector('.tracksvg'), svg2=blk.querySelector('.spsvg');
  const tip=blk.querySelector('.tip'), zr=blk.querySelector('.zrange');
  let G=null;

  function render(){
    const n=view.i1-view.i0+1;
    const X=i=>n>1?L+(i-view.i0)*(W-L-R)/(n-1):(L+W-R)/2;

    /* 两条线各自按「当前窗口」重新定标，缩到哪段就看哪段的形状 */
    const hm=zRange(T.hold,view.i0,view.i1), im=zRange(T.idx,view.i0,view.i1);
    const top=Tp+10, bot=H-B-8, hh=bot-top;
    const YH=[],YI=[];
    for(let i=view.i0;i<=view.i1;i++){
      YH[i]=top+(hm[1]-T.hold[i])/(hm[1]-hm[0])*hh;
      YI[i]=top+(im[1]-T.idx[i])/(im[1]-im[0])*hh;
    }
    let g='';
    for(let k=0;k<=4;k++){const y=top+k*hh/4;
      g+='<line x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" stroke="#2A2F39" stroke-width="1"/>';}
    let axis='';
    for(let k=0;k<=4;k++){const f=k/4,y=top+f*hh;
      axis+='<text x="'+(L-8)+'" y="'+(y+4)+'" fill="#8A93A3" font-size="10.5" text-anchor="end" font-family="Consolas">'+(hm[1]-f*(hm[1]-hm[0])).toFixed(3)+'</text>';
      axis+='<text x="'+(W-R+8)+'" y="'+(y+4)+'" fill="#8A93A3" font-size="10.5" font-family="Consolas">'+(im[1]-f*(im[1]-im[0])).toFixed(0)+'</text>';}
    let xt='';
    const step=Math.max(1,Math.ceil(n/9));
    for(let i=view.i0;i<=view.i1;i+=step){
      xt+='<text x="'+X(i)+'" y="'+(H-8)+'" fill="#8A93A3" font-size="10.5" text-anchor="middle" font-family="Consolas">'+T.dates[i].slice(0,7)+'</text>';}
    let sh='';
    for(let i=Math.max(view.i0,1);i<=view.i1;i++){
      if(Math.abs(T.spread[i])>=25)
        sh+='<rect x="'+X(i-1)+'" y="'+Tp+'" width="'+Math.max(1.2,X(i)-X(i-1)+1)+'" height="'+(H-B-Tp)+'" fill="'+(T.spread[i]>0?'#E8453C':'#1FB37A')+'" opacity="0.07"/>';}
    const pth=ys=>{let s='';for(let i=view.i0;i<=view.i1;i++){s+=(i===view.i0?'M':'L')+X(i).toFixed(1)+' '+ys[i].toFixed(1);}return s;};
    svg.innerHTML=g+sh+
      '<line x1="'+L+'" y1="'+(H-B)+'" x2="'+(W-R)+'" y2="'+(H-B)+'" stroke="#2A2F39"/>'+
      '<path d="'+pth(YI)+'" fill="none" stroke="#9B6BFF" stroke-width="2" opacity=".95"/>'+
      '<path d="'+pth(YH)+'" fill="none" stroke="#FF8A1F" stroke-width="2.4"/>'+axis+xt+
      '<line class="cross" x1="0" y1="'+Tp+'" x2="0" y2="'+(H-B)+'" stroke="#8A93A3" stroke-width="1" stroke-dasharray="3 3" opacity="0"/>'+
      '<circle class="dotH" r="4" fill="#FF8A1F" stroke="#181A20" stroke-width="1.5" opacity="0"/>'+
      '<circle class="dotI" r="4" fill="#9B6BFF" stroke="#181A20" stroke-width="1.5" opacity="0"/>';

    /* Spread 副图：阈值 0 轴永远留在视野内，缩小时不会把 ±25 线挤出画面 */
    const sm=zRange(T.spread,view.i0,view.i1);
    const lo=Math.min(sm[0],-25,0), hi=Math.max(sm[1],25,0);
    const Y2=v=>T2+(hi-v)/((hi-lo)||1)*(H2-B2-T2);
    const X2=i=>n>1?L2+(i-view.i0)*(W2-L2-R2)/(n-1):(L2+W2-R2)/2;
    let gl='';
    for(let k=0;k<=4;k++){const y=T2+k*(H2-B2-T2)/4;
      gl+='<line x1="'+L2+'" y1="'+y+'" x2="'+(W2-R2)+'" y2="'+y+'" stroke="#2A2F39" stroke-width="1"/>';}
    const bw=Math.max(1,(W2-L2-R2)/n*0.7);
    let bars='';
    for(let i=view.i0;i<=view.i1;i++){
      const v=T.spread[i]||0,y0=Y2(0),y1=Y2(v);
      bars+='<rect x="'+(X2(i)-bw/2)+'" y="'+Math.min(y0,y1)+'" width="'+bw+'" height="'+Math.max(Math.abs(y1-y0),0.6)+'" fill="'+(v>=0?'#E8453C':'#1FB37A')+'" opacity="0.72"/>';}
    let thr='';
    for(const t of [25,-25]){
      thr+='<line x1="'+L2+'" y1="'+Y2(t)+'" x2="'+(W2-R2)+'" y2="'+Y2(t)+'" stroke="#F5A623" stroke-width="1" stroke-dasharray="5 4" opacity="0.75"/>'+
      '<text x="'+(W2-R2+6)+'" y="'+(Y2(t)+4)+'" fill="#F5A623" font-size="10" font-family="Consolas">'+(t>0?'+':'')+t+'</text>';}
    let spAxis='';
    for(let k=0;k<=4;k++){const f=k/4,y=T2+f*(H2-B2-T2);
      spAxis+='<text x="'+(L2-8)+'" y="'+(y+4)+'" fill="#8A93A3" font-size="10.5" text-anchor="end" font-family="Consolas">'+(hi-f*(hi-lo)).toFixed(0)+'</text>';}
    svg2.innerHTML=gl+bars+'<line x1="'+L2+'" y1="'+Y2(0)+'" x2="'+(W2-R2)+'" y2="'+Y2(0)+'" stroke="#4a5160"/>'+thr+spAxis;

    G={X:X,YH:YH,YI:YI,n:n};
    zr.textContent='当前 '+n+' 个交易日：'+T.dates[view.i0]+' ~ '+T.dates[view.i1]+'（共 '+N+' 天）';
    for(const b of blk.querySelectorAll('.zbtn')){
      const len=Number(b.dataset.len);
      const on = len<0 ? false : (len===0 ? n===N : len===n);   /* 复位按钮不参与高亮 */
      b.classList.toggle('on',on);
    }
  }

  function setLen(len){
    if(len===-1){view.i1=N-1;view.i0=Math.max(0,N-250);}
    else if(len<=0||len>=N){view.i0=0;view.i1=N-1;}
    else {view.i1=N-1;view.i0=Math.max(0,N-len);}
    render();
  }
  for(const b of blk.querySelectorAll('.zbtn')) b.addEventListener('click',()=>setLen(Number(b.dataset.len)));
  attachZoom(svg,view,N,render,L,R);
  attachZoom(svg2,view,N,render,L2,R2);

  svg.addEventListener('mousemove',ev=>{
    if(!G)return;
    const rc=svg.getBoundingClientRect();
    const px=(ev.clientX-rc.left)/rc.width*1000;
    let i=view.i0+Math.round((px-L)/Math.max(1,(W-L-R))*(G.n-1));
    i=Math.max(view.i0,Math.min(view.i1,i));
    const x=G.X(i);
    const cross=svg.querySelector('.cross'),dH=svg.querySelector('.dotH'),dI=svg.querySelector('.dotI');
    if(cross){cross.setAttribute('x1',x);cross.setAttribute('x2',x);cross.setAttribute('opacity','.7');}
    if(dH){dH.setAttribute('cx',x);dH.setAttribute('cy',G.YH[i]);dH.setAttribute('opacity','1');}
    if(dI){dI.setAttribute('cx',x);dI.setAttribute('cy',G.YI[i]);dI.setAttribute('opacity','1');}
    let rows='';
    for(const kk in T.names){const c=T.chg[kk][i];
      rows+='<div style="display:flex;justify-content:space-between;gap:14px"><span style="color:#8A93A3">'+esc(T.names[kk])+
        '</span><span>'+fmt(T.shares[kk][i],2)+' 亿份 <span class="'+(c>=0?'pos':'neg')+'">'+sign(c,2)+'</span></span></div>';}
    tip.innerHTML='<b>'+T.dates[i]+'</b><div style="color:var(--orange)">持仓占比 '+fmt(T.hold[i],4)+'%</div>'+
      '<div style="color:var(--purple)">'+S.index_name+' '+fmt(T.idx[i],2)+'</div>'+
      '<div style="color:var(--blue)">Spread '+sign(T.spread[i],1)+'</div><div style="margin-top:5px">'+rows+'</div>';
    tip.style.display='block';
    const br=blk.getBoundingClientRect();
    let lx=ev.clientX-br.left+16;
    if(lx+240>br.width) lx=ev.clientX-br.left-236;
    tip.style.left=lx+'px'; tip.style.top=(ev.clientY-br.top+14)+'px';
  });
  svg.addEventListener('mouseleave',()=>{
    tip.style.display='none';
    for(const c of svg.querySelectorAll('.cross,.dotH,.dotI')) c.setAttribute('opacity','0');
  });

  render();
}
D.order.forEach(drawTrack);

/* ---------- 三大比价 ---------- */
if (D.ratios && D.ratios.items) {
  $('ratioPanel').style.display='';
  let h='';
  for (const k of D.ratios.order) {
    const it = D.ratios.items[k]; if(!it) continue;
    const col = it.level==='high' ? 'var(--up)' : (it.level==='low' ? 'var(--down)' : '#8A93A3');
    h += '<div class="rbox"><div class="t">'+esc(it.title)+'</div><div class="fm">'+esc(it.formula)+'</div>'+
      '<div class="barwrap"><div class="lo"></div><div class="hi"></div><div class="mk" style="left:'+it.pct.toFixed(1)+'%"></div></div>'+
      '<div class="kv"><span>当前比值 <b style="color:#fff;font-family:Consolas">'+it.cur.toFixed(4)+'</b></span>'+
      '<span style="color:'+col+';font-weight:700">分位 '+it.pct.toFixed(1)+'% · '+esc(it.word)+'</span></div>'+
      '<div class="kv" style="margin-top:5px"><span>近1年 '+sign(it.chg_y,2)+'%　近1季 '+sign(it.chg_q,2)+'%　近1月 '+sign(it.chg_m,2)+'%</span>'+
      '<span>20分位 '+it.q20.toFixed(4)+'｜80分位 '+it.q80.toFixed(4)+'</span></div>'+
      '<div style="margin-top:8px;font-size:12.4px;color:'+col+'"><b>'+esc(it.label)+'</b></div>'+
      '<div class="fm" style="margin-top:3px">'+esc(it.advice)+'</div>'+
      '<div class="fm">覆盖 '+it.n+' 周（约 '+it.years+' 年，'+it.start+' ~ '+it.end+'）　配置倾向：<b style="color:#F5A623">'+esc(it.tilt)+'</b></div></div>';
  }
  $('ratioCards').innerHTML = h;
}

/* ---------- LSI vs GLI 走势图（对应监测图行 3，可缩放） ---------- */
function drawLsi(){
  const L = D.lsi;
  if (!L || !L.hist || !L.cal) return;
  const h = L.hist;
  const cal = L.cal;
  const lsiAll = h.lsi || [], gliAll = h.gli || [];
  const rrpTAll = h.rrp_T || [], rrpPAll = h.rrp_pct || [];
  const cdAll = h.credit || [], impAll = h.impulse || [];
  const N = Math.min(cal.length, lsiAll.length, gliAll.length);
  if (N < 5) return;
  const view = {i0: Math.max(0, N-260), i1: N-1};   /* 默认展示最近约一年，可缩到全历史 */

  const W=1000,H=360,Lf=62,R=66,Tp=14,B=30;
  const el = $('lsiChart');

  /* 区间按钮 */
  const zb = $('lsiZbar');
  let btns='';
  for(const rg of RANGES) btns+='<button class="zbtn" data-len="'+rg[1]+'">'+rg[0]+'</button>';
  btns+='<button class="zbtn" data-len="-1" title="回到最近一年">复位</button>';
  zb.innerHTML = btns + '<span class="zhint">滚轮缩放 · 按住拖拽平移 · 双击复位</span><span class="zrange"></span>';
  const zr = zb.querySelector('.zrange');

  let G=null;
  function render(){
    const i0=view.i0, i1=view.i1, n=i1-i0+1;
    const X=i=>Lf+(i-i0)*(W-Lf-R)/Math.max(1,(n-1));
    /* 左右轴都按当前窗口定标；左轴额外纳入三条阈值线，保证阈值始终可见 */
    let lw=[];
    for(let i=i0;i<=i1;i++){const v=lsiAll[i]; if(v!==null&&v!==undefined) lw.push(v);}
    lw=lw.concat([20,50,-30]);
    const lMin=Math.min.apply(null,lw), lMax=Math.max.apply(null,lw);
    const yL=v=>Tp+10+(lMax-v)/((lMax-lMin)||1)*(H-B-8-Tp-10);
    let gw=[];
    for(let i=i0;i<=i1;i++){const v=gliAll[i]; if(v!==null&&v!==undefined) gw.push(v);}
    if(!gw.length) gw=[0,1];
    const gMin=Math.min.apply(null,gw), gMax=Math.max.apply(null,gw);
    const yG=v=>Tp+10+(gMax-v)/((gMax-gMin)||1)*(H-B-8-Tp-10);

    let g='';
    for(let k=0;k<=4;k++){const y=Tp+10+k*(H-B-8-Tp-10)/4;
      g+='<line x1="'+Lf+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" stroke="#2A2F39" stroke-width="1"/>';}
    /* 背景带：LSI≥20 偏紧(红)、≤-30 极端宽松(绿) */
    let sh='';
    for(let i=Math.max(i0,1);i<=i1;i++){
      const v=lsiAll[i]; if(v===null||v===undefined) continue;
      const col = v>=20 ? '#E8453C' : (v<=-30 ? '#1FB37A' : null);
      if(col) sh+='<rect x="'+X(i-1)+'" y="'+Tp+'" width="'+Math.max(1.2,X(i)-X(i-1)+1)+'" height="'+(H-B-Tp)+'" fill="'+col+'" opacity="0.07"/>';
    }
    let thr='';
    for(const t of [50,20,-30]){
      const y=yL(t), col = t===50?'#8B1A1A':(t===20?'#E8453C':'#1FB37A');
      /* 阈值标注放在图内左侧：右上方是 GLI 轴刻度，写在外面会和刻度数字叠在一起 */
      thr+='<line x1="'+Lf+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" stroke="'+col+'" stroke-width="1" stroke-dasharray="5 4" opacity="0.8"/>'+
        '<text x="'+(Lf+5)+'" y="'+(y-4)+'" fill="'+col+'" font-size="10" font-family="Consolas">'+(t>0?'+':'')+t+'</text>';
    }
    let axis='';
    for(let k=0;k<=4;k++){const f=k/4, y=Tp+10+f*(H-B-8-Tp-10);
      axis+='<text x="'+(Lf-8)+'" y="'+(y+4)+'" fill="#FF8A1F" font-size="10.5" text-anchor="end" font-family="Consolas">'+(lMax-f*(lMax-lMin)).toFixed(0)+'</text>';
      axis+='<text x="'+(W-R+8)+'" y="'+(y+4)+'" fill="#4C9AFF" font-size="10.5" font-family="Consolas">'+(gMax-f*(gMax-gMin)).toFixed(2)+'</text>';}
    let xt='';
    const step=Math.max(1,Math.ceil(n/9));
    for(let i=i0;i<=i1;i+=step){
      xt+='<text x="'+X(i)+'" y="'+(H-8)+'" fill="#8A93A3" font-size="10.5" text-anchor="middle" font-family="Consolas">'+String(cal[i]).slice(0,7)+'</text>';}

    const pth=(arr,yf)=>{let s='',pen=false;
      for(let i=i0;i<=i1;i++){const v=arr[i];
        if(v===null||v===undefined){pen=false;continue;}
        s+=(pen?'L':'M')+X(i).toFixed(1)+' '+yf(v).toFixed(1);pen=true;}
      return s;};

    el.innerHTML=g+sh+
      '<line x1="'+Lf+'" y1="'+(H-B)+'" x2="'+(W-R)+'" y2="'+(H-B)+'" stroke="#2A2F39"/>'+
      '<path d="'+pth(gliAll,yG)+'" fill="none" stroke="#4C9AFF" stroke-width="2.1" opacity=".95"/>'+
      '<path d="'+pth(lsiAll,yL)+'" fill="none" stroke="#FF8A1F" stroke-width="2.4"/>'+
      thr+axis+xt+
      '<line class="cross" x1="0" y1="'+Tp+'" x2="0" y2="'+(H-B)+'" stroke="#8A93A3" stroke-width="1" stroke-dasharray="3 3" opacity="0"/>'+
      '<circle class="dotL" r="4" fill="#FF8A1F" stroke="#181A20" stroke-width="1.5" opacity="0"/>'+
      '<circle class="dotG" r="4" fill="#4C9AFF" stroke="#181A20" stroke-width="1.5" opacity="0"/>';

    G={X:X,yL:yL,yG:yG,n:n};
    zr.textContent='当前 '+n+' 个观测日：'+cal[i0]+' ~ '+cal[i1]+'（共 '+N+' 天）';
    for(const b of zb.querySelectorAll('.zbtn')){
      const len=Number(b.dataset.len);
      const on = len<0 ? false : (len===0 ? n===N : len===n);   /* 复位按钮不参与高亮 */
      b.classList.toggle('on',on);
    }
  }

  function setLen(len){
    if(len===-1){view.i1=N-1;view.i0=Math.max(0,N-250);}
    else if(len<=0||len>=N){view.i0=0;view.i1=N-1;}
    else {view.i1=N-1;view.i0=Math.max(0,N-len);}
    render();
  }
  for(const b of zb.querySelectorAll('.zbtn')) b.addEventListener('click',()=>setLen(Number(b.dataset.len)));
  attachZoom(el,view,N,render,Lf,R);

  /* 悬停明细 */
  const tip=$('lsiTip');
  el.addEventListener('mousemove',ev=>{
    if(!G)return;
    const rc=el.getBoundingClientRect();
    const px=(ev.clientX-rc.left)/rc.width*1000;
    let i=view.i0+Math.round((px-Lf)/Math.max(1,(W-Lf-R))*(G.n-1));
    i=Math.max(view.i0,Math.min(view.i1,i));
    while(i>view.i0 && (lsiAll[i]===null||lsiAll[i]===undefined)) i--;
    const x=G.X(i);
    const cross=el.querySelector('.cross'),dL=el.querySelector('.dotL'),dG=el.querySelector('.dotG');
    if(cross){cross.setAttribute('x1',x);cross.setAttribute('x2',x);cross.setAttribute('opacity','.7');}
    if(dL && lsiAll[i]!==null && lsiAll[i]!==undefined){dL.setAttribute('cx',x);dL.setAttribute('cy',G.yL(lsiAll[i]));dL.setAttribute('opacity','1');}
    if(dG && gliAll[i]!==null && gliAll[i]!==undefined){dG.setAttribute('cx',x);dG.setAttribute('cy',G.yG(gliAll[i]));dG.setAttribute('opacity','1');}
    const lsiv=lsiAll[i], gliv=gliAll[i];
    const st=(lsiv===null||lsiv===undefined)?'—':
      (lsiv>=50?'极端紧张':(lsiv>=20?'偏紧':(lsiv<0?(lsiv<=-30?'极端宽松':'正常宽松'):'中性平衡')));
    tip.innerHTML='<b>'+String(cal[i])+'</b>'+
      '<div style="color:#FF8A1F">LSI '+fmt(lsiv,1)+' bps（'+st+'）</div>'+
      '<div style="color:#4C9AFF">GLI '+fmt(gliv,3)+' T</div>'+
      '<div style="color:#8A93A3">RRP '+fmt(rrpTAll[i],3)+' T（峰值占比 '+fmt(rrpPAll[i],1)+'%）</div>'+
      '<div style="color:#8A93A3">信用利差 '+fmt(cdAll[i],0)+' bps　冲量 '+sign(impAll[i],2)+'%</div>';
    tip.style.display='block';
    const pr=$('lsiPanel').getBoundingClientRect();
    let lx=ev.clientX-pr.left+16;
    if(lx+250>pr.width) lx=ev.clientX-pr.left-246;
    tip.style.left=lx+'px'; tip.style.top=(ev.clientY-pr.top+14)+'px';
  });
  el.addEventListener('mouseleave',()=>{
    tip.style.display='none';
    for(const c of el.querySelectorAll('.cross,.dotL,.dotG')) c.setAttribute('opacity','0');
  });

  render();
}
if (D.lsi) drawLsi();

/* ---------- LSI 核心面板 ---------- */
if (D.lsi) {
  const L = D.lsi, c = L.core;
  $('lsiPanel').style.display='';
  $('lsiHint').innerHTML = 'LSI = (SOFR − RRP利率) + (EFFR − IORB)，衡量美元体系<b>内部管道</b>压力；' +
    'GLI = WALCL − WTREGEN − RRPONTSYD，衡量美联储<b>净流动性总量</b>水位。' +
    '数据截至 <b>'+L.asof+'</b>　当前状态：<b>'+esc(L.state)+'</b>　报警 <b style="color:#E8453C">'+L.alert_count+'</b>/'+L.total+' 项。';
  const lsiCol = (gt(c.lsi,49.999)?'#8B1A1A':(gt(c.lsi,19.999)?'var(--up)':(lt(c.lsi,0)?'var(--down)':'var(--txt)')));
  let lh='';
  const kv = (k,v,d,col)=>'<div class="card"><div class="k">'+k+'</div><div class="v" style="color:'+(col||'var(--txt)')+'">'+v+'</div><div class="d">'+d+'</div></div>';
  lh += kv('LSI 压力指数', fmt(c.lsi,1)+' bp', 'SOFR−RRP + EFFR−IORB', lsiCol);
  lh += kv('SOFR / RRP 利率', fmt(d100(c.sofr),2)+' / '+fmt(d100(c.rrp_rate),2)+'%', '美元隔夜融资基准');
  lh += kv('EFFR / IORB', fmt(d100(c.effr),2)+' / '+fmt(d100(c.iorb),2)+'%', '有效联邦基金利率 / 准备金利率');
  lh += kv('GLI 净流动性', fmt(c.gli,3)+' T', 'WALCL '+fmt(c.walcl_T,3)+' − TGA '+fmt(c.wtregen_T,3)+' − RRP '+fmt(c.rrp_T,3), 'var(--blue)');
  lh += kv('GLI 250日分位阈值', fmt(c.gli_low_th,3)+' ~ '+fmt(c.gli_high_th,3), '25% / 75% 分位', 'var(--sub)');
  lh += kv('GLI 20日变化', sign(c.tlc,2)+'%', '骤减阈值 < −1.00%', lt(c.tlc,-1)? 'var(--up)' : 'var(--down)');
  lh += kv('流动性冲量', sign(c.impulse,2)+'%', '连续3日回落即报警', gt(c.impulse,0)?'var(--down)':'var(--up)');
  lh += kv('RRP 余额 / 峰值占比', fmt(c.rrp_T,3)+' T / '+fmt(c.rrp_pct,1)+'%', '枯竭阈值 <5% 或 <0.1T', c.rrp_pct<5?'var(--up)':'var(--down)');
  lh += kv('银行准备金', fmt(c.wrb_T,3)+' T', '占GDP '+fmt(c.reserve_gdp,2)+'%｜占银行总资产 '+fmt(c.reserve_assets,2)+'%',
           (c.reserve_gdp<11 && c.reserve_assets<11)?'var(--up)':'var(--down)');
  lh += kv('10Y 实际利率 DFII10', fmt(d100(c.dfii10),2)+'%', '紧缩 >2.20%｜极宽 <0.00%',
           gt(c.dfii10,220)?'var(--up)':(lt(c.dfii10,0)?'var(--down)':'var(--txt)'));
  lh += kv('信用利差 OAS', fmt(d100(c.credit),2)+'%', '动量 '+sign(c.credit_roc,2)+'%｜危机 >4.00%',
           gt(c.credit,400)?'var(--up)':'var(--down)');
  lh += kv('10Y−2Y 利差', sign(c.yield_spread,1)+' bp', 'US10Y '+fmt(d100(c.us10y),2)+'%｜US02Y '+fmt(d100(c.us02y),2)+'%',
           c.yield_spread<0?'#F5A623':'var(--down)');
  lh += kv('T10YIE / CPI YoY', fmt(d100(c.t10yie),2)+'% / '+fmt(d100(c.cpi_yoy),2)+'%', '偏差阈值 >0.90%',
           (c.t10yie!==null&&c.cpi_yoy!==null&&Math.abs(c.t10yie-c.cpi_yoy)>90)?'var(--up)':'var(--down)');
  lh += kv('广义美元指数', fmt(c.dxy,2), 'MA50 = '+fmt(c.dxy_ma,2)+'｜强美元阈值 > MA50',
           gt(c.dxy,c.dxy_ma)?'var(--up)':'var(--down)');
  $('lsiCards').innerHTML = lh;

  const f = L.flow;
  $('flowBox').innerHTML =
    '<h2 style="margin-top:6px">V57 资金流向雷达（近 10 个观测日，单位 Billion 美元）</h2>' +
    '<div class="hint">监测 TGA / 外国官方逆回购 / 国内逆回购 三个渠道的净抽水与净放水，有效动作过滤阈值 ±'+f.threshold+'B。</div>' +
    '<div class="reason" style="border-left-color:#F5A623"><b>最大抽水：</b>'+esc(f.drain_str)+'　<b>最大放水：</b>'+esc(f.inject_str)+
    '<br><b>三渠道净流量：</b>'+esc(f.net_desc)+
    '<br>' + f.items.map(x=>esc(x.name)+' '+sign(x.delta_b,2)+'B').join('　｜　') + '</div>';
}

/* ---------- 20 项报警明细表 ---------- */
if (D.lsi && D.lsi.alerts) {
  $('alertPanel').style.display='';
  const cols = ['序号','分类','报警项目名称','原始数据明细','计算公式','当前计算结果','代码报警阈值','当前是否报警'];
  let h = '<thead><tr>' + cols.map(c=>'<th>'+c+'</th>').join('') + '</tr></thead><tbody>';
  for (const a of D.lsi.alerts) {
    const cls = a.alert ? 'alert-on' : 'alert-off';
    const txt = a.alert ? '🚨 报警（已触发）' : '✅ 正常（未触发）';
    h += '<tr>' +
      '<td>'+a.no+'</td>' +
      '<td>'+esc(a.cat)+'</td>' +
      '<td style="font-family:inherit">'+esc(a.name)+'</td>' +
      '<td class="raw">'+esc(a.raw)+'</td>' +
      '<td class="fm">'+esc(a.formula)+'</td>' +
      '<td class="'+cls+'">'+esc(a.result)+'</td>' +
      '<td class="fm">'+esc(a.threshold)+'</td>' +
      '<td class="'+cls+'">'+txt+'</td></tr>';
  }
  h += '</tbody>';
  $('alertTbl').innerHTML = h;
  $('excludedNote').innerHTML = '<b>已剔除的 TradingView 私有数据项（FRED 无免费接口）：</b><br>' +
    D.lsi.excluded.map(x=>'· '+esc(x)).join('<br>');
}

/* ---------- 宽松状态 ---------- */
if (D.lsi && D.lsi.loose) {
  $('loosePanel').style.display='';
  let h = '<thead><tr><th>状态名称</th><th>当前计算结果</th><th>触发阈值</th><th>当前是否成立</th></tr></thead><tbody>';
  for (const a of D.lsi.loose) {
    h += '<tr><td style="font-family:inherit">'+esc(a.name)+'</td><td>'+esc(a.result)+'</td>' +
      '<td class="fm">'+esc(a.threshold)+'</td>' +
      '<td class="'+(a.on?'alert-off':'alert-on')+'">'+(a.on?'✅ 成立（宽松）':'— 未成立')+'</td></tr>';
  }
  $('looseTbl').innerHTML = h + '</tbody>';
}

/* ---------- 四维诊断 ---------- */
if (D.lsi && D.lsi.diag) {
  $('diagPanel').style.display='';
  const d = D.lsi.diag;
  const box = (t, s) => '<div class="diag"><span class="h">'+t+'</span><br>'+esc(s)+'</div>';
  $('diagBox').innerHTML = box('🔍 资金动态与净流向定量穿透', d.flow)
    + box('【一阶】宏观周期与债务周期', d.level1)
    + box('【二阶】流动性矩阵与底层水位', d.level2)
    + box('【三阶】微观定价与风险溢价', d.level3);
}

/* ---------- 近5日份额明细 ---------- */
let sh = '';
for (const k of D.order) {
  const T = D.tracks[k], S = T.summary;
  const rows = S.share_rows || [];
  const syms = Object.keys(T.names);
  let h = '<thead><tr><th>日期</th>' + syms.map(s=>'<th>'+esc(T.names[s])+'</th>').join('') +
          '<th>四只合计（亿份）</th></tr></thead><tbody>';
  for (const r of rows) {
    h += '<tr><td>'+r.date+'</td>';
    for (const s of syms) {
      const v = r.shares[s], c = r.chg[s];
      h += '<td>'+(v? (v/1e8).toFixed(3) : '—')+' <span class="'+(c>=0?'pos':'neg')+'">'+
           (c===null||c===undefined?'—':(c>=0?'+':'')+(c/1e8).toFixed(3))+'</span></td>';
    }
    h += '<td>'+(r.total_shares?(r.total_shares/1e8).toFixed(2):'—')+'</td></tr>';
  }
  h += '</tbody>';
  sh += '<div class="panel"><h2>'+esc(S.labels.share_tbl)+'（亿份，括号内为当日增减）</h2>' +
    '<div class="hint">份额为基金端 T+1~T+2 披露值；脚本会识别并剔除「沿用上次披露值」的尾部交易日（当前截断至 ' +
    esc(S.shares_asof||'—') + (S.stale_tail?('，已剔除 '+S.stale_tail+' 个未披露日'):'') + '）。</div>' +
    '<div style="overflow-x:auto"><table>'+h+'</table></div></div>';
}
$('shareBlocks').innerHTML = sh;

/* ══════════ ⑨ 境内资金面 ══════════ */
(function renderCnLiquidity(){
  const S = D.signals;
  if (!S || !S.liquidity) return;
  const L = S.liquidity;
  let rows = (L.data || []).filter(r => r && r.date);
  // 中国货币网两个接口的回溯长度不一样：SHIBOR 能给到 60+ 天，而回购定盘（DR007）
  // 只回最近约 1 个月且忽略 startDate。若照原样从头画，左侧会有一大段
  // 「只有 SHIBOR、没有 DR007」的空白，主次颠倒。从首个 DR007 有效点起画。
  let i0 = -1;
  for (let i = 0; i < rows.length; i++) {
    if (rows[i].dr007 !== null && rows[i].dr007 !== undefined) { i0 = i; break; }
  }
  if (i0 > 0) rows = rows.slice(i0);
  if (rows.length < 5) return;
  $('liqCnPanel').style.display = '';

  const lt = L.latest || {}, dv = L.derived || {};
  $('liqCnHint').innerHTML = '银行间资金价格，单位为年化 %。DR007 是央行公开市场操作实际盯的锚，'
    + '比 SHIBOR 更能代表真实资金面 —— <b>曲线下行＝资金转松，上行＝收紧</b>。'
    + '⑨ 与 ⑤ 合起来才是完整流动性环境：⑤ 看境外（美联储），⑨ 看境内。'
    + (lt.date ? '　最新 ' + esc(lt.date) : '')
    + '　<b>数据源：中国货币网</b>（SHIBOR 八期限 + 银行间质押式回购定盘 FR/FDR）。';

  const bp = v => (v === null || v === undefined) ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(1) + ' bp';
  // 资金利率上行＝收紧＝红；下行＝转松＝绿（沿用 A 股红涨绿跌）
  const bpCol = v => (v === null || v === undefined) ? 'var(--sub)' : (v > 0 ? 'var(--up)' : (v < 0 ? 'var(--down)' : 'var(--txt)'));

  let ch = '';
  ch += '<div class="card"><div class="k">DR007 · 7天回购定盘</div>'
      + '<div class="v" style="color:var(--orange)">' + fmt(lt.dr007, 3) + '%</div>'
      + '<div class="d">20 日均 ' + fmt(dv.dr007_ma20, 3) + '｜偏离 <span style="color:' + bpCol(dv.dr007_vs_ma20_bp) + '">'
      + bp(dv.dr007_vs_ma20_bp) + '</span></div></div>';
  ch += '<div class="card"><div class="k">DR001 · 隔夜</div>'
      + '<div class="v" style="color:var(--cyan)">' + fmt(lt.dr001, 3) + '%</div>'
      + '<div class="d">FR001 ' + fmt(lt.fr001, 3) + '%｜5 日 DR007 <span style="color:' + bpCol(dv.dr007_chg_5d_bp) + '">'
      + bp(dv.dr007_chg_5d_bp) + '</span></div></div>';
  ch += '<div class="card"><div class="k">SHIBOR 3M · 中期资金成本</div>'
      + '<div class="v" style="color:var(--blue)">' + fmt(lt.shibor_3m, 3) + '%</div>'
      + '<div class="d">20 日变化 <span style="color:' + bpCol(dv.shibor_3m_chg_20d_bp) + '">'
      + bp(dv.shibor_3m_chg_20d_bp) + '</span>｜1Y ' + fmt(lt.shibor_1y, 3) + '%</div></div>';
  ch += '<div class="card"><div class="k">期限利差 3M − 隔夜</div>'
      + '<div class="v" style="color:var(--txt)">' + bp(dv.term_spread_3m_on_bp) + '</div>'
      + '<div class="d">走阔＝机构提前备付、资金预期偏紧</div></div>';
  $('liqCnCards').innerHTML = ch;

  const W = 1000, H = 300, Lf = 54, R = 78, Tp = 14, B = 30;
  const n = rows.length;
  const X = i => Lf + i * (W - Lf - R) / Math.max(1, n - 1);
  const series = [
    {key: 'dr007', name: 'DR007', col: '#FF8A1F', w: 2.2},
    {key: 'shibor_3m', name: 'SHIBOR 3M', col: '#4C9AFF', w: 1.6},
    {key: 'shibor_on', name: '隔夜', col: '#8A93A3', w: 1.2, dash: '4 3'}
  ];
  let vals = [];
  for (const s of series) for (const r of rows) {
    const v = r[s.key];
    if (v !== null && v !== undefined && !isNaN(v)) vals.push(v);
  }
  if (!vals.length) return;
  let mn = Infinity, mx = -Infinity;
  for (const v of vals) { if (v < mn) mn = v; if (v > mx) mx = v; }
  const pd0 = (mx - mn) * 0.2 || 0.05; mn -= pd0; mx += pd0;
  const Y = v => Tp + (mx - v) / (mx - mn) * (H - B - Tp);

  let g = '';
  for (let k = 0; k <= 4; k++) {
    const y = Tp + k * (H - B - Tp) / 4, v = mx - (mx - mn) * k / 4;
    g += '<line x1="' + Lf + '" y1="' + y + '" x2="' + (W - R) + '" y2="' + y + '" stroke="#2A2F39" stroke-width="1"/>'
      + '<text x="' + (Lf - 8) + '" y="' + (y + 4) + '" fill="#8A93A3" font-size="10.5" text-anchor="end" '
      + 'font-family="Consolas">' + v.toFixed(2) + '</text>';
  }
  for (const s of series) {
    let d = '', on = false;
    for (let i = 0; i < n; i++) {
      const v = rows[i][s.key];
      if (v === null || v === undefined || isNaN(v)) { on = false; continue; }
      d += (on ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1) + ' ';
      on = true;
    }
    if (!d) continue;
    g += '<path d="' + d + '" fill="none" stroke="' + s.col + '" stroke-width="' + s.w + '"'
      + (s.dash ? ' stroke-dasharray="' + s.dash + '"' : '') + ' stroke-linejoin="round"/>';
    const lr = rows[n - 1];
    if (lr && lr[s.key] !== null && lr[s.key] !== undefined) {
      g += '<circle cx="' + X(n - 1) + '" cy="' + Y(lr[s.key]) + '" r="3" fill="' + s.col + '"/>'
        + '<text x="' + (X(n - 1) + 7) + '" y="' + (Y(lr[s.key]) + 4) + '" fill="' + s.col
        + '" font-size="11" font-family="Consolas">' + s.name + '</text>';
    }
  }
  g += '<text x="' + Lf + '" y="' + (H - 8) + '" fill="#6b7484" font-size="10.5" font-family="Consolas">' + esc(rows[0].date) + '</text>'
    + '<text x="' + (W - R) + '" y="' + (H - 8) + '" fill="#6b7484" font-size="10.5" text-anchor="end" font-family="Consolas">' + esc(rows[n - 1].date) + '</text>';
  $('liqCnChart').innerHTML = g;
})();

/* ══════════ ⑩ 市场宽度 ══════════ */
(function renderBreadth(){
  const S = D.signals;
  if (!S || !S.breadth) return;
  const BR = S.breadth, t = BR.today || {};
  if (!t.total) return;
  $('breadthPanel').style.display = '';

  $('breadthHint').innerHTML = '涨跌家数由「涨跌幅分布直方图」求和得到（已与东财 push2 的 f104/f105/f106 交叉校验，差异 <2%，'
    + '源于是否含北交所与停牌股）；涨停/跌停取涨停池、跌停池的 tc 字段；最高连板高度取池内 lbc 最大值。'
    + '<b>上游三个接口只返回当日快照、不支持按日期查询</b>，所以本仓库只能每天存一份，历史序列从上线当天开始积累。'
    + (t.is_today ? '　<span style="color:#F5A623">当日为盘中实时值，收盘前会变动</span>' : '');

  const card = (k, v, col, d) => '<div class="card"><div class="k">' + k + '</div>'
    + '<div class="v" style="color:' + col + '">' + v + '</div><div class="d">' + d + '</div></div>';
  let ch = '';
  ch += card('上涨家数', t.up, 'var(--up)', '占比 ' + fmt(t.up_pct, 1) + '%');
  ch += card('下跌家数', t.down, 'var(--down)', '平盘 ' + (t.flat === null || t.flat === undefined ? '—' : t.flat) + ' 家');
  ch += card('涨停 / 跌停', (t.limit_up === null ? '—' : t.limit_up) + ' / ' + (t.limit_down === null ? '—' : t.limit_down),
    'var(--orange)', '涨停家数含一字板与新上市');
  ch += card('最高连板', (t.max_streak || 0) + ' 板', 'var(--purple)', '连板高度＝情绪温度计');
  $('breadthCards').innerHTML = ch;

  const tot = t.total || 1;
  const pw = x => (x / tot * 100).toFixed(2);
  $('breadthBar').innerHTML =
    '<div class="wbar">'
    + '<div style="width:' + pw(t.up) + '%;background:#E8453C">' + (t.up / tot > 0.08 ? t.up : '') + '</div>'
    + '<div style="width:' + pw(t.flat) + '%;background:#6b7484">' + (t.flat / tot > 0.08 ? t.flat : '') + '</div>'
    + '<div style="width:' + pw(t.down) + '%;background:#1FB37A">' + (t.down / tot > 0.08 ? t.down : '') + '</div>'
    + '</div>'
    + '<div class="wleg"><span><i style="background:#E8453C"></i>上涨 ' + t.up + '</span>'
    + '<span><i style="background:#6b7484"></i>平盘 ' + t.flat + '</span>'
    + '<span><i style="background:#1FB37A"></i>下跌 ' + t.down + '</span>'
    + '<span>合计 ' + t.total + ' 只（' + esc(t.date || '') + '）</span></div>';

  const hist = (BR.history || []).filter(r => r && r.up_pct !== null && r.up_pct !== undefined);
  if (hist.length < 5) {
    // 历史不够时不占 220px 的大空白，收成一条 90px 的说明条，页面更紧凑
    $('breadthChart').setAttribute('viewBox', '0 0 1000 90');
    $('breadthChart').innerHTML = '<text x="500" y="46" fill="#6b7484" font-size="12" text-anchor="middle">'
      + '历史仅 ' + hist.length + ' 天，满 5 天后自动显示「上涨占比」趋势（每次运行累积一天，也可本地补跑）</text>';
    return;
  }
  $('breadthChart').setAttribute('viewBox', '0 0 1000 220');
  const W = 1000, H = 220, Lf = 48, R = 60, Tp = 14, B = 26;
  const n = hist.length;
  const X = i => Lf + i * (W - Lf - R) / Math.max(1, n - 1);
  const Y = v => Tp + (100 - v) / 100 * (H - B - Tp);
  let g = '';
  for (let k = 0; k <= 4; k++) {
    const y = Tp + k * (H - B - Tp) / 4, v = 100 - 25 * k;
    g += '<line x1="' + Lf + '" y1="' + y + '" x2="' + (W - R) + '" y2="' + y + '" stroke="#2A2F39" stroke-width="1"/>'
      + '<text x="' + (Lf - 8) + '" y="' + (y + 4) + '" fill="#8A93A3" font-size="10.5" text-anchor="end" '
      + 'font-family="Consolas">' + v + '%</text>';
  }
  g += '<line x1="' + Lf + '" y1="' + Y(50) + '" x2="' + (W - R) + '" y2="' + Y(50) + '" stroke="#6b7484" stroke-width="1" stroke-dasharray="4 3"/>';
  let d = '';
  for (let i = 0; i < n; i++) d += (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(hist[i].up_pct).toFixed(1) + ' ';
  g += '<path d="' + d + '" fill="none" stroke="#E8453C" stroke-width="2" stroke-linejoin="round"/>';
  const lr = hist[n - 1];
  g += '<circle cx="' + X(n - 1) + '" cy="' + Y(lr.up_pct) + '" r="3.5" fill="#E8453C"/>'
    + '<text x="' + (X(n - 1) + 7) + '" y="' + (Y(lr.up_pct) + 4) + '" fill="#E8453C" font-size="11" '
    + 'font-family="Consolas">' + fmt(lr.up_pct, 1) + '%</text>'
    + '<text x="' + Lf + '" y="' + (H - 6) + '" fill="#6b7484" font-size="10.5" font-family="Consolas">' + esc(hist[0].date) + '</text>'
    + '<text x="' + (W - R) + '" y="' + (H - 6) + '" fill="#6b7484" font-size="10.5" text-anchor="end" font-family="Consolas">' + esc(lr.date) + '</text>';
  $('breadthChart').innerHTML = g;
})();

/* ══════════ ⑪ 指数估值分位 ══════════ */
(function renderValuation(){
  const S = D.signals;
  if (!S || !S.valuation) return;
  const V = S.valuation, rows = V.data || [];
  if (!rows.length) return;
  $('valPanel').style.display = '';

  $('valHint').innerHTML = 'PE/PB 的历史分位（0%＝历史最便宜，100%＝最贵），分位越高越贵。'
    + '刻度条的白线就是当前分位。<b>口径注意</b>：pe_pct 即上游 <code>pe_percentile</code>，'
    + '而 <code>pe_over_history</code> 是它的互补值（1 − pe_pct），两者互为倒数关系，本页只用前者。'
    + '　数据源：蛋卷基金（替代被 401 拦下的 legulegu）。';

  const pctCol = p => (p === null || p === undefined) ? 'var(--sub)'
    : (p >= 0.8 ? 'var(--up)' : (p <= 0.2 ? 'var(--down)' : '#F5A623'));
  const pctTxt = p => (p === null || p === undefined) ? '—' : (p * 100).toFixed(1) + '%';

  let h = '<div class="mgrid">';
  for (const r of rows) {
    const pp = r.pe_pct, pb = r.pb_pct;
    h += '<div class="mbox">'
      + '<div class="t"><span>' + esc(r.name || r.code) + '</span><span class="tag">' + esc(r.date || '') + '</span></div>'
      + '<div class="hl"><i style="left:calc(' + ((pp === null || pp === undefined ? 50 : pp * 100)).toFixed(1) + '% - 1px)"></i></div>'
      + '<div class="hlscale"><span>0% 便宜</span><span>50%</span><span>贵 100%</span></div>'
      + '<div class="mrow"><span>PE（分位）</span><b style="color:' + pctCol(pp) + '">' + fmt(r.pe, 2)
      + '（' + pctTxt(pp) + '）</b></div>'
      + '<div class="mrow"><span>PB（分位）</span><b style="color:' + pctCol(pb) + '">' + fmt(r.pb, 3)
      + '（' + pctTxt(pb) + '）</b></div>'
      + '<div class="mrow"><span>ROE / 股息率</span><b>'
      + (r.roe === null || r.roe === undefined ? '—' : (r.roe * 100).toFixed(2) + '%') + ' / '
      + (r.dividend_yield === null || r.dividend_yield === undefined ? '—' : (r.dividend_yield * 100).toFixed(2) + '%') + '</b></div>'
      + '<div class="mrow"><span>PEG / 估值评级</span><b>' + fmt(r.peg, 2) + ' / '
      + esc(r.level === 'low' ? '低' : r.level === 'high' ? '高' : r.level === 'mid' ? '中' : (r.level || '—')) + '</b></div>'
      + '</div>';
  }
  h += '</div>';
  $('valBox').innerHTML = h;
})();

/* ══════════ ⑫ ETF 折溢价 ══════════ */
(function renderPremium(){
  const S = D.signals;
  if (!S || !S.premium) return;
  const P = S.premium, rows = P.data || [];
  if (!rows.length) return;
  $('premPanel').style.display = '';

  const stale = rows.some(r => r.stale);
  $('premHint').innerHTML = '折溢价 =（二级市场价 − 单位净值）/ 单位净值 × 100。'
    + '<b>溢价（红）＝场内买盘更强，折价（绿）＝场内抛压更重</b>，刻度以 0 为中心、±1% 满格。'
    + '注意这里用的是<b>收盘价与当日净值</b>，不是盘中实时 IOPV；'
    + (stale ? '<span style="color:#F5A623">当前存在「价格日期 ≠ 净值日期」的标的（净值尚未更新），该行数值只反映相对上一日净值的偏离，参考价值有限。</span>'
      : '当前价格与净值同日，数值可直接参考。')
    + '　数据源：腾讯行情 + 东财净值。';

  const LIM = 1.0;
  let h = '';
  for (const r of rows) {
    const v = r.premium_pct;
    const av = (v === null || v === undefined) ? 0 : Math.min(Math.abs(v) / LIM, 1);
    const w = av * 50;
    const col = (v === null || v === undefined) ? '#6b7484' : (v >= 0 ? 'var(--up)' : 'var(--down)');
    const left = (v === null || v === undefined || v >= 0) ? 50 : 50 - w;
    h += '<div class="prow"><span class="nm">' + esc(r.code) + '</span>'
      + '<div class="ptrack"><div class="zero" style="left:50%"></div>'
      + '<div class="fill" style="left:' + left.toFixed(2) + '%;width:' + Math.max(w, 0.4).toFixed(2)
      + '%;background:' + col + '"></div></div>'
      + '<span class="vv" style="color:' + col + '">'
      + (v === null || v === undefined ? '—' : (v >= 0 ? '+' : '') + v.toFixed(3) + '%')
      + (r.stale ? '<span style="color:#F5A623;font-size:10px"> *</span>' : '') + '</span></div>';
  }
  const nm = {}; for (const r of rows) nm[r.code] = r.name;
  h += '<div class="foot" style="margin-top:8px">' + rows.map(r => esc(r.code) + ' ' + esc(nm[r.code] || '')).join('　｜　') + '</div>';
  $('premBox').innerHTML = h;
})();

/* ---------- 页脚 ---------- */
$('footNote').innerHTML =
 '<b>方法说明：</b>单只 ETF 市值 = 基金份额 × 累计单位净值；持仓占比 = 四只合计市值 ÷ 对应指数流通市值 × 100%。' +
 '占比与指数收盘价分别按近 250 个交易日区间最高/最低归一化到 0~100 分位，Spread = 占比分位 − 指数分位。' +
 '|Spread| ≥ 25 判定为大劈叉；指数向上而持仓占比向下（或近5日份额显著净赎回）判定为顶背离；指数下跌而持仓占比逆势抬升且份额净申购判定为底背离。<br>' +
 '宏观模块由 TradingView Pine Script v6《AA流动性压力指数》移植，数据源为美联储 FRED 官方 API（20 个序列，单位严格按官方口径换算），' +
 '缺失值按交易日前向填充（等价 Pine 的 gaps_off）。GLI 采用美联储净流动性口径，欧/中/日央行与 S5TH、金银比等 TradingView 私有序列已剔除。<br>' +
 '配色遵循 A 股「红涨绿跌」：净申购与正 Spread 用红色，净赎回与负 Spread 用绿色。' +
 '本工具仅用于个人研究与数据可视化，所有指标由公开行情自动计算，<b>不构成任何投资建议</b>。市场有风险，决策需谨慎。<br>' +
 '<b style="color:#F5A623">关于本网页：</b>这是一个<b>静态快照</b>——打开时不会重新取数，显示的是流水线最近一次运行生成的结果；' +
 '每次定时任务跑完会自动更新本页。手机端在浏览器菜单选「添加到主屏幕 / 添加到桌面」即可获得独立图标，点开直接看图，断网也能浏览。';
</script>
</body></html>'''

    write_icons()

    out = TPL.replace('__DATA__', JS)
    with open(HTML, 'w', encoding='utf-8') as f:
        f.write(out)
    print('已生成', HTML, '（%d 字节）' % len(out))


if __name__ == '__main__':
    main()

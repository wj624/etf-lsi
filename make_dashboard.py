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
  <h2 style="margin-top:8px">⑤-1 美元宏观流动性压力指数 LSI vs 美联储净流动性 GLI（悬停查看每日数值）</h2>
  <div class="legend"><span><i style="background:var(--orange)"></i>LSI 压力指数（左轴，bps）</span>
  <span><i style="background:var(--blue)"></i>GLI 净流动性（右轴，万亿美元 T）</span>
  <span><i style="background:#F5A623"></i>阈值线：+20 / +50 / −30 bps</span></div>
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

/* ---------- 双宽基交互图 ---------- */
function drawTrack(key){
  const T = D.tracks[key];
  const S = T.summary, N = T.dates.length;
  const W=1000,H=380,L=64,R=64,Tp=14,B=30;
  function scale(arr, lo, hi){ const m=Math.min.apply(null,arr), M=Math.max.apply(null,arr);
    const a=(hi-lo)/((M-m)||1), b=lo-a*m; return arr.map(v=>a*v+b); }
  const X = i => L + i*(W-L-R)/(N-1);
  const YH = scale(T.hold, H-B-8, Tp+10), YI = scale(T.idx, H-B-8, Tp+10);
  const path = (ys)=>ys.map((y,i)=>(i?'L':'M')+X(i).toFixed(1)+' '+y.toFixed(1)).join('');
  let g='';
  for(let k=0;k<=4;k++){const y=Tp+10+k*(H-B-8-Tp-10)/4; g+='<line x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" stroke="#2A2F39" stroke-width="1"/>';}
  const lm=Math.min.apply(null,T.hold), lM=Math.max.apply(null,T.hold);
  const rm=Math.min.apply(null,T.idx), rM=Math.max.apply(null,T.idx);
  let axis='';
  for(let k=0;k<=4;k++){const f=k/4, y=Tp+10+f*(H-B-8-Tp-10);
    axis+='<text x="'+(L-8)+'" y="'+(y+4)+'" fill="#8A93A3" font-size="10.5" text-anchor="end" font-family="Consolas">'+(lM-f*(lM-lm)).toFixed(3)+'</text>';
    axis+='<text x="'+(W-R+8)+'" y="'+(y+4)+'" fill="#8A93A3" font-size="10.5" font-family="Consolas">'+(rM-f*(rM-rm)).toFixed(0)+'</text>';}
  let xt='';
  const step=Math.max(1,Math.floor(N/12));
  for(let i=0;i<N;i+=step){ xt+='<text x="'+X(i)+'" y="'+(H-8)+'" fill="#8A93A3" font-size="10.5" text-anchor="middle" font-family="Consolas">'+T.dates[i].slice(0,7)+'</text>';}
  let sh='';
  for(let i=1;i<N;i++){ if(Math.abs(T.spread[i])>=25)
    sh+='<rect x="'+X(i-1)+'" y="'+Tp+'" width="'+(X(i)-X(i-1)+1)+'" height="'+(H-B-Tp)+'" fill="'+(T.spread[i]>0?'#E8453C':'#1FB37A')+'" opacity="0.07"/>';}
  const svgHtml = g+sh+
    '<line x1="'+L+'" y1="'+(H-B)+'" x2="'+(W-R)+'" y2="'+(H-B)+'" stroke="#2A2F39"/>'+
    '<path d="'+path(YI)+'" fill="none" stroke="#9B6BFF" stroke-width="2" opacity=".95"/>'+
    '<path d="'+path(YH)+'" fill="none" stroke="#FF8A1F" stroke-width="2.4"/>'+
    axis+xt+
    '<line class="cross" x1="0" y1="'+Tp+'" x2="0" y2="'+(H-B)+'" stroke="#8A93A3" stroke-width="1" stroke-dasharray="3 3" opacity="0"/>'+
    '<circle class="dotH" r="4" fill="#FF8A1F" stroke="#181A20" stroke-width="1.5" opacity="0"/>'+
    '<circle class="dotI" r="4" fill="#9B6BFF" stroke="#181A20" stroke-width="1.5" opacity="0"/>'+
    '<rect x="'+L+'" y="'+Tp+'" width="'+(W-L-R)+'" height="'+(H-B-Tp)+'" fill="transparent" class="hit"/>';

  /* Spread 副图 */
  const W2=1000,H2=170,L2=64,R2=64,T2=10,B2=26;
  const X2 = i => L2 + i*(W2-L2-R2)/(N-1);
  const mS=Math.min.apply(null,T.spread), MS=Math.max.apply(null,T.spread);
  const lo=Math.min(mS,-25), hi=Math.max(MS,25);
  const Y2 = v => T2 + (hi-v)/((hi-lo)||1)*(H2-B2-T2);
  let bars='', gl='';
  for(let k=0;k<=4;k++){const y=T2+k*(H2-B2-T2)/4; gl+='<line x1="'+L2+'" y1="'+y+'" x2="'+(W2-R2)+'" y2="'+y+'" stroke="#2A2F39" stroke-width="1"/>';}
  const bw=Math.max(1,(W2-L2-R2)/N*0.7);
  for(let i=0;i<N;i++){ const v=T.spread[i], y0=Y2(0), y1=Y2(v);
    bars+='<rect x="'+(X2(i)-bw/2)+'" y="'+Math.min(y0,y1)+'" width="'+bw+'" height="'+Math.max(Math.abs(y1-y0),0.6)+'" fill="'+(v>=0?'#E8453C':'#1FB37A')+'" opacity="0.72"/>';}
  let thr='';
  for(const t of [25,-25]){ thr+='<line x1="'+L2+'" y1="'+Y2(t)+'" x2="'+(W2-R2)+'" y2="'+Y2(t)+'" stroke="#F5A623" stroke-width="1" stroke-dasharray="5 4" opacity="0.75"/>'
    +'<text x="'+(W2-R2+6)+'" y="'+(Y2(t)+4)+'" fill="#F5A623" font-size="10" font-family="Consolas">'+(t>0?'+':'')+t+'</text>';}
  let spAxis='';
  for(let k=0;k<=4;k++){const f=k/4, y=T2+f*(H2-B2-T2);
    spAxis+='<text x="'+(L2-8)+'" y="'+(y+4)+'" fill="#8A93A3" font-size="10.5" text-anchor="end" font-family="Consolas">'+(hi-f*(hi-lo)).toFixed(0)+'</text>';}
  const zero = Y2(0);
  const spHtml = gl+bars+'<line x1="'+L2+'" y1="'+zero+'" x2="'+(W2-R2)+'" y2="'+zero+'" stroke="#4a5160"/>'+thr+spAxis;

  const blk = document.createElement('div');
  blk.className='panel';
  blk.innerHTML =
    '<h2>' + esc(S.title) + ' · ' + esc(S.labels.div_title) + '（悬停查看每日明细）</h2>' +
    '<div class="legend"><span><i style="background:var(--orange)"></i>' + esc(S.labels.hold) + '（左轴）</span>' +
    '<span><i style="background:var(--purple)"></i>' + S.index_name + ' 收盘价（右轴）</span></div>' +
    '<svg viewBox="0 0 1000 380">' + svgHtml + '</svg>' +
    '<div class="tip"></div>' +
    '<h2 style="margin-top:10px">开口差值 Spread = 占比分位 − 指数分位</h2>' +
    '<div class="hint">红柱：橙线强于紫线（持仓相对抬升）　绿柱：紫线强于橙线（指数相对虚高）　橙虚线：±25 劈叉预警阈值</div>' +
    '<svg viewBox="0 0 1000 170">' + spHtml + '</svg>' +
    '<div class="reason" style="margin:12px 0 0"><b>今日诊断（' + S.date + '）：</b>' + esc(S.reason) + '</div>';
  $('trackBlocks').appendChild(blk);

  const svgEl = blk.querySelector('svg');
  const hit = svgEl.querySelector('.hit'), tip = blk.querySelector('.tip');
  const cross = svgEl.querySelector('.cross'), dotH = svgEl.querySelector('.dotH'), dotI = svgEl.querySelector('.dotI');
  hit.addEventListener('mousemove', ev=>{
    const rc = hit.getBoundingClientRect();
    const px = (ev.clientX-rc.left)/rc.width*(W-L-R);
    let i = Math.round(px/(W-L-R)*(N-1)); i = Math.max(0,Math.min(N-1,i));
    const x = X(i);
    cross.setAttribute('x1',x); cross.setAttribute('x2',x); cross.setAttribute('opacity','.7');
    dotH.setAttribute('cx',x); dotH.setAttribute('cy',YH[i]); dotH.setAttribute('opacity','1');
    dotI.setAttribute('cx',x); dotI.setAttribute('cy',YI[i]); dotI.setAttribute('opacity','1');
    let rows='';
    for (const kk in T.names){ const c=T.chg[kk][i];
      rows += '<div style="display:flex;justify-content:space-between;gap:14px"><span style="color:#8A93A3">'+esc(T.names[kk])+
        '</span><span>'+fmt(T.shares[kk][i],2)+' 亿份 <span class="'+(c>=0?'pos':'neg')+'">'+sign(c,2)+'</span></span></div>';}
    tip.innerHTML = '<b>'+T.dates[i]+'</b><div style="color:var(--orange)">持仓占比 '+fmt(T.hold[i],4)+'%</div>'+
      '<div style="color:var(--purple)">'+S.index_name+' '+fmt(T.idx[i],2)+'</div>'+
      '<div style="color:var(--blue)">Spread '+sign(T.spread[i],1)+'</div><div style="margin-top:5px">'+rows+'</div>';
    tip.style.display='block';
    const pr = svgEl.getBoundingClientRect(), br = blk.getBoundingClientRect();
    let lx = ev.clientX - br.left + 16;
    if (lx + 240 > br.width) lx = ev.clientX - br.left - 236;
    tip.style.left = lx + 'px';
    tip.style.top = (ev.clientY - br.top + 14) + 'px';
  });
  hit.addEventListener('mouseleave', ()=>{ tip.style.display='none';
    cross.setAttribute('opacity','0'); dotH.setAttribute('opacity','0'); dotI.setAttribute('opacity','0'); });
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

/* ---------- LSI vs GLI 走势图（对应监测图行 3） ---------- */
function drawLsi(){
  const L = D.lsi;
  if (!L || !L.hist || !L.cal) return;
  const h = L.hist;
  let cal = L.cal, lsi = h.lsi || [], gli = h.gli || [];
  const TAKE = 260;                      // 展示最近约一年
  let n = Math.min(cal.length, lsi.length, gli.length);
  const s0 = Math.max(0, n - TAKE);
  cal = cal.slice(s0, n); lsi = lsi.slice(s0, n); gli = gli.slice(s0, n);
  n = cal.length;
  if (n < 5) return;

  const rrpT = (h.rrp_T||[]).slice(s0, s0+n);
  const rrpP = (h.rrp_pct||[]).slice(s0, s0+n);
  const cd   = (h.credit||[]).slice(s0, s0+n);
  const imp  = (h.impulse||[]).slice(s0, s0+n);

  const W=1000,H=360,Lf=62,R=66,Tp=14,B=30;
  const X = i => Lf + i*(W-Lf-R)/(n-1);
  function scale(arr, lo, hi){
    const v = arr.filter(x=>x!==null && x!==undefined);
    const m = Math.min.apply(null,v), M = Math.max.apply(null,v);
    const a=(hi-lo)/((M-m)||1), b=lo-a*m;
    return arr.map(x => (x===null||x===undefined)?null:a*x+b);
  }
  // 左轴把三条阈值线纳入范围，保证阈值可见
  const lv = lsi.filter(x=>x!==null).concat([20,50,-30]);
  const lMin = Math.min.apply(null,lv), lMax = Math.max.apply(null,lv);
  function yL(v){ return Tp+10 + (lMax-v)/((lMax-lMin)||1)*(H-B-8-Tp-10); }
  const gv = gli.filter(x=>x!==null);
  const gMin = Math.min.apply(null,gv), gMax = Math.max.apply(null,gv);
  function yG(v){ return Tp+10 + (gMax-v)/((gMax-gMin)||1)*(H-B-8-Tp-10); }

  let g='';
  for(let k=0;k<=4;k++){const y=Tp+10+k*(H-B-8-Tp-10)/4;
    g+='<line x1="'+Lf+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" stroke="#2A2F39" stroke-width="1"/>';}
  // 劈叉/阈值阴影：LSI ≥ 20 偏紧（红）、≤ -30 极端宽松（绿）
  let sh='';
  for(let i=1;i<n;i++){
    const v=lsi[i]; if(v===null||v===undefined) continue;
    if(v>=20) sh+='<rect x="'+X(i-1)+'" y="'+Tp+'" width="'+(X(i)-X(i-1)+1)+'" height="'+(H-B-Tp)+'" fill="#E8453C" opacity="0.07"/>';
    else if(v<=-30) sh+='<rect x="'+X(i-1)+'" y="'+Tp+'" width="'+(X(i)-X(i-1)+1)+'" height="'+(H-B-Tp)+'" fill="#1FB37A" opacity="0.07"/>';
  }
  let thr='';
  for(const t of [50,20,-30]){
    const y=yL(t);
    const col = t===50?'#8B1A1A':(t===20?'#E8453C':'#1FB37A');
    thr+='<line x1="'+Lf+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" stroke="'+col+'" stroke-width="1" stroke-dasharray="5 4" opacity="0.8"/>'
      +'<text x="'+(W-R+6)+'" y="'+(y+4)+'" fill="'+col+'" font-size="10" font-family="Consolas">'+(t>0?'+':'')+t+'</text>';
  }
  let axis='';
  for(let k=0;k<=4;k++){const f=k/4, y=Tp+10+f*(H-B-8-Tp-10);
    axis+='<text x="'+(Lf-8)+'" y="'+(y+4)+'" fill="#FF8A1F" font-size="10.5" text-anchor="end" font-family="Consolas">'+(lMax-f*(lMax-lMin)).toFixed(0)+'</text>';
    axis+='<text x="'+(W-R+8)+'" y="'+(y+4)+'" fill="#4C9AFF" font-size="10.5" font-family="Consolas">'+(gMax-f*(gMax-gMin)).toFixed(2)+'</text>';}
  let xt='';
  const step=Math.max(1,Math.floor(n/12));
  for(let i=0;i<n;i+=step){ xt+='<text x="'+X(i)+'" y="'+(H-8)+'" fill="#8A93A3" font-size="10.5" text-anchor="middle" font-family="Consolas">'+String(cal[i]).slice(0,7)+'</text>';}

  const pL = lsi.map((v,i)=>((v===null||v===undefined)?null:((i?'L':'M')+X(i).toFixed(1)+' '+yL(v).toFixed(1)))).filter(Boolean).join('');
  const pG = gli.map((v,i)=>((v===null||v===undefined)?null:((i?'L':'M')+X(i).toFixed(1)+' '+yG(v).toFixed(1)))).filter(Boolean).join('');

  const el = $('lsiChart');
  el.innerHTML = g+sh+
    '<line x1="'+Lf+'" y1="'+(H-B)+'" x2="'+(W-R)+'" y2="'+(H-B)+'" stroke="#2A2F39"/>'+
    '<path d="'+pG+'" fill="none" stroke="#4C9AFF" stroke-width="2.1" opacity=".95"/>'+
    '<path d="'+pL+'" fill="none" stroke="#FF8A1F" stroke-width="2.4"/>'+
    thr+axis+xt+
    '<line id="lcross" x1="0" y1="'+Tp+'" x2="0" y2="'+(H-B)+'" stroke="#8A93A3" stroke-width="1" stroke-dasharray="3 3" opacity="0"/>'+
    '<circle id="ldotL" r="4" fill="#FF8A1F" stroke="#181A20" stroke-width="1.5" opacity="0"/>'+
    '<circle id="ldotG" r="4" fill="#4C9AFF" stroke="#181A20" stroke-width="1.5" opacity="0"/>'+
    '<rect x="'+Lf+'" y="'+Tp+'" width="'+(W-Lf-R)+'" height="'+(H-B-Tp)+'" fill="transparent" id="lhit"/>';

  const tip=$('lsiTip'), hit=$('lhit'), cross=$('lcross'), dL=$('ldotL'), dG=$('ldotG');
  hit.addEventListener('mousemove', ev=>{
    const rc=hit.getBoundingClientRect();
    const px=(ev.clientX-rc.left)/rc.width*(W-Lf-R);
    let i=Math.round(px/(W-Lf-R)*(n-1)); i=Math.max(0,Math.min(n-1,i));
    // 跳过左轴的空值点
    while(i>0 && (lsi[i]===null||lsi[i]===undefined)) i--;
    const x=X(i);
    cross.setAttribute('x1',x); cross.setAttribute('x2',x); cross.setAttribute('opacity','.7');
    if(lsi[i]!==null&&lsi[i]!==undefined){ dL.setAttribute('cx',x); dL.setAttribute('cy',yL(lsi[i])); dL.setAttribute('opacity','1'); }
    if(gli[i]!==null&&gli[i]!==undefined){ dG.setAttribute('cx',x); dG.setAttribute('cy',yG(gli[i])); dG.setAttribute('opacity','1'); }
    const lsiv = lsi[i], gliv = gli[i];
    const st = (lsiv===null||lsiv===undefined)?'—':
      (lsiv>=50?'极端紧张':(lsiv>=20?'偏紧':(lsiv<0?(lsiv<=-30?'极端宽松':'正常宽松'):'中性平衡')));
    tip.innerHTML = '<b>'+String(cal[i])+'</b>'+
      '<div style="color:#FF8A1F">LSI '+fmt(lsiv,1)+' bps（'+st+'）</div>'+
      '<div style="color:#4C9AFF">GLI '+fmt(gliv,3)+' T</div>'+
      '<div style="color:#8A93A3">RRP '+fmt(rrpT[i],3)+' T（峰值占比 '+fmt(rrpP[i],1)+'%）</div>'+
      '<div style="color:#8A93A3">信用利差 '+fmt(cd[i],0)+' bps　冲量 '+sign(imp[i],2)+'%</div>';
    tip.style.display='block';
    const br=el.getBoundingClientRect(), pr=$('lsiPanel').getBoundingClientRect();
    let lx = ev.clientX - pr.left + 16;
    if (lx + 250 > pr.width) lx = ev.clientX - pr.left - 246;
    tip.style.left = lx+'px';
    tip.style.top = (ev.clientY - pr.top + 14)+'px';
  });
  hit.addEventListener('mouseleave', ()=>{ tip.style.display='none';
    cross.setAttribute('opacity','0'); dL.setAttribute('opacity','0'); dG.setAttribute('opacity','0'); });
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

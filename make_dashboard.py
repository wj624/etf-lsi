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
        for k in ('valuation', 'liquidity', 'premium', 'breadth', 'rates', 'macro_ratios'):
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
.prow{display:grid;grid-template-columns:64px 132px 1fr 70px;align-items:center;gap:9px;font-size:12px;padding:3px 0}
.prow .nm{color:var(--sub);font-family:Consolas,monospace}
.prow .nmx{color:var(--txt);font-size:11.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ptrack{position:relative;height:16px;background:#15181D;border-radius:4px;overflow:hidden}
.ptrack .zero{position:absolute;top:0;bottom:0;width:1px;background:#3a4150}
.ptrack .fill{position:absolute;top:2px;bottom:2px;border-radius:3px}
.prow .vv{text-align:right;font-family:Consolas,monospace;font-weight:600}
.subh{color:var(--sub);font-size:12px;font-weight:600;margin:14px 0 4px}

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
  .prow{grid-template-columns:56px 104px 1fr 62px;gap:7px;font-size:11.5px}
  .prow .nmx{font-size:11px}
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

<div class="subh" id="macroRatioHead" style="display:none">跨资产比价 / 风险偏好<span style="font-weight:400">　·　外盘连续合约盘中快照 · KOSPI/GOLD 固定阈值 1.85 / 1.10</span></div>
<div class="cards" id="macroRatioCards" style="display:none"></div>

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
  <div id="usGapBox" style="display:none">
    <div class="subh" id="usGapH"></div>
    <svg id="usGapChart" viewBox="0 0 1000 190"></svg>
  </div>
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
  <h2>⑨ 境内资金面（DR001 / 政策锚）· 与 ⑤ 的境外流动性互为对照 <span id="liqCnBadge" style="display:none;margin-left:10px;padding:2px 9px;border-radius:9px;font-size:11.5px;border:1px solid;font-weight:400"></span></h2>
  <div class="hint" id="liqCnHint"></div>
  <div class="legend" id="liqCnLegend"></div>
  <div class="zbar" id="liqCnBar">
    <button class="zbtn" data-len="21">1M</button>
    <button class="zbtn" data-len="63">3M</button>
    <button class="zbtn" data-len="126">6M</button>
    <button class="zbtn" data-len="250">1Y</button>
    <button class="zbtn" data-len="-1" title="全部">复位</button>
    <span class="zhint">滚轮缩放 · 按住拖拽平移 · 双击复位</span>
    <span class="zrange" id="liqCnRange"></span>
  </div>
  <svg id="liqCnChart" viewBox="0 0 1000 300"></svg>
  <div class="hint" id="liqCnDevHint" style="margin-top:10px;margin-bottom:2px"></div>
  <svg id="liqCnDevChart" viewBox="0 0 1000 120"></svg>
  <div class="tip" id="liqCnTip" style="display:none"></div>
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

<div class="panel" id="ratesPanel" style="display:none">
  <h2>⑬ 国债收益率曲线与期限利差（无风险利率 · 数据源：东财）</h2>
  <div class="hint" id="ratesHint"></div>
  <div class="cards" id="ratesCards"></div>
  <div class="subh">曲线形态（横轴＝期限 2Y / 5Y / 10Y / 30Y）：同一条收益率曲线在三个日期的三张快照</div>
  <svg id="ratesCurve" viewBox="0 0 1000 300"></svg>
  <div class="subh" id="ratesSpreadSub">10Y − 2Y 期限利差（横轴＝交易日）：上图每条线 2Y→10Y 的落差＝这条曲线上的一个点　｜　单位 bp，负值＝倒挂</div>
  <div class="zbar" id="ratesSpreadTabs" style="margin:0 0 6px">
    <button class="zbtn on" data-sp="cn_10y_2y">10Y − 2Y</button>
    <button class="zbtn" data-sp="cn_30y_10y">30Y − 10Y</button>
    <span class="zhint" id="ratesSpreadHint"></span>
  </div>
  <svg id="ratesSpread" viewBox="0 0 1000 170"></svg>
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

/* ---------- 跨资产比价 / 风险偏好（4 张卡，样式与顶部 9 张一致） ---------- */
const MR = D.signals && D.signals.macro_ratios;
if (MR && MR.gold_silver && MR.gold_oil && MR.copper_gold && MR.kospi_gold) {
  const pct1 = (v) => (v === null || v === undefined) ? '—' : sign(v, 1) + '%';
  const mcard = (k, v, col, d) => '<div class="card"><div class="k">' + k + '</div>'
    + '<div class="v" style="color:' + col + '">' + v + '</div>'
    + '<div class="d">' + d + '</div></div>';
  let mh = '';
  const gs = MR.gold_silver, go = MR.gold_oil, cg = MR.copper_gold, kg = MR.kospi_gold;
  mh += mcard('金银比 · GC / SI', fmt(gs.value, 2), 'var(--orange)',
              '20日 ' + pct1(gs.chg20_pct) + '｜250日分位 ' + fmt(gs.pct250, 1) + '%');
  mh += mcard('金油比 · GC / CL', fmt(go.value, 2), 'var(--blue)',
              '20日 ' + pct1(go.chg20_pct) + '｜250日分位 ' + fmt(go.pct250, 1) + '%');
  mh += mcard('铜金比 · HG / GC', fmt(cg.value, 2), 'var(--cyan)',
              '20日 ' + pct1(cg.chg20_pct) + '｜250日分位 ' + fmt(cg.pct250, 1) + '%');
  const sigCol = kg.signal === 'sell' ? 'var(--up)'
               : (kg.signal === 'buy' ? 'var(--down)' : 'var(--txt)');
  const sigTxt = kg.signal === 'sell' ? '卖股票' : (kg.signal === 'buy' ? '买股票' : '中性');
  mh += mcard('KOSPI / 黄金(盎司)', fmt(kg.value, 4), sigCol,
              sigTxt + '｜距上限 ' + pct1(kg.dist_hi_pct)
              + '｜距下限 ' + pct1(kg.dist_lo_pct));
  $('macroRatioHead').style.display = '';
  $('macroRatioCards').innerHTML = mh;
  $('macroRatioCards').style.display = '';
}

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
  // US02Y − EFFR：市场定价与当前政策利率的缺口。
  // 2Y 高于 EFFR = 市场在定价「未来要加息」→ 红；低于 = 定价「要降息」→ 绿。
  // 两个字段都是 bp 口径（459 = 4.59%），直接相减就是 bp 差，不要再 ×100。
  const usE = (c.us02y!==null&&c.us02y!==undefined&&c.effr!==null&&c.effr!==undefined) ? (c.us02y-c.effr) : null;
  lh += kv('US02Y − EFFR', usE===null?'—':sign(usE,1)+' bp',
           'US02Y '+fmt(d100(c.us02y),2)+'% − EFFR '+fmt(d100(c.effr),2)+'%｜&gt;0 加息周期 · &lt;0 降息周期',
           usE===null?'var(--txt)':(usE>0?'var(--up)':'var(--down)'));
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

/* ---------- ⑤-3 US02Y − EFFR 缺口（近 250 个交易日） ---------- */
(function renderUsGap(){
  const L = D.lsi;
  if (!L || !L.hist || !L.hist.us2_effr || !L.cal) return;
  const cal = L.cal, ser = L.hist.us2_effr;
  const len = Math.min(cal.length, ser.length);
  const n = Math.min(250, len);
  if (n < 20) return;
  const i0 = len - n;
  const V = [], DD = [];
  for (let i = i0; i < i0 + n; i++) { DD.push(cal[i]); V.push(ser[i]); }
  const vals = V.filter(function(v){ return v !== null && v !== undefined && !isNaN(v); });
  if (vals.length < 10) return;
  $('usGapBox').style.display = '';

  let mnv = 0, mxv = 0, pos = 0, neg = 0;
  for (const v of vals) {
    if (v < mnv) mnv = v;
    if (v > mxv) mxv = v;
    if (v > 0) pos++; else if (v < 0) neg++;
  }
  const cur = vals[vals.length - 1];
  const pad = (mxv - mnv) * 0.16 || 5;
  const mn = mnv - pad, mx = mxv + pad;

  // 头文字刻意不写日期区间：横轴两端已经有，重复反而让窄屏折行时把最后几个字甩到下一行。
  $('usGapH').innerHTML = '⑤-3 US02Y − EFFR 缺口 · 近 ' + n + ' 个交易日'
    + '　｜　<b style="color:#E8453C">上方＝定价加息</b> · <b style="color:#1FB37A">下方＝定价降息</b>'
    + '　｜　区间 ' + mnv.toFixed(0) + ' ~ ' + mxv.toFixed(0) + ' bp（加息 ' + pos + ' 天 · 降息 ' + neg + ' 天）';

  const W = 1000, H = 190, Lf = 58, Rr = 80, Tp = 16, B = 28;
  const X = function(i){ return Lf + i * (W - Lf - Rr) / Math.max(1, n - 1); };
  const Y = function(v){ return Tp + (mx - v) / (mx - mn) * (H - B - Tp); };

  let g = '';
  // 刻度用「整齐步长」而不是等分：等分会得到 130 / 72 / 14 / −44 这种读不出量级的数字。
  const span = mx - mn;
  const mag = Math.pow(10, Math.floor(Math.log10(span / 4 || 1)));
  const nrm = (span / 4) / mag;
  const step = (nrm <= 1 ? 1 : nrm <= 2 ? 2 : nrm <= 5 ? 5 : 10) * mag;
  const ticks = [];
  for (let t = Math.ceil(mn / step) * step; t <= mx + 1e-9; t += step) ticks.push(+t.toFixed(4));
  const y0 = Y(0);
  for (const tv of ticks) {
    const isZero = Math.abs(tv) < 1e-9;
    const yy = isZero ? y0 : Y(tv);
    g += '<line x1="' + Lf + '" y1="' + yy.toFixed(1) + '" x2="' + (W - Rr) + '" y2="' + yy.toFixed(1)
      + '" stroke="' + (isZero ? '#E8453C' : '#2A2F39') + '" stroke-width="1"'
      + (isZero ? ' stroke-dasharray="4 4" opacity="0.85"' : '') + '/>'
      + '<text x="' + (Lf - 8) + '" y="' + (yy + 4).toFixed(1) + '" fill="' + (isZero ? '#E8453C' : '#8A93A3')
      + '" font-size="10.5" text-anchor="end" font-family="Consolas">' + (isZero ? '0' : tv.toFixed(0)) + '</text>';
  }

  let d = '', on = false;
  for (let i = 0; i < n; i++) {
    const v = V[i];
    if (v === null || v === undefined || isNaN(v)) { on = false; continue; }
    d += (on ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1) + ' ';
    on = true;
  }
  // 同一条路径画两遍，用「零轴之上 / 之下」两个裁剪区分别着色：
  // 上方红＝定价加息、下方绿＝定价降息，比单色线更能一眼看出周期切换。
  const y0c = Math.max(0, y0).toFixed(1);
  g += '<defs><clipPath id="ugTop"><rect x="0" y="0" width="' + W + '" height="' + y0c + '"/></clipPath>'
    + '<clipPath id="ugBot"><rect x="0" y="' + y0c + '" width="' + W + '" height="'
    + Math.max(0, H - y0).toFixed(1) + '"/></clipPath></defs>'
    + '<path d="' + d + '" fill="none" stroke="#E8453C" stroke-width="1.9" stroke-linejoin="round" clip-path="url(#ugTop)"/>'
    + '<path d="' + d + '" fill="none" stroke="#1FB37A" stroke-width="1.9" stroke-linejoin="round" clip-path="url(#ugBot)"/>';

  const col = cur >= 0 ? '#E8453C' : '#1FB37A';
  g += '<circle cx="' + X(n - 1).toFixed(1) + '" cy="' + Y(cur).toFixed(1) + '" r="3.2" fill="' + col + '"/>'
    + '<text x="' + (X(n - 1) + 8).toFixed(1) + '" y="' + (Y(cur) + 4).toFixed(1) + '" fill="' + col
    + '" font-size="11" font-family="Consolas">' + (cur > 0 ? '+' : '') + cur.toFixed(1) + ' bp</text>'
    + '<text x="' + Lf + '" y="' + (H - 7) + '" fill="#6b7484" font-size="10.5" font-family="Consolas">' + esc(DD[0]) + '</text>'
    + '<text x="' + (W - Rr) + '" y="' + (H - 7) + '" fill="#6b7484" font-size="10.5" text-anchor="end" '
    + 'font-family="Consolas">' + esc(DD[n - 1]) + '</text>';
  $('usGapChart').innerHTML = g;
})();

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
  const rows = (L.data || []).filter(r => r && r.date);
  if (rows.length < 5) return;
  $('liqCnPanel').style.display = '';
  /* 2026-11-02 换锚：隔夜逆回购 1.25% 成为主要政策利率，DR001 为调控目标。
     走廊 ±25bp 为按公告「加减点幅度不变」推算，官方未单独公布上下限数值。
     央行日后调整政策利率时只需改这里一处；下方 anchorStale 会自动提示核对。 */
  const POLICY = { rate: 1.25, bandBp: 25, from: '2026-11-02' };
  const BAND = POLICY.bandBp / 100;
  const devBp = v => (v === null || v === undefined || isNaN(v)) ? null : (v - POLICY.rate) * 100;
  const lt0 = L.latest || {};
  const dev0 = devBp(lt0.dr001);
  const anchorStale = dev0 !== null && Math.abs(dev0) > POLICY.bandBp * 1.5;
  let firstDr = -1;
  for (let i = 0; i < rows.length; i++) {
    if (rows[i].dr001 !== null && rows[i].dr001 !== undefined) { firstDr = i; break; }
  }
  const badge = $('liqCnBadge');
  if (badge) {
    let txt, col;
    if (anchorStale) { txt = '政策利率可能已变更 · 请核对'; col = '#F5A623'; }
    else if (dev0 === null) { txt = 'DR001 数据待更新'; col = '#8A93A3'; }
    else if (Math.abs(dev0) <= 10) { txt = '贴合政策锚 · 资金平稳'; col = '#1FB37A'; }
    else if (dev0 > 0) { txt = '高于锚 ' + dev0.toFixed(1) + 'bp · 资金偏紧'; col = '#E8453C'; }
    else { txt = '低于锚 ' + Math.abs(dev0).toFixed(1) + 'bp · 资金偏松'; col = '#4C9AFF'; }
    badge.textContent = txt;
    badge.style.display = '';
    badge.style.color = col;
    badge.style.borderColor = col;
  }

  // 沪深300 归一序列：从主图 track 取 sh000300 的 dates/idx，按日期对齐到资金面 rows，
  // 以 rows 中第一个能对上指数的日期为 100。用来对照「利率松紧 vs 指数涨跌」。
  let idxDates = null, idxVals = null, idxName = '沪深300';
  for (const k of (D.order || [])) {
    const T = D.tracks && D.tracks[k];
    if (T && T.summary && T.summary.index_code === 'sh000300') {
      idxDates = T.dates; idxVals = T.idx;
      idxName = T.summary.index_name || '沪深300';
      break;
    }
  }
  let baseIdx = null, idxMap = {};
  if (idxDates && idxVals) {
    const byDate = {};
    for (let j = 0; j < idxDates.length; j++) {
      if (idxVals[j] !== null && idxVals[j] !== undefined) byDate[idxDates[j]] = idxVals[j];
    }
    for (const r of rows) {
      if (byDate[r.date] !== null && byDate[r.date] !== undefined) { baseIdx = byDate[r.date]; break; }
    }
    if (baseIdx) for (const r of rows) {
      const v = byDate[r.date];
      idxMap[r.date] = (v === null || v === undefined) ? null : v / baseIdx * 100;
    }
  }
  const lastVal = key => {
    for (let i = rows.length - 1; i >= 0; i--) {
      const v = rows[i][key];
      if (v !== null && v !== undefined && !isNaN(v)) return v;
    }
    return null;
  };
  let lastIdxVal = null;
  if (baseIdx) for (let i = rows.length - 1; i >= 0; i--) {
    const v = idxMap[rows[i].date];
    if (v !== null && v !== undefined && !isNaN(v)) { lastIdxVal = v; break; }
  }

  const lt = L.latest || {}, dv = L.derived || {};
  const bp = v => (v === null || v === undefined) ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(1) + ' bp';
  const bpCol = v => (v === null || v === undefined) ? 'var(--sub)' : (v > 0 ? 'var(--up)' : (v < 0 ? 'var(--down)' : 'var(--txt)'));

  $('liqCnHint').innerHTML = '银行间资金价格，年化 %。<b>' + POLICY.from + ' 换锚后</b>，'
    + '央行主要政策利率为隔夜逆回购 <b>' + POLICY.rate.toFixed(2) + '%</b>、调控目标为 <b>DR001</b>；'
    + 'DR001 在锚上方＝资金偏紧，下方＝偏松。浅蓝带为窄走廊 ±' + POLICY.bandBp + 'bp（<b>按公告推算，非官方公布值</b>）。'
    + '<b>右轴紫线为 ' + esc(idxName) + ' 归一=100，用来对照「利率松紧 vs 指数涨跌」</b>，下方副图同样叠加了这条紫线。'
    + 'SHIBOR 3M ' + fmt(lt.shibor_3m, 3) + '%｜3M−隔夜 ' + bp(dv.term_spread_3m_on_bp) + '。'
    + (lt.date ? '　最新 ' + esc(lt.date) : '')
    + '　<b>数据源：中国货币网</b>；DR001 / DR007 / FR001 上游仅回溯约 1 个月（线在后段，竖虚线为 DR001 数据起点），SHIBOR 更长。'
    + (anchorStale ? '　<span style="color:#F5A623"><b>注意：政策利率可能已变更，请核对 POLICY.rate</b></span>' : '');

  const spreadBp = (lt.fr001 != null && lt.dr001 != null) ? (lt.fr001 - lt.dr001) * 100 : null;
  let dayChgBp = null;
  for (let i = rows.length - 1; i > 0; i--) {
    if (rows[i].dr001 != null && rows[i - 1].dr001 != null) {
      dayChgBp = (rows[i].dr001 - rows[i - 1].dr001) * 100; break;
    }
  }
  let ch = '';
  ch += '<div class="card"><div class="k">DR001 · 隔夜目标利率</div>'
      + '<div class="v" style="color:var(--cyan)">' + fmt(lt.dr001, 3) + '%</div>'
      + '<div class="d">距锚 <span style="color:' + bpCol(devBp(lt.dr001)) + '">' + bp(devBp(lt.dr001)) + '</span>'
      + '｜日变 <span style="color:' + bpCol(dayChgBp) + '">' + bp(dayChgBp) + '</span></div></div>';
  ch += '<div class="card"><div class="k">政策锚 · 隔夜逆回购</div>'
      + '<div class="v" style="color:var(--down)">' + POLICY.rate.toFixed(3) + '%</div>'
      + '<div class="d">' + POLICY.from + ' 换锚｜走廊 ±' + POLICY.bandBp + 'bp（推算）</div></div>';
  ch += '<div class="card"><div class="k">FR001 分层溢价</div>'
      + '<div class="v" style="color:var(--purple)">' + bp(spreadBp) + '</div>'
      + '<div class="d">FR001 ' + fmt(lt.fr001, 3) + '%｜走阔＝非银借钱变难</div></div>';
  ch += '<div class="card"><div class="k">DR007 · 7天回购（辅助）</div>'
      + '<div class="v" style="color:var(--orange)">' + fmt(lt.dr007, 3) + '%</div>'
      + '<div class="d">20 日均 ' + fmt(dv.dr007_ma20, 3) + '｜5 日 ' + bp(dv.dr007_chg_5d_bp) + '</div></div>';
  $('liqCnCards').innerHTML = ch;

  // 图例直接带最新值；政策锚与走廊为固定参考，不随缩放变化
  $('liqCnLegend').innerHTML = '<span><i style="background:#22D3EE"></i>DR001 ' + fmt(lastVal('dr001'), 3) + '%（左轴·主线）</span>'
    + '<span><i style="background:#1FB37A"></i>政策锚 ' + POLICY.rate.toFixed(2) + '%（' + POLICY.from + '）</span>'
    + '<span><i style="background:#B5D4F4"></i>窄走廊 ' + (POLICY.rate - BAND).toFixed(2) + '~' + (POLICY.rate + BAND).toFixed(2) + '%（±' + POLICY.bandBp + 'bp 推算）</span>'
    + '<span><i style="background:#FF8A1F"></i>DR007 ' + fmt(lastVal('dr007'), 3) + '%（左轴）</span>'
    + '<span><i style="background:#4C9AFF"></i>SHIBOR 3M ' + fmt(lastVal('shibor_3m'), 3) + '%（左轴）</span>'
    + '<span><i style="background:#8A93A3"></i>SHIBOR 隔夜 O/N ' + fmt(lastVal('shibor_on'), 3) + '%（左轴）</span>'
    + (baseIdx ? '<span><i style="background:#9B6BFF"></i>' + esc(idxName) + (lastIdxVal === null ? '' : ' 归一 ' + lastIdxVal.toFixed(1)) + '（右轴·对照）</span>' : '');
  const devHint = $('liqCnDevHint');
  if (devHint) {
    devHint.innerHTML = '<b>② 距政策锚的偏离（bp，放大显示）</b>　左轴青线＝DR001 偏离，'
      + '绿虚线＝贴合锚 0bp，蓝虚线＝走廊 ±' + POLICY.bandBp + 'bp（推算）；'
      + '<b>紫线＝' + esc(idxName) + ' 归一（右轴）</b>，与上方主图同一对照：资金转松通常对应指数走强。';
  }

  const W = 1000, H = 300, Lf = 54, R = 78, Tp = 14, B = 26;
  const N = rows.length;
  const view = {i0: 0, i1: N - 1};
  const series = [
    {key: 'dr007', name: 'DR007', col: '#FF8A1F', w: 1.3},
    {key: 'shibor_3m', name: 'SHIBOR 3M', col: '#4C9AFF', w: 1.6},
    {key: 'shibor_on', name: 'SHIBOR 隔夜 O/N', col: '#8A93A3', w: 1.2, dash: '4 3'},
    {key: 'dr001', name: 'DR001', col: '#22D3EE', w: 2.6}
  ];
  const svg = $('liqCnChart');
  let GR = null;

  function render(){
    const n = view.i1 - view.i0 + 1;
    const X = i => n > 1 ? Lf + (i - view.i0) * (W - Lf - R) / (n - 1) : (Lf + W - R) / 2;

    let mn = Infinity, mx = -Infinity;
    for (const s of series) for (let i = view.i0; i <= view.i1; i++) {
      const v = rows[i][s.key];
      if (v !== null && v !== undefined && !isNaN(v)) { if (v < mn) mn = v; if (v > mx) mx = v; }
    }
    if (!isFinite(mn)) { mn = 0; mx = 1; }
    mn = Math.min(mn, POLICY.rate); mx = Math.max(mx, POLICY.rate);
    const pd0 = (mx - mn) * 0.2 || 0.05; mn -= pd0; mx += pd0;
    const Y = v => Tp + (mx - v) / (mx - mn) * (H - B - Tp);

    let imn = Infinity, imx = -Infinity;
    if (baseIdx) for (let i = view.i0; i <= view.i1; i++) {
      const v = idxMap[rows[i].date];
      if (v !== null && v !== undefined && !isNaN(v)) { if (v < imn) imn = v; if (v > imx) imx = v; }
    }
    const hasIdx = !!baseIdx && isFinite(imn) && isFinite(imx);
    if (hasIdx) { const p = (imx - imn) * 0.2 || 0.5; imn -= p; imx += p; }
    const YI = v => Tp + (imx - v) / ((imx - imn) || 1) * (H - B - Tp);

    let g = '';
    for (let k = 0; k <= 4; k++) {
      const y = Tp + k * (H - B - Tp) / 4;
      g += '<line x1="' + Lf + '" y1="' + y + '" x2="' + (W - R) + '" y2="' + y + '" stroke="#2A2F39" stroke-width="1"/>';
    }
    let axL = '', axR = '';
    for (let k = 0; k <= 4; k++) {
      const f = k / 4, y = Tp + f * (H - B - Tp);
      axL += '<text x="' + (Lf - 8) + '" y="' + (y + 4) + '" fill="#8A93A3" font-size="10.5" text-anchor="end" font-family="Consolas">'
        + (mx - f * (mx - mn)).toFixed(2) + '</text>';
      if (hasIdx) axR += '<text x="' + (W - R + 8) + '" y="' + (y + 4) + '" fill="#9B6BFF" font-size="10.5" font-family="Consolas">'
        + (imx - f * (imx - imn)).toFixed(1) + '</text>';
    }
    let xt = '';
    const NL = Math.min(7, n);
    for (let k = 0; k < NL; k++) {
      const i = view.i0 + Math.round(k * (n - 1) / ((NL - 1) || 1));
      const isLast = (k === NL - 1);
      const lab = n > 80 ? rows[i].date.slice(0, 7) : rows[i].date.slice(5);
      xt += '<text x="' + (isLast ? (W - R) : X(i)) + '" y="' + (H - 8) + '" fill="#4a5160" font-size="10.5" '
        + (isLast ? 'text-anchor="end"' : 'text-anchor="middle"') + ' font-family="Consolas">' + lab + '</text>';
    }

    let idxPath = '';
    if (hasIdx) {
      let d = '', on = false;
      for (let i = view.i0; i <= view.i1; i++) {
        const v = idxMap[rows[i].date];
        if (v === null || v === undefined || isNaN(v)) { on = false; continue; }
        d += (on ? 'L' : 'M') + X(i).toFixed(1) + ' ' + YI(v).toFixed(1) + ' ';
        on = true;
      }
      if (d) idxPath = '<path d="' + d + '" fill="none" stroke="#9B6BFF" stroke-width="1.6" opacity="0.9" stroke-linejoin="round"/>';
    }

    let ratePaths = '';
    for (const s of series) {
      let d = '', on = false;
      for (let i = view.i0; i <= view.i1; i++) {
        const v = rows[i][s.key];
        if (v === null || v === undefined || isNaN(v)) { on = false; continue; }
        d += (on ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1) + ' ';
        on = true;
      }
      if (!d) continue;
      ratePaths += '<path d="' + d + '" fill="none" stroke="' + s.col + '" stroke-width="' + s.w + '"'
        + (s.dash ? ' stroke-dasharray="' + s.dash + '"' : '') + ' stroke-linejoin="round"/>';
    }

    // 走廊带与政策锚：裁剪到画布内，不撑开 Y 轴（避免压扁利率线）
    const yBandTop = Y(POLICY.rate + BAND), yBandBot = Y(POLICY.rate - BAND);
    const cTop = Math.max(Tp, Math.min(H - B, yBandTop));
    const cBot = Math.max(Tp, Math.min(H - B, yBandBot));
    let refLayer = '';
    if (cBot > cTop) {
      refLayer += '<rect x="' + Lf + '" y="' + cTop.toFixed(1) + '" width="' + (W - Lf - R) + '" height="' + (cBot - cTop).toFixed(1) + '" fill="#B5D4F4" opacity="0.16"/>';
      if (yBandTop >= Tp && yBandTop <= H - B) {
        refLayer += '<line x1="' + Lf + '" y1="' + yBandTop.toFixed(1) + '" x2="' + (W - R) + '" y2="' + yBandTop.toFixed(1) + '" stroke="#85B7EB" stroke-width="1" stroke-dasharray="5 4"/>';
      }
      if (yBandBot >= Tp && yBandBot <= H - B) {
        refLayer += '<line x1="' + Lf + '" y1="' + yBandBot.toFixed(1) + '" x2="' + (W - R) + '" y2="' + yBandBot.toFixed(1) + '" stroke="#85B7EB" stroke-width="1" stroke-dasharray="5 4"/>';
      }
    }
    const yAnc = Y(POLICY.rate);
    if (yAnc >= Tp && yAnc <= H - B) {
      refLayer += '<line x1="' + Lf + '" y1="' + yAnc.toFixed(1) + '" x2="' + (W - R) + '" y2="' + yAnc.toFixed(1) + '" stroke="#1FB37A" stroke-width="1.6" stroke-dasharray="6 4"/>'
        + '<text x="' + (W - R - 5) + '" y="' + (yAnc - 5).toFixed(1) + '" fill="#1FB37A" font-size="10.5" text-anchor="end">政策锚 ' + POLICY.rate.toFixed(2) + '%</text>';
    }
    if (firstDr >= view.i0 && firstDr <= view.i1 && firstDr > view.i0) {
      const fx = X(firstDr).toFixed(1);
      refLayer += '<line x1="' + fx + '" y1="' + Tp + '" x2="' + fx + '" y2="' + (H - B) + '" stroke="#8A93A3" stroke-width="0.8" stroke-dasharray="3 3"/>'
        + '<text x="' + (Number(fx) + 4).toFixed(1) + '" y="' + (Tp + 11) + '" fill="#8A93A3" font-size="10">DR001 数据起点 ' + esc(rows[firstDr].date.slice(5)) + '</text>';
    }

    svg.innerHTML = g + refLayer + axL + axR + idxPath + ratePaths + xt;

    // 副图：DR001 距政策锚的偏离（bp）放大显示，并叠加沪深300 归一（右轴）作对照
    const devSvg = $('liqCnDevChart');
    if (devSvg) {
      const DH = 120, DT = 14, DB = 20;
      let devs = [], dm = 8;
      for (let i = view.i0; i <= view.i1; i++) {
        const v = rows[i].dr001;
        const d = (v === null || v === undefined || isNaN(v)) ? null : (v - POLICY.rate) * 100;
        devs.push(d);
        if (d !== null) dm = Math.max(dm, Math.abs(d) * 1.35);
      }
      dm = Math.min(60, Math.ceil(dm));
      const DY = v => DT + (dm - v) / (2 * dm) * (DH - DB - DT);
      const DYI = v => DT + (imx - v) / ((imx - imn) || 1) * (DH - DB - DT);
      let dg = '';
      for (let k = 0; k <= 2; k++) {
        const y = DT + k * (DH - DB - DT) / 2;
        dg += '<line x1="' + Lf + '" y1="' + y.toFixed(1) + '" x2="' + (W - R) + '" y2="' + y.toFixed(1) + '" stroke="#2A2F39" stroke-width="1"/>';
      }
      dg += '<line x1="' + Lf + '" y1="' + DY(0).toFixed(1) + '" x2="' + (W - R) + '" y2="' + DY(0).toFixed(1) + '" stroke="#1FB37A" stroke-width="1.2" stroke-dasharray="5 4"/>';
      if (POLICY.bandBp <= dm) {
        dg += '<line x1="' + Lf + '" y1="' + DY(POLICY.bandBp).toFixed(1) + '" x2="' + (W - R) + '" y2="' + DY(POLICY.bandBp).toFixed(1) + '" stroke="#85B7EB" stroke-width="1" stroke-dasharray="4 3"/>';
        dg += '<line x1="' + Lf + '" y1="' + DY(-POLICY.bandBp).toFixed(1) + '" x2="' + (W - R) + '" y2="' + DY(-POLICY.bandBp).toFixed(1) + '" stroke="#85B7EB" stroke-width="1" stroke-dasharray="4 3"/>';
      }
      let dax = '';
      dax += '<text x="' + (Lf - 8) + '" y="' + (DT + 4) + '" fill="#8A93A3" font-size="10.5" text-anchor="end">+' + dm + 'bp</text>';
      dax += '<text x="' + (Lf - 8) + '" y="' + (DY(0) + 4).toFixed(1) + '" fill="#1FB37A" font-size="10.5" text-anchor="end">0</text>';
      dax += '<text x="' + (Lf - 8) + '" y="' + (DH - DB + 4) + '" fill="#8A93A3" font-size="10.5" text-anchor="end">-' + dm + 'bp</text>';
      let didx = '', don = false;
      if (hasIdx) {
        for (let i = view.i0; i <= view.i1; i++) {
          const v = idxMap[rows[i].date];
          if (v === null || v === undefined || isNaN(v)) { don = false; continue; }
          didx += (don ? 'L' : 'M') + X(i).toFixed(1) + ' ' + DYI(v).toFixed(1) + ' ';
          don = true;
        }
        if (didx) didx = '<path d="' + didx + '" fill="none" stroke="#9B6BFF" stroke-width="1.5" opacity="0.6" stroke-linejoin="round"/>';
      }
      let dpath = '', don2 = false, lastD = null, lastX = null;
      for (let i = view.i0; i <= view.i1; i++) {
        const d = devs[i - view.i0];
        if (d === null) { don2 = false; continue; }
        dpath += (don2 ? 'L' : 'M') + X(i).toFixed(1) + ' ' + DY(d).toFixed(1) + ' ';
        don2 = true; lastD = d; lastX = X(i);
      }
      if (dpath) dpath = '<path d="' + dpath + '" fill="none" stroke="#22D3EE" stroke-width="2.4" stroke-linejoin="round"/>';
      if (lastD !== null) {
        dpath += '<circle cx="' + lastX.toFixed(1) + '" cy="' + DY(lastD).toFixed(1) + '" r="3.5" fill="#22D3EE"/>'
          + '<text x="' + (lastX - 6).toFixed(1) + '" y="' + (DY(lastD) - 8).toFixed(1) + '" fill="#22D3EE" font-size="11" text-anchor="end">' + bp(lastD) + '</text>';
      }
      if (firstDr >= view.i0 && firstDr <= view.i1 && firstDr > view.i0) {
        dpath += '<line x1="' + X(firstDr).toFixed(1) + '" y1="' + DT + '" x2="' + X(firstDr).toFixed(1) + '" y2="' + (DH - DB) + '" stroke="#8A93A3" stroke-width="0.8" stroke-dasharray="3 3"/>';
      }
      devSvg.innerHTML = dg + dax + didx + dpath;
    }
    GR = {X: X, n: n};

    const zr = $('liqCnRange');
    if (zr) zr.textContent = '当前 ' + n + ' 个交易日：' + rows[view.i0].date + ' ~ ' + rows[view.i1].date + '（共 ' + N + ' 天）';
    for (const b of $('liqCnBar').querySelectorAll('.zbtn')) {
      const len = Number(b.dataset.len);
      const on = len < 0 ? false : (len === 0 ? n === N : len === n);
      b.classList.toggle('on', on);
    }
  }

  function setLen(len){
    if (len === -1) { view.i1 = N - 1; view.i0 = Math.max(0, N - 250); }
    else if (len <= 0 || len >= N) { view.i0 = 0; view.i1 = N - 1; }
    else { view.i1 = N - 1; view.i0 = Math.max(0, N - len); }
    render();
  }
  for (const b of $('liqCnBar').querySelectorAll('.zbtn')) b.addEventListener('click', () => setLen(Number(b.dataset.len)));
  attachZoom(svg, view, N, render, Lf, R);

  svg.addEventListener('mousemove', ev => {
    if (!GR) return;
    const rc = svg.getBoundingClientRect();
    const px = (ev.clientX - rc.left) / rc.width * 1000;
    let i = view.i0 + Math.round((px - Lf) / Math.max(1, (W - Lf - R)) * (GR.n - 1));
    i = Math.max(view.i0, Math.min(view.i1, i));
    const r = rows[i];
    let h = '<b>' + esc(r.date) + '</b>'
      + '<div style="color:#1FB37A">政策锚 ' + POLICY.rate.toFixed(2) + '%</div>'
      + '<div style="color:#22D3EE">DR001 ' + (r.dr001 == null ? '—' : fmt(r.dr001, 3) + '%（距锚 ' + bp(devBp(r.dr001)) + '）') + '</div>'
      + '<div style="color:#FF8A1F">DR007 ' + (r.dr007 == null ? '—' : fmt(r.dr007, 3) + '%') + '</div>'
      + '<div style="color:#4C9AFF">SHIBOR 3M ' + (r.shibor_3m == null ? '—' : fmt(r.shibor_3m, 3) + '%') + '</div>'
      + '<div style="color:#8A93A3">SHIBOR 隔夜 O/N ' + (r.shibor_on == null ? '—' : fmt(r.shibor_on, 3) + '%') + '</div>';
    if (baseIdx) {
      const iv = idxMap[r.date];
      h += '<div style="color:#9B6BFF">' + esc(idxName) + ' 归一 ' + (iv === null || iv === undefined ? '—' : iv.toFixed(1)) + '</div>';
    }
    const tip = $('liqCnTip');
    tip.innerHTML = h; tip.style.display = 'block';
    const br = $('liqCnPanel').getBoundingClientRect();
    let lx = ev.clientX - br.left + 16;
    if (lx + 200 > br.width) lx = ev.clientX - br.left - 196;
    tip.style.left = lx + 'px';
    tip.style.top = (ev.clientY - br.top + 14) + 'px';
  });
  svg.addEventListener('mouseleave', () => { $('liqCnTip').style.display = 'none'; });

  render();
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
      + '<span class="nmx" title="' + esc(r.name || '') + '">' + esc(r.name || '—') + '</span>'
      + '<div class="ptrack"><div class="zero" style="left:50%"></div>'
      + '<div class="fill" style="left:' + left.toFixed(2) + '%;width:' + Math.max(w, 0.4).toFixed(2)
      + '%;background:' + col + '"></div></div>'
      + '<span class="vv" style="color:' + col + '">'
      + (v === null || v === undefined ? '—' : (v >= 0 ? '+' : '') + v.toFixed(3) + '%')
      + (r.stale ? '<span style="color:#F5A623;font-size:10px"> *</span>' : '') + '</span></div>';
  }
  $('premBox').innerHTML = h;
})();

/* ══════════ ⑬ 国债收益率曲线 ══════════ */
(function renderRates(){
  const S = D.signals;
  if (!S || !S.rates) return;
  const R = S.rates;
  const rows = (R.data || []).filter(r => r && r.date);
  if (rows.length < 5) return;
  $('ratesPanel').style.display = '';

  const lt = R.latest || {}, dv = R.derived || {};
  const n = rows.length;
  const pp = v => (v === null || v === undefined) ? '—' : Number(v).toFixed(3) + '%';
  const bp = v => (v === null || v === undefined) ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(1) + ' bp';
  // 利率上行＝无风险利率走高＝对权益估值不利，按 A 股习惯标红；下行标绿
  const bpc = v => (v === null || v === undefined) ? 'var(--sub)' : (v > 0 ? 'var(--up)' : (v < 0 ? 'var(--down)' : 'var(--txt)'));

  const inverted = dv.inverted === true;
  $('ratesHint').innerHTML = '国债到期收益率是<b>无风险利率</b>，整条曲线同时隐含增长与通胀预期。'
    + '与 ⑨ 的区别：⑨ 看的是银行间<b>资金价格</b>（DR007/SHIBOR，短端、政策驱动，回答「钱紧不紧」），'
    + '本节看的是<b>债券收益率曲线</b>（回答「钱贵不贵」）——算股债性价比时分母用的就是 10Y 国债。'
    + '利差走阔 / 走平的判读随下方所选期限段而变，见切换条右侧的提示。'
    + '<br><b>本面板两张图的横轴不同</b>：上图是<b>期限</b>（2Y→30Y），三条线是同一条曲线在三个日期的三张快照；'
    + '下图是<b>交易日</b>，把某一段期限利差逐日连成一条线（下方按钮可切换 10Y−2Y / 30Y−10Y）。'
    + '上图每条线上所选两个期限点的落差，就是下图在那一天的一个点 —— 下图画的是上图的斜率，不是另一个指标。'
    + (inverted ? '　<span style="color:var(--up)">当前 10Y−2Y 已倒挂。</span>' : '')
    + '　数据源：东财 datacenter（国债到期收益率）。';

  // ── 卡片 ──
  let ch = '';
  const ma = dv.cn_10y_ma20;
  const dev = (lt.cn_10y !== null && lt.cn_10y !== undefined && ma !== null && ma !== undefined)
    ? (lt.cn_10y - ma) * 100 : null;
  ch += '<div class="card"><div class="k">10Y 国债 · 无风险利率基准</div>'
    + '<div class="v" style="color:var(--orange)">' + pp(lt.cn_10y) + '</div>'
    + '<div class="d">20 日均 ' + (ma === null || ma === undefined ? '—' : Number(ma).toFixed(3) + '%')
    + '｜偏离 <span style="color:' + bpc(dev) + '">' + bp(dev) + '</span></div></div>';
  ch += '<div class="card"><div class="k">2Y 国债 · 短端（贴政策利率）</div>'
    + '<div class="v" style="color:var(--cyan)">' + pp(lt.cn_2y) + '</div>'
    + '<div class="d">5Y ' + pp(lt.cn_5y) + '｜5Y−2Y ' + bp(lt.cn_5y_2y === null || lt.cn_5y_2y === undefined ? null : lt.cn_5y_2y * 100) + '</div></div>';
  ch += '<div class="card"><div class="k">30Y 国债 · 长端（含增长预期）</div>'
    + '<div class="v" style="color:var(--blue)">' + pp(lt.cn_30y) + '</div>'
    + '<div class="d">30Y−10Y ' + bp(lt.cn_30y_10y === null || lt.cn_30y_10y === undefined ? null : lt.cn_30y_10y * 100)
    + '｜10Y 近20日 <span style="color:' + bpc(dv.cn_10y_chg_20d_bp) + '">' + bp(dv.cn_10y_chg_20d_bp) + '</span></div></div>';
  ch += '<div class="card"><div class="k">10Y − 2Y 期限利差</div>'
    + '<div class="v" style="color:' + (inverted ? 'var(--up)' : 'var(--txt)') + '">'
    + bp(lt.cn_10y_2y === null || lt.cn_10y_2y === undefined ? null : lt.cn_10y_2y * 100) + '</div>'
    + '<div class="d">' + (inverted ? '倒挂（10Y &lt; 2Y）' : (lt.cn_10y_2y > 0.005 ? '正常陡峭' : '平坦'))
    + '｜近 20 日 <span style="color:' + bpc(dv.cn_10y_2y_chg_20d_bp) + '">' + bp(dv.cn_10y_2y_chg_20d_bp) + '</span></div></div>';
  $('ratesCards').innerHTML = ch;

  // ── 曲线形态：当期 vs 60 日前 vs 250 日前 ──
  const TEN = [['2Y', 'cn_2y'], ['5Y', 'cn_5y'], ['10Y', 'cn_10y'], ['30Y', 'cn_30y']];
  const snaps = [
    {i: n - 1, name: '当期', col: '#FF8A1F', w: 2.6, dash: ''},
    {i: Math.max(0, n - 61), name: '60 日前', col: '#4C9AFF', w: 1.6, dash: '5 4'},
    {i: 0, name: '约一年前', col: '#8A93A3', w: 1.4, dash: '2 4'}
  ];
  let vals = [];
  for (const s of snaps) {
    const r = rows[s.i];
    if (!r) continue;
    for (const [, k] of TEN) if (r[k] !== null && r[k] !== undefined) vals.push(r[k]);
  }
  if (vals.length) {
    const W = 1000, H = 300, Lf = 62, Rr = 96, Tp = 22, B = 36;
    let mn = Math.min(...vals), mx = Math.max(...vals);
    const pd = (mx - mn) * 0.22 || 0.05; mn -= pd; mx += pd;
    const x = i => Lf + i * (W - Lf - Rr) / (TEN.length - 1);
    const y = v => Tp + (mx - v) / (mx - mn) * (H - B - Tp);

    let g = '';
    for (let k = 0; k <= 4; k++) {
      const yy = Tp + k * (H - B - Tp) / 4, vv = mx - (mx - mn) * k / 4;
      g += '<line x1="' + Lf + '" y1="' + yy + '" x2="' + (W - Rr) + '" y2="' + yy + '" stroke="#2A2F39" stroke-width="1"/>'
        + '<text x="' + (Lf - 8) + '" y="' + (yy + 4) + '" fill="#8A93A3" font-size="10.5" text-anchor="end" '
        + 'font-family="Consolas">' + vv.toFixed(2) + '%</text>';
    }
    // 横轴期限标签
    for (let i = 0; i < TEN.length; i++) {
      g += '<text x="' + x(i) + '" y="' + (H - 12) + '" fill="#8A93A3" font-size="11.5" text-anchor="middle" '
        + 'font-family="Consolas">' + TEN[i][0] + '</text>';
    }
    const labels = [];
    for (const s of snaps) {
      const r = rows[s.i];
      if (!r) continue;
      let d = '', on = false, lastX = 0, lastY = 0;
      for (let i = 0; i < TEN.length; i++) {
        const v = r[TEN[i][1]];
        if (v === null || v === undefined) { on = false; continue; }
        d += (on ? 'L' : 'M') + x(i).toFixed(1) + ' ' + y(v).toFixed(1) + ' ';
        on = true; lastX = x(i); lastY = y(v);
      }
      if (!d) continue;
      g += '<path d="' + d + '" fill="none" stroke="' + s.col + '" stroke-width="' + s.w + '"'
        + (s.dash ? ' stroke-dasharray="' + s.dash + '"' : '') + ' stroke-linejoin="round"/>';
      for (let i = 0; i < TEN.length; i++) {
        const v = r[TEN[i][1]];
        if (v === null || v === undefined) continue;
        g += '<circle cx="' + x(i) + '" cy="' + y(v) + '" r="' + (s.name === '当期' ? 3.6 : 2.2) + '" fill="' + s.col + '"/>';
      }
      labels.push({x: lastX + 9, y: lastY + 4, col: s.col, txt: s.name + ' ' + String(r.date).slice(5)});
    }
    // 三条曲线的末端可能落在非常接近的高度上（尤其 30Y 附近），
    // 直接按各自 y 写标签会糊成一团。这里按 y 排序后强制拉开 13px 最小间距。
    labels.sort((a, b) => a.y - b.y);
    for (let i = 1; i < labels.length; i++) {
      if (labels[i].y - labels[i - 1].y < 13) labels[i].y = labels[i - 1].y + 13;
    }
    for (const L of labels) {
      g += '<text x="' + L.x.toFixed(1) + '" y="' + L.y.toFixed(1) + '" fill="' + L.col + '" font-size="10.5" '
        + 'font-family="Consolas">' + esc(L.txt) + '</text>';
    }
    $('ratesCurve').innerHTML = g;
  }

  // ── 期限利差历史（可切换 10Y−2Y / 30Y−10Y）──
  // 切换的不只是数据：判读口径、小标题、右侧提示都要跟着换，
  // 否则 30Y−10Y 会被误读成美债 10Y−2Y 倒挂那套衰退叙事。
  const SPREADS = {
    cn_10y_2y: {
      sub: '10Y − 2Y 期限利差（横轴＝交易日）：上图每条线 2Y→10Y 的落差＝这条曲线上的一个点　｜　单位 bp，负值＝倒挂',
      hint: '短端贴政策利率；利差走阔多对应宽松预期升温，为负＝倒挂（市场定价强宽松）'
    },
    cn_30y_10y: {
      sub: '30Y − 10Y 超长端期限溢价（横轴＝交易日）：上图每条线 10Y→30Y 的落差＝这条曲线上的一个点　｜　单位 bp，负值＝超长端倒挂',
      hint: '衡量长端相对中端的额外补偿；走阔＝长端要求更高溢价（供给 / 增长预期 / 久期），走平＝溢价压缩'
    }
  };
  function drawSpread(key) {
    const cfg = SPREADS[key];
    $('ratesSpreadSub').textContent = cfg.sub;
    $('ratesSpreadHint').textContent = cfg.hint;
    const sp = rows.map(r => (r[key] === null || r[key] === undefined) ? null : r[key] * 100);
    const sv = sp.filter(v => v !== null);
    if (sv.length < 5) { $('ratesSpread').style.display = 'none'; return; }
    $('ratesSpread').style.display = '';
    const W = 1000, H = 170, Lf = 62, Rr = 30, Tp = 14, B = 26;
    let mn = Math.min(0, ...sv), mx = Math.max(0, ...sv);
    const pd = (mx - mn) * 0.18 || 1; mn -= pd; mx += pd;
    const X = i => Lf + i * (W - Lf - Rr) / Math.max(1, n - 1);
    const Y = v => Tp + (mx - v) / (mx - mn) * (H - B - Tp);
    let g = '';
    for (let k = 0; k <= 3; k++) {
      const yy = Tp + k * (H - B - Tp) / 3, vv = mx - (mx - mn) * k / 3;
      g += '<line x1="' + Lf + '" y1="' + yy + '" x2="' + (W - Rr) + '" y2="' + yy + '" stroke="#2A2F39" stroke-width="1"/>'
        + '<text x="' + (Lf - 8) + '" y="' + (yy + 4) + '" fill="#8A93A3" font-size="10.5" text-anchor="end" '
        + 'font-family="Consolas">' + vv.toFixed(0) + '</text>';
    }
    // 零轴：所选期限段倒挂的分界（两种口径含义不同，见切换提示）
    g += '<line x1="' + Lf + '" y1="' + Y(0) + '" x2="' + (W - Rr) + '" y2="' + Y(0) + '" stroke="#E8453C" '
      + 'stroke-width="1" stroke-dasharray="4 4" opacity="0.75"/>'
      + '<text x="' + (W - Rr + 3) + '" y="' + (Y(0) + 4) + '" fill="#E8453C" font-size="10" font-family="Consolas">0</text>';
    let d = '', on = false;
    for (let i = 0; i < n; i++) {
      const v = sp[i];
      if (v === null) { on = false; continue; }
      d += (on ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1) + ' ';
      on = true;
    }
    g += '<path d="' + d + '" fill="none" stroke="#FF8A1F" stroke-width="1.9" stroke-linejoin="round"/>';
    const lv = sv[sv.length - 1];
    g += '<circle cx="' + X(n - 1) + '" cy="' + Y(lv) + '" r="3.2" fill="#FF8A1F"/>'
      + '<text x="' + (X(n - 1) - 6) + '" y="' + (Y(lv) - 8) + '" fill="#FF8A1F" font-size="11" '
      + 'text-anchor="end" font-family="Consolas">' + lv.toFixed(1) + ' bp</text>'
      + '<text x="' + Lf + '" y="' + (H - 7) + '" fill="#6b7484" font-size="10.5" font-family="Consolas">' + esc(rows[0].date) + '</text>'
      + '<text x="' + (W - Rr) + '" y="' + (H - 7) + '" fill="#6b7484" font-size="10.5" text-anchor="end" font-family="Consolas">'
      + esc(rows[n - 1].date) + '</text>';
    $('ratesSpread').innerHTML = g;
  }
  const spreadTabs = $('ratesSpreadTabs');
  for (const b of spreadTabs.querySelectorAll('.zbtn')) {
    b.addEventListener('click', () => {
      for (const x of spreadTabs.querySelectorAll('.zbtn')) x.classList.toggle('on', x === b);
      drawSpread(b.dataset.sp);
    });
  }
  drawSpread('cn_10y_2y');
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

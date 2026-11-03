# -*- coding: utf-8 -*-
"""
三合一高清监测图（PNG）

行 1：沪深300 持仓占比 vs 沪深300（双轴 + 劈叉区阴影）
行 2：创业板 持仓占比 vs 创业板指（双轴 + 劈叉区阴影）
行 3：宏观 LSI 压力指数（左轴 bps） vs 美联储净流动性 GLI（右轴 T）
行 4：三大风格 / 股债比价全周期百分位刻度条
"""
import json, os, sys, re, datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties

import common
from config import ORDER, UP_COLOR, DOWN_COLOR

BASE = common.BASE
PNG = os.path.join(BASE, 'etf_lsi_monitor_latest.png')

BG, PANEL, GRID = '#181A20', '#1E2128', '#2A2F39'
TXT, SUB = '#D6DAE1', '#8A93A3'
ORANGE, PURPLE = '#FF8A1F', '#9B6BFF'
UP, DOWN = UP_COLOR, DOWN_COLOR
BLUE, CYAN = '#4C8DFF', '#22D3EE'

_FP = common.find_cjk_font()
FP = FontProperties(fname=_FP) if _FP else None


def fp(size=11, **kw):
    return dict(fontproperties=FP, fontsize=size, **kw) if FP else dict(fontsize=size, **kw)


def fp_legend(size=9.5, **kw):
    """legend 不接受 fontproperties，需用 prop"""
    return dict(prop=FP, fontsize=size, **kw) if FP else dict(fontsize=size, **kw)


# matplotlib 的中文字体（微软雅黑 / Noto CJK）不含 emoji，绘标题前先剔除，避免 Glyph missing 警告
_EMOJI = re.compile('['
                    '\U0001F000-\U0001FAFF'   # 表情符号
                    '\U00002600-\U000027BF'   # 杂项符号与装饰符号
                    '\U00002B00-\U00002BFF'
                    '\U00002190-\U000021FF'   # 箭头
                    '\U0000FE0F\U000020E3'    # 变体选择符 / 组合键帽
                    ']+')


def no_emoji(s):
    return _EMOJI.sub('', str(s)).strip()


def load(name, default=None):
    p = os.path.join(BASE, name)
    if not os.path.exists(p):
        return default
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default


def draw_divergence(ax, dates, hold, idx, spread, lbl, title):
    axb = ax.twinx()
    # 劈叉/背离区域阴影（合并连续区间）
    i = 1
    while i < len(spread):
        if abs(spread[i]) >= 25:
            j = i
            while j + 1 < len(spread) and abs(spread[j + 1]) >= 25:
                j += 1
            col = UP if spread[j] > 0 else DOWN
            ax.axvspan(dates[i - 1], dates[j], color=col, alpha=0.10, lw=0, zorder=0)
            i = j + 1
        else:
            i += 1
    ax.plot(dates, hold, color=ORANGE, lw=2.5, solid_capstyle='round', zorder=4,
            label='%s  [橙线]' % lbl['hold'])
    axb.plot(dates, idx, color=PURPLE, lw=2.3, solid_capstyle='round', zorder=4,
             label='%s 收盘价（点）  [紫线]' % lbl['idx_div'].replace('流通市值', ''))
    ax.scatter([dates[-1]], [hold[-1]], color=ORANGE, s=64, zorder=6,
               edgecolors=BG, linewidths=1.5)
    axb.scatter([dates[-1]], [idx[-1]], color=PURPLE, s=56, zorder=6,
                edgecolors=BG, linewidths=1.5)
    # 注意：lbl['hold'] 本身已以 (%) 结尾，这里不能再拼一次 (%%)
    ax.set_ylabel('%s   [橙线]' % lbl['hold'], color=ORANGE, **fp(11))
    axb.set_ylabel('%s 收盘价（点）   [紫线]' % lbl['idx_div'].replace('流通市值', ''),
                   color=PURPLE, **fp(11))
    ax.set_title(title, **fp(13, color=TXT, pad=8))
    ax.grid(True, color=GRID, lw=0.6, alpha=0.65)
    ax.set_axisbelow(True)
    for a in (ax, axb):
        a.tick_params(labelsize=9)
    lines = ax.get_lines() + axb.get_lines()
    ax.legend(lines, [l.get_label() for l in lines], loc='upper left',
              facecolor=PANEL, edgecolor=GRID, labelcolor=TXT, **fp_legend(9.5))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    return axb


def main():
    summary = load('summary.json')
    if not summary or not summary.get('tracks'):
        print('!! 缺少 summary.json，请先运行 analyze_report.py')
        sys.exit(1)
    packs = {k: load('series_%s.json' % k) for k in ORDER}
    packs = {k: v for k, v in packs.items() if v}
    lsi = load('lsi.json')
    ratios = load('ratios.json')

    nrow = 2 + (1 if lsi else 0) + (1 if ratios else 0)
    hr = [3.0, 3.0] + ([2.1] if lsi else []) + ([1.5] if ratios else [])
    fig = plt.figure(figsize=(17, 5.0 * nrow), dpi=135)
    gs = fig.add_gridspec(nrow, 1, height_ratios=hr, hspace=0.32,
                          left=0.095, right=0.945, top=0.935, bottom=0.055)

    plt.rcParams['figure.facecolor'] = BG
    plt.rcParams['axes.facecolor'] = PANEL
    plt.rcParams['savefig.facecolor'] = BG
    plt.rcParams['axes.edgecolor'] = GRID
    plt.rcParams['text.color'] = TXT
    plt.rcParams['axes.labelcolor'] = TXT
    plt.rcParams['xtick.color'] = SUB
    plt.rcParams['ytick.color'] = SUB

    r = 0
    for key in ORDER:
        pk = packs.get(key)
        if not pk:
            continue
        ax = fig.add_subplot(gs[r, 0])
        # 看板可以缩放到 5 年，但这张 PNG 只画最近 250 个交易日：
        # 1212 天塞进一张 17 英寸宽的图，线会糊成一团，反而看不出背离。
        PN = min(250, len(pk['dates']))
        dates = [datetime.datetime.strptime(d, '%Y-%m-%d').date() for d in pk['dates'][-PN:]]
        S = pk['summary']
        draw_divergence(ax, dates, pk['hold'][-PN:], pk['idx'][-PN:], pk['spread'][-PN:], S['labels'],
                        no_emoji('%s · %s（截至 %s｜Spread %+.1f）' % (S['title'], S['status'], S['date'], S['spread'])))
        r += 1

    # ---- 行 3：LSI vs GLI ----
    if lsi:
        ax = fig.add_subplot(gs[r, 0])
        cal = lsi.get('cal', [])
        h = lsi.get('hist', {}) or {}
        dts = [datetime.datetime.strptime(d, '%Y-%m-%d').date() for d in cal]
        lsi_v = h.get('lsi') or []
        gli_v = h.get('gli') or []
        m = min(len(dts), len(lsi_v), len(gli_v))
        # 只画最近 260 个观测日：与前两行（250 交易日）及看板周期对齐，
        # 否则 820 天全画会密到看不出波动
        m = min(m, 260)
        dts, lsi_v, gli_v = dts[-m:], lsi_v[-m:], gli_v[-m:]
        axb = ax.twinx()
        # 显式持有 Line2D 句柄：ax.get_lines() 会把 axhline 的阈值虚线也算进去，
        # 按索引取会把红色阈值虚线误当成 GLI 蓝线的图例
        l_lsi, = ax.plot(dts, lsi_v, color=ORANGE, lw=2.2, solid_capstyle='round',
                         label='LSI 压力指数（bps）')
        l_gli, = axb.plot(dts, gli_v, color=BLUE, lw=2.2, solid_capstyle='round',
                          label='美联储净流动性 GLI（T）')
        ax.axhline(20, color=UP, lw=1.0, ls='--', alpha=0.85)
        ax.axhline(50, color='#8B1A1A', lw=1.0, ls='--', alpha=0.85)
        ax.axhline(-30, color=DOWN, lw=1.0, ls='--', alpha=0.85)
        ax.set_ylabel('LSI（bps）', color=ORANGE, **fp(11))
        axb.set_ylabel('GLI（万亿美元 T）', color=BLUE, **fp(11))
        ax.set_title(no_emoji('模块三 · 美元宏观流动性压力指数 LSI vs 美联储净流动性 GLI（截至 %s｜%s｜%d/%d 项报警）'
                              % (lsi.get('asof', ''), lsi.get('state', ''),
                                 lsi.get('alert_count', 0), lsi.get('total', 20))),
                     **fp(13, color=TXT, pad=8))
        ax.grid(True, color=GRID, lw=0.6, alpha=0.65)
        ax.set_axisbelow(True)
        ax.legend([l_lsi, l_gli], ['LSI 压力指数（bps）  [橙线]', 'GLI 净流动性（T）  [蓝线]'],
                  loc='upper left', facecolor=PANEL, edgecolor=GRID, labelcolor=TXT, **fp_legend(9.5))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%y-%m'))
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.tick_params(labelsize=9)
        axb.tick_params(labelsize=9)
        r += 1

    # ---- 行 4：三大比价百分位刻度条 ----
    if ratios and ratios.get('items'):
        ax = fig.add_subplot(gs[r, 0])
        keys = [k for k in ratios.get('order', []) if k in ratios['items']]
        ys = list(range(len(keys)))[::-1]
        for y, k in zip(ys, keys):
            it = ratios['items'][k]
            pct = it['pct']
            ax.barh(y, 100, color=GRID, height=0.34, alpha=0.5)
            col = UP if it['level'] == 'high' else (DOWN if it['level'] == 'low' else '#8A93A3')
            ax.barh(y, pct, color=col, height=0.34, alpha=0.9)
            ax.plot([pct], [y], marker='D', color='#FFFFFF', markersize=7, zorder=5)
            # 名称写在条形上方（图内），避免长中文标签被左边界截断
            ax.text(0, y + 0.30, no_emoji('%s ÷ %s' % (it.get('num_short', ''), it.get('den_short', ''))),
                    va='bottom', **fp(11, color=TXT))
            ax.text(101.5, y, '%.1f%%（%s）' % (pct, no_emoji(it['word'])), va='center', **fp(10, color=TXT))
        ax.set_yticks([])
        ax.set_ylim(-0.45, len(keys) - 0.15)
        ax.set_xlim(0, 122)
        ax.set_xticks([0, 20, 35, 50, 65, 80, 100])
        for x, c, t in ((20, DOWN, '极端偏低'), (80, UP, '极端偏高')):
            ax.axvline(x, color=c, lw=1.0, ls='--', alpha=0.9)
        ax.set_title('模块二 · 三大风格 / 股债比价 · 全周期历史百分位（截至 %s，周K口径）'
                     % ratios.get('asof', ''), **fp(13, color=TXT, pad=8))
        ax.grid(True, axis='x', color=GRID, lw=0.6, alpha=0.6)
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=9)
        r += 1

    fig.suptitle('A股双宽基 ETF 持仓背离 + 宏观 LSI 流动性压力 · 三合一监测（%s）'
                 % summary.get('asof', ''), **fp(17, color='#FFFFFF', y=0.982))
    fig.savefig(PNG, facecolor=BG)
    plt.close(fig)          # 释放内存，避免 Actions 上多张大图叠加
    print('已生成', PNG)


if __name__ == '__main__':
    main()

# -*- coding: utf-8 -*-
"""三合一监测系统 · 中央配置

模块一：沪深300 ETF 持仓背离
模块二：创业板 ETF 持仓背离 + 三大风格/股债比价
模块三：美联储宏观流动性压力指数 (LSI) + 20 项背景报警

两套宽基逻辑 100% 同源，仅标的与文案不同，故抽象为 TRACKS 配置字典，
由同一套引擎驱动，避免重复代码。
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))

# ==========================================================================
# 模块一 & 模块二：双宽基赛道
# ==========================================================================
TRACKS = {
    'hs300': {
        'key': 'hs300',
        'name': '沪深300',
        'title': '沪深300（大盘蓝筹国家队）',
        'index_code': 'sh000300',
        'index_name': '沪深300',
        'etfs': {
            'sh510300': '华泰柏瑞300ETF',
            'sh510310': '易方达300ETF',
            'sh510330': '华夏300ETF',
            'sz159919': '嘉实300ETF',
        },
        # (code, name, 显示用纯数字代码)
        'etf_list': [
            ('sh510300', '华泰柏瑞300ETF', '510300'),
            ('sh510310', '易方达300ETF', '510310'),
            ('sh510330', '华夏300ETF', '510330'),
            ('sz159919', '嘉实300ETF', '159919'),
        ],
        'labels': {
            'fund': '头部沪深300ETF',
            'hold': '头部沪深300ETF市值 / 沪深300流通市值 (%)',
            'hold_card': '头部沪深300ETF市值 / 沪深300流通市值',
            'idx_div': '沪深300流通市值',
            'div_title': '双轴对比 · 持仓占比 vs 沪深300',
            'share_tbl': '近5日四只沪深300ETF份额明细',
        },
        'out_prefix': 'csi300',
    },
    'cyb': {
        'key': 'cyb',
        'name': '创业板',
        'title': '创业板（双创成长主力）',
        'index_code': 'sz399006',
        'index_name': '创业板指',
        'etfs': {
            'sz159915': '易方达创业板ETF',
            'sz159949': '华安创业板50ETF',
            'sz159957': '华夏创业板ETF',
            'sz159948': '南方创业板ETF',
        },
        'etf_list': [
            ('sz159915', '易方达创业板ETF', '159915'),
            ('sz159949', '华安创业板50ETF', '159949'),
            ('sz159957', '华夏创业板ETF', '159957'),
            ('sz159948', '南方创业板ETF', '159948'),
        ],
        'labels': {
            'fund': '头部创业板ETF',
            'hold': '头部创业板ETF市值 / 创业板指流通市值 (%)',
            'hold_card': '头部创业板ETF市值 / 创业板指流通市值',
            'idx_div': '创业板指流通市值',
            'div_title': '双轴对比 · 持仓占比 vs 创业板指',
            'share_tbl': '近5日四只创业板ETF份额明细',
        },
        'out_prefix': 'cyb',
    },
}
ORDER = ['hs300', 'cyb']

# ==========================================================================
# 模块二：三大风格 / 股债比价（分子统一为「防御性资产」）
# ==========================================================================
RATIO_PAIRS = [
    {
        'key': 'style_cyb',
        'title': '风格：红利低波 vs 创业板',
        'num': ('sh000922', None, '中证红利低波'),
        'den': ('sz399006', None, '创业板指'),
        'formula': '中证红利低波(000922) ÷ 创业板指(399006)　［均前复权］',
        'high': ('创业板性价比更高', '红利低波已大幅跑赢创业板、处历史高位，进攻端(创业板)均值回归空间大'),
        'low': ('红利低波性价比更高', '创业板已大幅跑赢红利低波、处历史低位，追高性价比下降，偏防守'),
        'up_word': '红利占优', 'down_word': '成长占优',
        'high_tilt': '偏向进攻/创业板', 'low_tilt': '偏向防御/红利低波',
    },
    {
        'key': 'style_star',
        'title': '风格：红利 vs 科创板',
        'num': ('sh000922', None, '中证红利'),
        'den': ('sh000688', None, '科创50'),
        'formula': '中证红利(000922) ÷ 科创50(000688)　［均前复权］',
        'high': ('科创50(科创板)性价比更高', '红利已大幅跑赢科创板、处历史高位，进攻端(科创板)均值回归空间大'),
        'low': ('中证红利性价比更高', '科创板已大幅跑赢红利、处历史低位，追高性价比下降，偏防守'),
        'up_word': '红利占优', 'down_word': '成长占优',
        'high_tilt': '偏向进攻/科创板', 'low_tilt': '偏向防御/红利',
    },
    {
        'key': 'bond',
        'title': '股债性价比：债券 vs 股票',
        'num': ('sh511260', None, '十年国债ETF'),
        'den': ('sh510300', None, '沪深300ETF'),
        'formula': '十年国债ETF(511260) ÷ 沪深300ETF(510300)　［均前复权］',
        'high': ('股票(沪深300)性价比更高', '债券大幅跑赢股票，股票相对处于历史最便宜区域'),
        'low': ('债券(511260)性价比更高', '股票大幅跑赢债券，股票相对处于历史最贵区域'),
        'up_word': '债券占优', 'down_word': '股票占优',
        'high_tilt': '偏向股票', 'low_tilt': '偏向债券',
    },
]

# ==========================================================================
# 模块三：FRED 宏观序列（严格按需求说明书 3.2 单位换算表）
#   unit: pct→bps 乘 100；millions→T 除 1e6；millions→B 除 1e3；billions→T 除 1e3
# ==========================================================================
# 仅在配置了 FRED_API_KEY 环境变量（或 GitHub Actions Secret）时才请求 FRED；
# 未配置则 LSI / 宏观模块自动降级，看板其余部分不受影响。
# 注意：Actions 在未配置该 Secret 时会注入空字符串，这里用 `or` 兜底成空串而非 None。
FRED_API_KEY = (os.environ.get('FRED_API_KEY') or '').strip()

FRED_SERIES = {
    'SOFR':           {'label': '担保隔夜融资利率 SOFR',           'unit': 'pct',      'to': 'bps'},
    'RRPONTSYAWARD':  {'label': '隔夜逆回购奖励利率 RRP Rate',     'unit': 'pct',      'to': 'bps'},
    'EFFR':           {'label': '有效联邦基金利率 EFFR',            'unit': 'pct',      'to': 'bps'},
    'IORB':           {'label': '准备金余额利率 IORB',              'unit': 'pct',      'to': 'bps'},
    'DGS2':           {'label': '2年期美债收益率 US02Y',            'unit': 'pct',      'to': 'bps'},
    'DGS10':          {'label': '10年期美债收益率 US10Y',           'unit': 'pct',      'to': 'bps'},
    'T10YIE':         {'label': '10年期盈亏平衡通胀预期',           'unit': 'pct',      'to': 'bps'},
    'DFII10':         {'label': '10年期实际利率 (TIPS)',            'unit': 'pct',      'to': 'bps'},
    'BAMLH0A0HYM2':   {'label': '美国高收益债信用利差 (OAS)',       'unit': 'pct',      'to': 'bps'},
    'CPIAUCSL':       {'label': '美国 CPI 物价指数',                'unit': 'index',    'to': 'yoy_bps'},
    'WALCL':          {'label': '美联储总资产',                     'unit': 'millions', 'to': 'T'},
    'WTREGEN':        {'label': '财政部一般账户 TGA',                'unit': 'millions', 'to': 'T'},
    'WDTGAL':         {'label': '财政部一般账户 TGA(周)',            'unit': 'millions', 'to': 'B'},
    'RRPONTSYD':      {'label': '隔夜逆回购余额 ON RRP',            'unit': 'billions', 'to': 'T'},
    'WLRRAL':         {'label': '外国官方逆回购池余额',             'unit': 'millions', 'to': 'B'},
    'WRESBAL':        {'label': '银行准备金余额',                   'unit': 'millions', 'to': 'T'},
    'WRBWFRBL':       {'label': '银行准备金余额(周)',                'unit': 'millions', 'to': 'T'},
    'TLAACBM027SBOG': {'label': '美国商业银行总资产',               'unit': 'billions', 'to': 'B'},
    'GDP':            {'label': '美国名义 GDP',                     'unit': 'billions', 'to': 'B'},
    'DTWEXBGS':       {'label': '贸易加权广义美元指数',             'unit': 'index',    'to': 'raw'},
}

# ==========================================================================
# LSI 阈值（严格照搬 TradingView Pine Script v6 原代码）
# ==========================================================================
LSI_TH = {
    'threshold_tight': 20.0,            # LSI 紧张阈值 (bps)
    'threshold_extreme_tight': 50.0,    # LSI 极端紧张 (bps)
    'threshold_extreme_loose': -30.0,   # LSI 极端宽松 (bps)
    'th_t10yie': 2.5,                   # 10Y 通胀预期红色阈值 (%)
    'th_inf_yoy': 3.0,                  # 通胀 YoY 红色阈值 (%)
    'curve_lookback': 10,               # 斜率变动计算周期(天)
    'us02y_drop_th': 20.0,              # 牛陡：2年期暴跌阈值(BP)
    'us10y_spike_th': 20.0,             # 熊陡：10年期暴涨阈值(BP)
    'spread_change_th': 10.0,           # 利差走阔最低阈值(BP)
    'dxy_ma_len': 50,                   # 美元指数趋势 MA 周期
    'credit_roc_len': 10,               # 信用利差动量检测周期(日)
    'credit_roc_th': 10.0,              # 信用利差急升预警阈值(%)
    'gold_th': -350.0,                  # 黄金到顶判定阈值 (EFFR-CPI, bps)
    'credit_th': 400.0,                 # 危机判定信用利差阈值 (bps)
    'reserve_gdp_threshold': 0.11,      # 准备金/GDP 不足阈值
    'reserve_assets_threshold': 0.11,   # 准备金/银行总资产 不足阈值
    'ma_period': 10,                    # 美联储黄金到顶 MA 周期
    'th_real_tight': 2.2,               # 实际利率显著紧缩阈值 (%)
    'th_real_ext_loose': 0.0,           # 实际利率极度宽松阈值 (%)
    'th_breakeven_dev': 0.9,            # 通胀预期 vs 现实偏差 (%)
    'th_stagflation_real': 1.8,         # 滞胀+信用压力双杀 实际利率 (%)
    'th_stagflation_credit': 4.0,       # 滞胀+信用压力双杀 信用利差 (%)
    'gli_lookback': 250,                # GLI 背景判定回溯周期 (日)
    'gli_high_pct': 75,                 # GLI 高位宽松触发点
    'gli_low_pct': 25,                  # GLI 低位收缩触发点
    'gli_mom_lookback': 20,             # GLI 增长率检测周期 (天)
    'gli_mom_threshold': -1.0,          # 周环比骤减报警阈值 (%)
    'flow_lookback': 10,                # V57 资金流向周期 (天)
    'flow_threshold': 5.0,              # 有效动作过滤阈值 (Billion)
    'crisis_rate_infl_delta': 50.0,     # 危机判定：利率与通胀预期收敛阈值 (bps)
    'rrp_peak_window': 500,             # RRP 峰值回溯窗口
    'rrp_exhaust_pct': 5.0,             # RRP 枯竭：占峰值百分比
    'rrp_exhaust_abs': 0.1,             # RRP 枯竭：绝对值 (T)
    'norm_window': 500,                 # fed_liq_proxy 归一化窗口
}

# A 股配色：红涨绿跌
UP_COLOR = '#E8453C'      # 净申购 / 正 Spread → 红
DOWN_COLOR = '#1FB37A'    # 净赎回 / 负 Spread → 绿
ALERT_COLOR = '#E8453C'   # 报警红
NORMAL_COLOR = '#1FB37A'  # 正常绿

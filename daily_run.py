# -*- coding: utf-8 -*-
"""
三合一监测系统 · 每日全流程一键执行

fetch_exchange.py（交易所官方 ETF 份额/净值，T+0，替代 westock 的滞后份额）
  → fetch_data.py（沪深300 + 创业板 8 只 ETF / 2 个指数；交易所值优先，缺失回退 westock）
  → fetch_ratios.py（三大风格/股债比价）
  → fetch_fred_lsi.py（FRED 20 序列 + LSI + 20 项报警）
  → analyze_report.py（双宽基诊断）
  → fetch_signals.py（市场环境四件套：估值/境内资金面/折溢价/市场宽度）
  → render.py（高清监测图 PNG）
  → make_dashboard.py（三合一交互 HTML 看板）
  → make_llm_summary.py（从看板 HTML 内嵌 const D 生成 llms.txt / data.json，给 AI 读）
  → send_mail.py（三合一汇总日报邮件）

fetch_ratios / fetch_fred_lsi / fetch_signals 为增强模块：失败仅降级，不阻断主报告。
make_llm_summary.py 只读本地看板 HTML、不联网，同样登记为降级不阻断；
排在 make_dashboard.py 之后，因为要读它刚生成的 etf_lsi_dashboard.html。
"""
import subprocess, sys, os, json

BASE = os.path.dirname(os.path.abspath(__file__))
if BASE not in sys.path:
    sys.path.insert(0, BASE)

PY = sys.executable

# (脚本, 失败是否阻断)
# fetch_exchange 失败不阻断：fetch_data 会自动回退 westock，退化为改造前的行为
STEPS = [
    ('fetch_exchange.py', False),
    ('fetch_data.py', True),
    ('fetch_ratios.py', False),
    ('fetch_fred_lsi.py', False),
    ('analyze_report.py', True),
    # 市场环境四件套：四个端点各自独立容错，全挂也只是四块面板不出现
    ('fetch_signals.py', False),
    ('render.py', True),
    ('make_dashboard.py', True),
    # 给 AI 读的文档：纯本地、不联网、失败只降级；必须排在 make_dashboard.py 之后
    ('make_llm_summary.py', False),
]

DEGRADED = []


def run_step(script, fatal):
    print('=' * 28, script, '=' * 28, flush=True)
    r = subprocess.run([PY, os.path.join(BASE, script)], cwd=BASE)
    if r.returncode != 0:
        if fatal:
            print('!! %s 失败，流程终止' % script)
            sys.exit(r.returncode)
        DEGRADED.append(script)
        print('!! %s 失败（%d）—— 降级继续，报告中相应区块将自动隐藏' % (script, r.returncode))
    return r.returncode == 0


def main():
    for script, fatal in STEPS:
        run_step(script, fatal)

    mail_script = os.path.join(BASE, 'send_mail.py')
    if not os.path.exists(mail_script):
        print('未找到 send_mail.py，跳过邮件')
        return
    cfg_path = os.path.join(BASE, 'email_config.json')
    cfg = {}
    if os.path.exists(cfg_path):
        try:
            cfg = json.load(open(cfg_path, encoding='utf-8'))
        except Exception:
            cfg = {}
    env_ok = bool(os.environ.get('ETF_SMTP_USER') and os.environ.get('ETF_SMTP_PASS') and os.environ.get('ETF_MAIL_TO'))
    cfg_ok = bool(cfg.get('sender') and cfg.get('auth_code') and cfg.get('receivers'))
    if env_ok or cfg_ok:
        print('=' * 28, 'send_mail.py', '=' * 28, flush=True)
        r = subprocess.run([PY, mail_script], cwd=BASE)
        if r.returncode != 0:
            print('!! send_mail.py 邮件发送失败，流程终止')
            sys.exit(r.returncode)
    else:
        print('未配置邮箱（email_config.json 或 ETF_SMTP_* 环境变量），跳过邮件发送')

    if DEGRADED:
        print('完成（降级模块：%s）' % '、'.join(DEGRADED))
    else:
        print('全部完成。产物：%s / %s' % (
            os.path.join(BASE, 'etf_lsi_monitor_latest.png'),
            os.path.join(BASE, 'etf_lsi_dashboard.html')))


if __name__ == '__main__':
    main()

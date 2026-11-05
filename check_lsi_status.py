# -*- coding: utf-8 -*-
"""数据完整性把关：读 lsi_status.json（由 fetch_fred_lsi.py 每轮写出），决定这一轮要不要标红。

单独做成一个脚本而不是塞进 workflow 的 run 里，理由：
  · 可以本地 `python check_lsi_status.py` 直接验证；
  · workflow 里 YAML 块标量 + heredoc 的缩进很容易踩坑。

退出码约定：
  0  数据完整（可能有 CSV 兜底，但每个序列都拿到了数）
  1  有序列两个通道都失败，或 LSI 模块整体没跑起来 -> 整轮标红

放在 workflow 的最后一步：前面「发布看板 / 上传 artifacts」照常执行，
这样当天仍能拿到（降级的）看板，只是这一轮会显示红色 ❌ 并带注解，
而不是像以前那样一路绿灯、没人发现 GLI / RRP / DXY 已经整条变 null。
"""
import datetime
import json
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
STATUS = os.path.join(BASE, 'lsi_status.json')
LSI = os.path.join(BASE, 'lsi.json')


def annot(level, msg):
    """GitHub Actions 注解；本地运行时只打印普通文本"""
    if os.environ.get('GITHUB_ACTIONS') == 'true':
        print('::%s::%s' % (level, msg), flush=True)
    else:
        print('[%s] %s' % (level.upper(), msg), flush=True)


def main():
    if not os.path.exists(STATUS):
        annot('error', 'LSI 模块未产出 lsi_status.json —— 说明 fetch_fred_lsi.py 整体崩溃，'
                       '本轮没有宏观数据（看板相关区块会隐藏），请看上一步日志')
        return 1

    st = json.load(open(STATUS, encoding='utf-8'))
    csv_ids = st.get('csv_fallback') or []
    empty = st.get('empty') or []

    print('FRED 序列 %d/%d 拿到数据（API %d / CSV 兜底 %d / 空 %d）  @%s'
          % (st.get('ok', 0), st.get('total', 0), st.get('api_ok', 0),
             len(csv_ids), len(empty), st.get('checked_at', '?')))

    if csv_ids:
        annot('warning', 'FRED JSON 接口本轮失败、已由 fredgraph.csv 兜底（%d 个）：%s'
              % (len(csv_ids), '、'.join(csv_ids)))

    bad = 0
    if empty:
        annot('error', '本轮有 %d 个序列两个通道都没拿到数据，相关指标会是 null：%s'
              % (len(empty), '、'.join(empty)))
        bad = 1

    # 兜底防回归：日历/asof 不允许出现未来日期（历史上 IORB 的未来预填把它顶到过明天）
    if os.path.exists(LSI):
        try:
            asof = json.load(open(LSI, encoding='utf-8')).get('asof')
            today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
            if asof and asof > today:
                annot('error', 'lsi.asof=%s 晚于今天(%s) —— build_calendar 的未来日期过滤失效了'
                      % (asof, today))
                bad = 1
            else:
                print('数据基准日 asof = %s（今天 %s）' % (asof, today))
        except Exception as e:
            # README 12.1：本脚本是「数据完整性闸门」，兜底异常必须非 0 退出
            annot('error', '读取 lsi.json 失败：%s' % e)
            bad = 1

    if bad:
        print('!! 本轮宏观数据不完整，已标记失败（看板仍按现有数据发布）', flush=True)
    else:
        print('数据完整性检查通过', flush=True)
    return bad


if __name__ == '__main__':
    sys.exit(main())

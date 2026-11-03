# 三合一全能监测系统：沪深300 ETF + 创业板 ETF + 宏观 LSI 流动性压力指数

一个仓库、一次流水线、一封邮件，同时完成 **A股双宽基 ETF 持仓背离监测** 与 **美联储宏观流动性压力指数（LSI）20 项报警**。

- 🌐 云端：GitHub Actions 每工作日自动跑一次，出图 + 出交互看板 + 发汇总日报邮件到邮箱
- 💻 本地：`python daily_run.py` 一条命令跑完全流程
- 🧩 三个模块解耦，任一模块取数失败只降级隐藏对应区块，不会拖垮整份报告

---

## 📱 手机端访问地址（添加到主屏幕）

| 线路 | 地址 | 说明 |
| :--- | :--- | :--- |
| **主地址** | **https://etf-lsi.pages.dev/** | Cloudflare 全球节点，国内多数网络可直连 |
| **备用地址** | **https://wj624.github.io/etf-lsi/** | GitHub Pages 原生托管 |

> 两个地址是**同一份看板**，每天流水线跑完会同时更新，内容完全一致。
> 国内打不开 `github.io` 时请用主地址；图标与添加到主屏幕后的体验也完全一样。

手机微信 / Safari / Chrome 直接打开上面任一网址，然后：

| 系统 | 操作 |
| :--- | :--- |
| **iPhone（Safari）** | 底部「分享」按钮 → 下滑找到 **「添加到主屏幕」** → 右上角「添加」 |
| **Android（Chrome）** | 右上角 ⋮ → **「添加到主屏幕 / 安装应用」** |
| **微信内置浏览器** | 右上角 ⋯ → **「在浏览器中打开」**，再按上面步骤操作（微信内无法直接添加） |

添加成功后，手机桌面会多出一个**剪刀差图标**（橙线向上、紫线向下），名字叫 **「ETF监测」**。
点开是一个**独立全屏网页**（没有浏览器地址栏），直接上下滑动看图，和 App 体验一致。

### 它是怎么工作的

```
每天北京时间 21:17
   GitHub Actions 跑流水线 → 生成看板 HTML
        ↓ 自动推送
    本仓库的 `gh-pages` 分支（GitHub Pages 自动发布，不含任何密钥）
        ↓ 同一次运行里并行发布到两个地方（同一份产物）
   ├── https://wj624.github.io/etf-lsi/     GitHub Pages 原生托管
   └── https://etf-lsi.pages.dev/           Cloudflare Pages（国内更稳）
```

**⚠️ 关于「每次打开是重新跑，还是读缓存」——答案是：读快照，不重新跑。**

- 打开网址**不会触发任何计算、不联网取数**，直接加载最近一次流水线生成好的 HTML，秒开。
- 网页里所有数据（曲线、LSI 数值、20 项报警）都是**生成时烤死在 HTML 里的**，因此**断网也能看**。
- 内容只在**每天 19:00 定时任务跑完后**更新一次。也就是说白天打开看到的是**前一晚 19:00 的快照**，不是实时行情。
- 想立刻刷新：去 `wj624/etf-lsi-monitor` → Actions → **Run workflow**，跑完约 1 分钟后网址即更新。

代码库 `wj624/etf-lsi-monitor` 保持**私有**，公开仓库里**只有生成的网页文件**，不含任何源码、邮箱凭证或 API Key。
若哪天不再需要网址，在仓库 Settings → Pages 关掉发布即可，代码仓库不受影响。

---

## 目录

- [一、这个系统在监测什么](#一这个系统在监测什么)
- [二、模块一 & 模块二：双宽基 ETF 持仓背离](#二模块一--模块二双宽基-etf-持仓背离)
- [三、模块三：宏观 LSI 压力指数与 20 项报警](#三模块三宏观-lsi-压力指数与-20-项报警)
- [四、数据源、单位换算与剔除项](#四数据源单位换算与剔除项)
- [五、流水线与产物](#五流水线与产物)
- [六、GitHub Actions 部署（从零到收到第一封邮件）](#六github-actions-部署从零到收到第一封邮件)
- [七、本地运行](#七本地运行)
- [八、环境变量](#八环境变量)
- [九、防 Bug 铁律（改动代码前必读）](#九防-bug-铁律改动代码前必读)
- [十、常见问题 FAQ](#十常见问题-faq)
- [十一、已知限制与免责声明](#十一已知限制与免责声明)

---

## 一、这个系统在监测什么

| 模块 | 监测标的 | 核心问题 |
| :--- | :--- | :--- |
| **① 沪深300** | 华泰柏瑞 `510300`、易方达 `510310`、华夏 `510330`、嘉实 `159919` 对 **沪深300** `sh000300` | 大盘蓝筹的「真金白银」有没有跟上指数涨跌 |
| **② 创业板** | 易方达 `159915`、华安创业板50 `159949`、华夏 `159957`、南方 `159948` 对 **创业板指** `sz399006`，外加三大风格/股债比价 | 成长主力的资金是进是退；红利 vs 成长、债 vs 股谁更便宜 |
| **③ 宏观 LSI** | 美联储 FRED 官方 20 个宏观序列 | 美元体系内部管道紧不紧、美联储净流动性水位高不高、有没有触发 20 项危机报警 |

**为什么把三者放在一起看**：A股的增量资金很大程度来自 ETF 申赎（含国家队与机构配置盘），而外资与全球风险偏好又受美元流动性支配。
「**国内资金是否撤离**」（模块一、二）与「**美元水位是否在退潮**」（模块三）是同一枚硬币的两面。

---

## 二、模块一 & 模块二：双宽基 ETF 持仓背离

### 2.1 指标怎么算（6 步）

```
1) 单只 ETF 当日市值 = 基金份额 × 累计单位净值        (口径1，优先)
                     = 接口返回的 size               (口径2，兜底)
2) 头部 ETF 合计市值  = 四只求和
3) 持仓占比 hold(%)   = 合计市值 ÷ 对应指数流通市值 × 100
4) 归一化分位          = (值 − 区间最小) ÷ (区间最大 − 区间最小) × 100
   窗口 = 滚动 250 个交易日（每个点各自取它之前 250 日的极值，不是整段 5 年一起算）
   hold_pct = 持仓占比分位（橙线）
   idx_pct  = 指数收盘价分位（紫线）
   ※ 为什么不让 5 年整段一起归一化：极值一旦落在远端，近端曲线就被压成一条水平线，
     ±25 的劈叉阈值也就失效了。滚动窗口下「最后一点」和原来 250 天口径完全一致，
     今日读数不变，历史各点也各自可比。
5) 开口差 Spread      = hold_pct − idx_pct          取值 −100 ~ +100
6) 近 20 日线性回归斜率（分位/日）用于顶/底背离判定
```

### 2.2 五档状态（带优先级，自上而下命中即返回）

| 优先级 | 状态 | 判定条件 | 含义 |
| :---: | :--- | :--- | :--- |
| 1 | 🚨 负向大劈叉（主力已撤/指数虚高） | `Spread ≤ −25` | 紫线高高在上、橙线大幅下台阶，持仓与指数严重背离 |
| 2 | ⚡ 正向大劈叉（指数超跌脱离持仓区） | `Spread ≥ +25` | 橙线锁仓高位、紫线深度回调，裂开大喇叭口 |
| 3 | ⚠️ 疑似暗中减持（顶背离） | `(idx_slope > 0 或 idx_pct > 65)` 且 `(hold_slope < 0 或 显著净赎回)` | 指数向上而持仓撤退 |
| 4 | 🛡️ 疑似护盘吸筹（底背离） | `idx_ret20 < 0` 且 `hold_ret20 > 0` 且 `显著净申购` | 指数下跌而资金逆势加仓 |
| 5 | ✅ 同步运行（差值正常） | 其余 | 未触发背离 |

> **显著净赎回**的数学定义：`net5 < 0` 或 `(net1 < 0 且 |net1| > 0.5 × |net5|)`
> **显著净申购**：`net5 > 0`
> 其中 `net5` / `net1` 为四只 ETF 近 5 个 / 1 个交易日的份额净变化（亿份）。

### 2.3 三大风格 / 股债比价（模块二）

分子统一为「防御性资产」，故**比值上行 = 防御占优**，三条线可直接横向对比：

| key | 公式 | 分位高（红区）含义 |
| :--- | :--- | :--- |
| `style_cyb` | 中证红利低波 `000922` ÷ 创业板指 `399006` | 红利已大幅跑赢创业板，**创业板性价比更高** |
| `style_star` | 中证红利 `000922` ÷ 科创50 `000688` | 红利已大幅跑赢科创板，**科创50 性价比更高** |
| `bond` | 十年国债ETF `511260` ÷ 沪深300ETF `510300` | 债券已大幅跑赢股票，**股票性价比更高** |

用**周K**而非日K：行情接口单次最多返回约 1210 根日K（≈5年），脚本按 **4 年一段分段抓取再拼接**（每段约 208 周，低于 260 上限）。
已实测分段重叠处数值 100% 一致，且接口返回即前复权价，拼接安全、无分红除息假跳空。百分位基于各标的**上市以来全周期**全样本。

---

## 三、模块三：宏观 LSI 压力指数与 20 项报警

由 TradingView Pine Script v6《AA流动性压力指数（宏观分析）》完整移植，数据源换成美联储 **FRED 官方 API**，阈值**严格照搬**原代码。

### 3.1 三个核心量

```
LSI (bps) = (SOFR − RRP利率) + (EFFR − IORB)        美元体系内部管道压力
GLI (T)   = WALCL − WTREGEN − RRPONTSYD             美联储净流动性总量
冲量       = GLI 的 20 日变化率 的 20 日变化          二阶加速度
```

- **LSI ≥ 20 bp 偏紧、≥ 50 bp 极端紧张、< 0 内部宽松**
- **GLI 低于近 250 日 25% 分位 = 总量收缩（QT）**，高于 75% 分位 = 总量宽松（QE）
- **RRP 缓冲垫**：`rrp_pct = RRP / Highest(RRP,500) × 100%`，`< 5%` 或 `< 0.1T` 即枯竭

### 3.2 20 项背景颜色报警明细表

看板与邮件中均生成 8 列结构化表格：
`序号 | 分类 | 报警项目名称 | 原始数据明细 | 计算公式 | 当前计算结果 | 代码报警阈值 | 当前是否报警`

| # | 分类 | 报警项 | 阈值（严格按原脚本） |
| :---: | :--- | :--- | :--- |
| 1 | 内部压力 | LSI 极端紧张 `is_extreme_tight` | LSI ≥ 50.0 bps |
| 2 | 内部压力 | LSI 偏紧 `is_tight` | 20.0 ≤ LSI < 50.0 bps |
| 3 | 内部压力 | 核心流动性断裂 `is_liquidity_break` | LSI > 20.0 bps **且** RRP 枯竭 |
| 4 | 缓冲垫 | RRP 逆回购枯竭 `is_rrp_exhausted` | rrp_pct < 5.0% **或** RRP < 0.100 T |
| 5 | 缓冲垫 | 商业银行准备金不足 `is_reserve_insufficient` | 准备金/GDP < 11.0% **且** 准备金/银行总资产 < 11.0% |
| 6 | 动量预警 | ⚠️ 曲线牛陡：衰退前兆 `is_bull_steepener` | sp_chg > +10.0 bps **且** us02y_chg ≤ −20.0 bps |
| 7 | 动量预警 | ⚠️ 曲线熊陡：长端杀估值 `is_bear_steepener` | sp_chg > +10.0 bps **且** us10y_chg ≥ +20.0 bps |
| 8 | 动量预警 | ⚠️ 信用利差短期急升 `is_credit_spiking` | credit_roc > +10.0%（10 日） |
| 9 | 信用与利率 | 高收益债信用利差过宽 | credit_spread > 400.0 bps |
| 10 | 信用与利率 | 实际利率显著紧缩 `is_real_tight` | DFII10 > 2.20% |
| 11 | 信用与利率 | 通胀预期 vs 现实偏差过大 | \|T10YIE − CPI_YoY\| > 0.90% |
| 12 | 信用与利率 | 滞胀 + 信用压力双杀 `is_stagflation_risk` | DFII10 > 1.80% **且** 利差 > 4.00% |
| 13 | 信用与利率 | 潜在危机判定 `crisis_signal` | \|EFFR−T10YIE\| < 50 bps **且** \|US02Y−T10YIE\| < 50 bps **且** 利差 > 400 bps |
| 14 | 总量与动量 | GLI 总量收缩（QT低水位）`is_gli_tight` | GLI < 250 日 25% 分位 |
| 15 | 总量与动量 | 全球流动性周期环比骤减 `is_sudden_drain` | total_liq_change < −1.00% |
| 16 | 总量与动量 | 流动性冲量边际衰竭 `is_impulse_waning` | impulse 连续 3 个观测日回落 |
| 17 | 周期与汇率 | 强美元潮汐发作 `is_dxy_strong` | DTWEXBGS > MA50 |
| 18 | 周期与汇率 | 黄金到顶预警 | gold_top_diff < −350 bps **或** `is_gold_top_macro` |
| 19 | 顶级宏观状态 | ⭐ 流动性黑洞 `state_blackhole` | 断裂 + 利差 > 400 bps + 强美元 |
| 20 | 顶级宏观状态 | ⭐ 滞胀式危机 `state_stagflation` | 滞胀双杀 + T10YIE > 2.50% |

**报警红 / 正常绿强制规范**：
- 触发（`Alert == True`）→ 结果与状态文字为**醒目红色 `#E8453C` 加粗**，显示 `🚨 报警（已触发）`
- 未触发 → **绿色 `#1FB37A`**，显示 `✅ 正常（未触发）`

**正面宽松指示项（5 项，表格底部，保持绿色）**：`is_normal_loose`（LSI < 0）、`is_gli_loose`（GLI > 75% 分位）、
`is_extreme_loose`（LSI < −30 且 GLI 宽松）、`is_real_ext_loose`（DFII10 < 0）、`state_supernova`（⭐流动性泛滥）。

### 3.3 四维全景合成诊断

移植原脚本的 V61 合成引擎，按四层输出成段文字（已剔除依赖私有数据的分支）：

1. **🔍 资金动态** — V57 资金流向雷达：TGA / 外国官方逆回购 / 国内逆回购 三个渠道近 10 个观测日的抽水与放水（Billion 美元），并给出三渠道净流量
2. **【一阶】宏观周期与债务周期** — 主象限定性 + 实际利率 / 通胀偏差 / 强美元 / 贵金属周期叠加
3. **【二阶】流动性矩阵与底层水位** — GLI 总量 + LSI 管道 + RRP 缓冲垫 + 准备金红线 + 冲量加速度
4. **【三阶】微观定价与风险溢价** — 收益率曲线牛陡/熊陡 + 信用利差高度与动量

---

## 四、数据源、单位换算与剔除项

### 4.1 FRED 序列与单位换算表（防 1000 倍误差必读）

| # | 指标 | FRED `series_id` | FRED 原始单位 | 换算为脚本口径 |
| :---: | :--- | :--- | :--- | :--- |
| 1 | 担保隔夜融资利率 | `SOFR` | 百分比 `%` | × 100 → bps |
| 2 | 隔夜逆回购奖励利率 | `RRPONTSYAWARD` | 百分比 `%` | × 100 → bps |
| 3 | 有效联邦基金利率 | `EFFR` | 百分比 `%` | × 100 → bps |
| 4 | 准备金余额利率 | `IORB` | 百分比 `%` | × 100 → bps |
| 5 | 2 年期美债收益率 | `DGS2` | 百分比 `%` | × 100 → bps |
| 6 | 10 年期美债收益率 | `DGS10` | 百分比 `%` | × 100 → bps |
| 7 | 10 年期盈亏平衡通胀预期 | `T10YIE` | 百分比 `%` | × 100 → bps |
| 8 | 10 年期实际利率 (TIPS) | `DFII10` | 百分比 `%` | × 100 → bps |
| 9 | 高收益债信用利差 (OAS) | `BAMLH0A0HYM2` | 百分比 `%` | × 100 → bps |
| 10 | 美国 CPI | `CPIAUCSL` | 月度指数 | 12 个月同比 → % → × 100 → bps |
| 11 | 美联储总资产 | `WALCL` | 百万美元 | ÷ 1e6 → 万亿 (T) |
| 12 | 财政部一般账户 | `WTREGEN` | 百万美元 | ÷ 1e6 → T |
| 13 | 财政部一般账户（周） | `WDTGAL` | 百万美元 | ÷ 1e3 → 十亿 (B) |
| 14 | 隔夜逆回购余额 | `RRPONTSYD` | **十亿美元** | ÷ 1e3 → T；本身即 B |
| 15 | 外国官方逆回购池 | `WLRRAL` | 百万美元 | ÷ 1e3 → B |
| 16 | 银行准备金余额 | `WRESBAL` / `WRBWFRBL` | 百万美元 | ÷ 1e6 → T；÷ 1e3 → B |
| 17 | 商业银行总资产 | `TLAACBM027SBOG` | 十亿美元 | 直接用 B 参与占比 |
| 18 | 名义 GDP | `GDP` | 十亿美元 | 直接用 B 参与占比 |
| 19 | 贸易加权广义美元指数（替代 DXY） | `DTWEXBGS` | 指数点位 | 算 SMA50 判强美元 |
| 20 | 准备金（备用口径） | `WRESBAL` | 百万美元 | ÷ 1e6 → T |

**混合频率处理**：FRED 序列有日频（SOFR/EFFR/DGS…）、周频（WALCL/WDTGAL/WLRRAL/WRBWFRBL/DTWEXBGS）、月频（CPI/银行总资产）、季频（GDP）。
脚本以**日频序列观测日期的并集**构造交易日历（默认取最近 820 个观测日），其余序列按日期**前向填充**，等价于 Pine Script 的 `gaps=barmerge.gaps_off`。

**为什么 `IORB` 不参与构造日历**：`IORB` 是政策利率，FRED 会对**未来日期**预填同一个值
（实测 2026-11-01 周日就能拿到 2026-11-02 的 3.90），并且序列里含周末行。
把它并进「日频序列并集」，等于把周末和「明天」塞进交易日历，`lsi.asof` 会被顶到未来
（线上曾出现 A 股口径 `asof=2026-10-30`、宏观口径 `asof=2026-11-02` 打架）。
它在 `_CAL_EXCLUDE` 里被排除，**数值照常参与 LSI 计算**（`LSI = (SOFR − RRP) + (EFFR − IORB)`），
只是不再定义「日历有哪些天」；`build_calendar()` 另有兜底，裁掉任何晚于今天(UTC)的日期。

### 4.2 明确剔除、不参加计算的 TradingView 私有数据项

1. **`INDEX:S5TH`**（标普500 高于 200 日均线的股票占比）—— 剔除 4 项广度报警
2. **`TVC:GOLD` / `TVC:SILVER`**（金银比）—— 剔除 `is_gs_low`、`is_gs_high` 与 `state_gold_regime`
3. **`ECONOMICS:EUCBBS` / `CNCBBS` / `JPCBBS`**（欧/中/日央行资产负债表）—— 剔除三国央行及汇率换算，
   GLI 改用**美联储净流动性**口径：`GLI(T) = WALCL(T) − WTREGEN(T) − RRPONTSYD(T)`

### 4.3 取数容错：JSON 接口挂了会自动改走 CSV

同一个 FRED 序列有两个入口：

| 通道 | 地址 | 需要 key | 特点 |
| :--- | :--- | :---: | :--- |
| 官方 JSON API | `api.stlouisfed.org/fred/series/observations` | 需要 | 支持 `observation_start` 裁剪，但**会随机 HTTP 500** |
| 图表后端 CSV | `fred.stlouisfed.org/graph/fredgraph.csv?id=<序列号>` | 不需要 | 不限频、实测稳定，但只能拿全量历史 |

**为什么必须两条腿走路**：`api.stlouisfed.org` 在 GitHub Actions 的共享出口 IP 下会偶发 500，
而且既不是「每次都挂」也不是「月初/月末才挂」——实测同一分钟内 20 个序列有 3 个 500、换一分钟全部正常，
**每轮失败的序列都不一样**，本机用 6 线程连打两轮则 20/20 全过。
原实现 `retry=3`（退避 1.5 / 3 / 4.5 秒）连续 3 次没命中就放弃，整条序列变成空字典，
后果是**整条曲线变 null，而不是只缺当天一个点**：

```
日志：GLI = None T｜RRP = None T
看板 JSON：{"gli": null, "rrp_T": null, "dxy": null}，hist.gli 500 点全 null
```

现在 `common.http_json(url, csv_id=<FRED 序列号>)` 在 JSON 通道重试全失败后会自动调用
`common.fred_csv()` 走 CSV 通道，再把结果包成 `{'observations': [{'date','value'}, ...]}` 原样返回，
**调用方的解析逻辑一行都不用改**。CSV 通道不支持 `observation_start`，会多下载全量历史
（最长 6 千行、几十 KB），解析后按 `FETCH_DAYS` 窗口裁剪，与 API 口径保持一致。

**数据完整性报告**：每轮抓完写一份 `lsi_status.json`（不提交进仓库，随 artifacts 上传）：

```json
{"total": 20, "api_ok": 17, "csv_fallback": ["DTWEXBGS", "RRPONTSYD"],
 "empty": [], "ok": 19, "checked_at": "2026-11-01 10:51 UTC"}
```

workflow 最后一步 `check_lsi_status.py` 读它决定这一轮的结论：

| 情形 | Actions 注解 | 退出码 | 看板 |
| :--- | :--- | :---: | :--- |
| 全部走 API | 无 | 0 | 正常发布 |
| 有序列走了 CSV 兜底 | `::warning::` 黄色 | 0 | 正常发布 |
| 有序列两个通道全失败 | `::error::` 红色 | **1（整轮标红 ❌）** | 仍发布（降级版） |
| `lsi_status.json` 不存在（模块整体崩溃） | `::error::` | **1** | — |
| `lsi.asof` 跑到未来 | `::error::` | **1** | — |

两个关键设计：
- **这一步必须排在「发布看板 / 上传 artifacts」之后**，否则一标红就看不到当天那份降级看板了；
- **`fetch_fred_lsi.py` 里 `lsi.json` 先落盘、最后才 `sys.exit(1)`**，保证有数据就先给看板用。
  `daily_run.py` 里本模块是「失败仅降级不阻断」，所以 ETF 主报告、PNG、邮件都不受影响。

### 4.4 交易所份额（上交所）：三层容错 + 开工探测

上交所份额是**逐日单点请求**（`query.sse.com.cn`，一天一次），也是最容易被限流的环节。

**线上实测（2026-11-01，同一份代码）**：

| 环境 | 结果 |
| :--- | :--- |
| 本机（国内 IP） | **248/248 天成功**，耗时 34s |
| GitHub runner | **10/10 天全失败**，报错 `JSONDecodeError: Expecting value: line 1 column 1` |

同一时刻本机全过、云端全挂，说明**不是数据源挂了，是 runner 的共享出口 IP 被 `query.sse.com.cn` 限流**
（服务端直接回空响应 / HTML 页，不回 JSON，所以既不超时也不报 4xx）。此前 03:40 那轮能跑 250/250，
说明限流是**分时段**的，过一段会自己恢复。

根因还有一层：akshare 的 `fund_etf_scale_sse` 内部用 `http.get` **既没有 timeout、也没有重试**，
一次失败就丢一天。现在按四层降级：

| 层 | 做什么 | 细节 |
| :---: | :--- | :--- |
| 0 | 开工探测 | 先花**一次请求**探最近一个交易日，不可用就直接跳过整段（否则 248 天 × 6 次重试 ≈ 8 分钟白等） |
| 1 | akshare 通道重试 | `tries=3`，退避 2s / 4s，**带 ±50% 抖动**（避免 4 个线程同步重试形成风暴），最后一次不再空等 |
| 2 | 失败项串行补抓 | 第 1 轮并发 4 线程跑完，把失败的日期**单线程串行**再跑一遍，间隔 1.5s。并发失败大概率是被限流，降并发才救得回来 |
| 3 | 直连兜底 | 若 akshare 连 3 次都挂，改直连 `query.sse.com.cn/commonQuery.do`（**同一个接口**），自带 `timeout=25s` + 重试 |

外加**熔断器**：两条通道都失败才记一笔，连续 12 天即判定「接口整段不可用」，剩余日期直接跳过。

> **绝不做的兜底**：不用「前一交易日的份额」冒充当天。份额每天在变，顶上去就是假数据。
> 取不到时的真实行为是：
> **沿用 `_exchange_shares.json` 里已有的份额**（这份缓存随仓库提交，250 天都在），
> 只有「连缓存都没有」的日期才由上层 `fetch_data.py` 回退 westock（腾讯）旧值、并自带滞后标记。
> 所以一次限流通常**只影响「最新一天是否刷新」，不会造成数据空洞**。

**直连与 akshare 的一致性已验证**：`510300` 两者都是 `38,866,987,700` 份
（上交所原始字段 `TOT_VOL` 单位是**万份**，必须 × 10000）。

**失败可见**：Actions 打 `::warning::` 注解，`_exchange_shares.json` 的
`meta.sse_failed_dates` 记录具体哪几天没刷到、`meta.sse_breaker_tripped` 记录是否熔断。
缺口不是永久的 —— 下一轮 `pick_todo()` 会把「窗口内缺失的日期 + 尾部 10 天」全部重抓。

---

## 五、流水线与产物

```
daily_run.py
 ├─ fetch_exchange.py    交易所官方 ETF 份额/净值（T+0）          → _exchange_shares.json（失败降级）
 ├─ fetch_data.py        沪深300 + 创业板：2 个指数 + 8 只 ETF  → raw_data.json
 ├─ fetch_ratios.py      三大风格/股债比价（周K全周期）        → ratios.json      （失败降级）
 ├─ fetch_fred_lsi.py    FRED 20 序列 + LSI + 20 项报警         → lsi.json         （失败降级）
 ├─ analyze_report.py    双宽基诊断                             → summary.json / series_<key>.json
 ├─ render.py            高清监测图                             → etf_lsi_monitor_latest.png
 ├─ make_dashboard.py    三合一交互看板                         → etf_lsi_dashboard.html
 └─ send_mail.py         三合一汇总日报邮件                     → mail_preview.html（本地试跑）
```

| 文件 | 说明 |
| :--- | :--- |
| `config.py` | **中央配置**：`TRACKS`（双宽基）、`RATIO_PAIRS`（三比价）、`FRED_SERIES`、`LSI_TH`（全部阈值）、A股配色 |
| `common.py` | 公共工具：node / westock-data 定位、子进程取数、markdown 表格解析、中文字体探测、HTTP JSON（含 `fred_csv` CSV 兜底通道）、分位数、SMA |
| `fetch_exchange.py` | 交易所官方份额/净值（沪市逐日 + 深市区间批量），三层容错 + 熔断，写 `_exchange_shares.json` |
| `fetch_data.py` | 双宽基取数（并发 8 线程） |
| `fetch_ratios.py` | 三大比价取数 |
| `fetch_fred_lsi.py` | FRED 取数 + LSI/GLI/报警/资金流向/四维诊断，并写出 `lsi_status.json` 数据完整性报告 |
| `check_lsi_status.py` | 读 `lsi_status.json` + `lsi.json` 决定本轮退出码（有空序列或 asof 跑到未来就标红） |
| `analyze_report.py` | 双宽基诊断 |
| `render.py` | matplotlib 四行布局 PNG |
| `make_dashboard.py` | 自包含交互 HTML（无外部依赖，离线可看） |
| `send_mail.py` | 汇总邮件（标题含三状态，正文五段，内嵌 PNG） |
| `daily_run.py` | 编排入口 |
| `westock-data/` | 腾讯自选股取数 CLI（Node，零第三方依赖，随仓库携带） |

运行期产物（不提交进仓库）：`raw_data.json`、`ratios.json`、`summary.json`、`lsi.json`、
`lsi_status.json`（数据完整性报告）、`etf_lsi_dashboard.html`、`etf_lsi_monitor_latest.png`。

### 监测图布局

```
行 1  沪深300：持仓占比（左轴，橙）vs 沪深300 收盘（右轴，紫）+ 劈叉区阴影
行 2  创业板：持仓占比（左轴，橙）vs 创业板指收盘（右轴，紫）+ 劈叉区阴影
行 3  LSI 压力指数（左轴，橙，含 ±20/50/−30 阈值线）vs GLI 净流动性（右轴，蓝）
行 4  三大比价全周期百分位横条（绿区 0~20 / 红区 80~100）
```

### 邮件标题

```
[A股双宽基主力 & 宏观LSI日报] YYYY-MM-DD | 沪深300: <状态> | 创业板: <状态> | 宏观: <状态> (LSI: XX.X BP)
```

---

## 六、GitHub Actions 部署（从零到收到第一封邮件）

### 1. 建仓库并推送

```bash
git init && git add -A && git commit -m "init: 三合一监测系统"
git remote add origin https://github.com/<你的用户名>/etf-lsi.git
git push -u origin main
```

### 2. 配置密钥（Actions Secrets，必填 4 项）

| Secret | 值 |
| :--- | :--- |
| `ETF_SMTP_USER` | 发件 QQ 邮箱，如 `123456@qq.com` |
| `ETF_SMTP_PASS` | QQ 邮箱 **SMTP 授权码**（16 位，不是登录密码。QQ邮箱 → 设置 → 账户 → 开启 SMTP → 生成授权码） |
| `ETF_MAIL_TO` | 收件邮箱（可与发件相同）。**想同时发到多个邮箱就用英文逗号分隔**：`123456@qq.com,yourname@gmail.com` |

> **想让 Gmail 也收到？** 只用上面第 3 行就够了——把 Gmail 地址加进 `ETF_MAIL_TO`（逗号分隔），
> QQ 邮箱会把同一封日报同时投递到两个邮箱，无需任何额外配置。

**可选的「第二个发件账号」**（例如用 Gmail 账号再独立发一份作备份通道）：

| Secret | 值 |
| :--- | :--- |
| `ETF_SMTP_USER_2` | Gmail 地址，如 `yourname@gmail.com` |
| `ETF_SMTP_PASS_2` | Gmail **应用专用密码**（16 位，见下方说明） |
| `ETF_MAIL_TO_2` | 第二账号的收件人（留空则与主账号相同） |

> Gmail 需要先在账号里开启两步验证，再到
> https://myaccount.google.com/apppasswords 生成 **App Password**（16 位，形如 `xxxx xxxx xxxx xxxx`，填 Secret 时去掉空格）。
> Gmail 登录密码本身**不能**用于 SMTP。
> 第二账号失败不会让流程变红（主账号那封已送达），只会在日志里打一条告警。

`FRED_API_KEY` **必须自己配置**（本仓库不含任何密钥）：在 Secrets 里加 `FRED_API_KEY`（免费申请：https://fredaccount.stlouisfed.org/apikeys ）。不配置则宏观 / LSI 模块自动降级，看板其余部分正常。

**网页发布（无需任何 Secret）**：看板由工作流自动发布到本仓库的 `gh-pages` 分支，GitHub Pages 直接托管，使用内置 `GITHUB_TOKEN`，**不再需要 `GH_PAT`**。开启方式：仓库 → Settings → Pages → Source 选 `gh-pages` 分支（首次工作流运行后该分支会自动生成）。

#### 密钥配置清单（必填 4 项，本仓库不含任何明文）

仓库 → **Settings → Secrets and variables → Actions → 新建仓库机密**，逐个添加：

| 机密名称（Name） | 取值来源（切勿写进代码 / 提交仓库） |
| :--- | :--- |
| `FRED_API_KEY` | FRED 官网免费申请的 API key：https://fredaccount.stlouisfed.org/apikeys |
| `ETF_SMTP_USER` | 发件邮箱地址（如 `123456@qq.com`） |
| `ETF_SMTP_PASS` | 该邮箱的 **SMTP 授权码**（不是登录密码；QQ 邮箱在 设置 → 账户 → 开启 SMTP 后生成 16 位授权码） |
| `ETF_MAIL_TO`  | 收件邮箱（多个用英文逗号分隔，如 `a@qq.com,b@gmail.com`） |

> **可选（备份通道）**：`ETF_SMTP_USER_2` / `ETF_SMTP_PASS_2` / `ETF_MAIL_TO_2`（第二个发件账号，例如 Gmail 应用专用密码）。
>
> ⚠️ **安全约定**：本仓库代码与 git 历史里**绝不内置任何密钥**。FRED key 与邮箱凭证只存在于 ① 你的 Actions Secrets（GitHub 加密存储）或 ② 本地 `email_config.json`（已被 `.gitignore` 忽略，不会上传）。更换 key 时只需在 Secrets 里改值，**代码无需改动**。

### 3. 触发一次验证

仓库 → **Actions** → 选 `ETF + LSI daily report` → **Run workflow**。
约 10 分钟后若全部为绿色，邮箱应收到日报，手机网址也会同步更新。

### 3.5 手机网页（GitHub Pages）

本仓库现已**公开**，看板直接发布到本仓库的 `gh-pages` 分支（GitHub Pages 原生支持公开仓库），无需第二个仓库：

> 单一公开仓库 `wj624/etf-lsi`：全部源码、配置在 `main` 分支，看板产物（`index.html` / `monitor.png` / 图标 / `manifest.json`）自动发布到 `gh-pages` 分支（GitHub Pages 托管）。原私有仓库 `etf-lsi-monitor` / `etf-lsi-pages` 已合并迁入，确认无误后可删除。

流水线末尾的 **Publish dashboard to GitHub Pages** 步骤会自动把产物推过去，
Pages 从该仓库 `gh-pages` 分支根目录发布，网址见文首「📱 手机端访问地址」。

开启 GitHub Pages 只需一次：Settings → Pages → Source 选 `gh-pages` 分支 / `/(root)`（或用 API
`POST /repos/<owner>/<repo>/pages {"source":{"branch":"gh-pages","path":"/"}}`）。

### 4. 定时规则

```yaml
schedule:
  - cron: "17 13 * * 1-5"    # UTC 13:17 = 北京时间 21:17，周一至周五，每日一次
```

> **为什么定在 21:17 而不是傍晚？**
> 纽约联储每天 **美东时间 08:00** 才公布当日的 SOFR / EFFR / IORB，
> 换算成北京时间是**夏令时 20:00 / 冬令时 21:00**。若在北京时间 19:00 跑，
> 拿到的还是**前一天**的旧利率，等于整份 LSI 报告滞后一天。
> 21:17 在两种时制下都晚于美东 08:00，同时也晚于沪深交易所晚间披露的 ETF 份额，
> 是一天中最稳妥的单次执行点。只跑一次，避免一天收两封邮件。

> ⚠️ **GitHub 定时任务的三个坑**
> 1. cron 用 **UTC**。北京 = UTC+8。
> 2. 仓库 **60 天无任何提交**会导致定时任务被自动停用（UI 上显示灰色）。长期不用请偶尔提交一次。
> 3. 高峰期实际触发可能**延迟数分钟到半小时**，且 GitHub 不保证准时。重要日子建议手动 Run workflow 兜底。

### 4.5 看板图表交互（三张图都能缩放）

看板上有三张手写 SVG 图：沪深300 双轴、创业板双轴、宏观 LSI vs GLI。三张都支持同一套操作：

| 操作 | 效果 |
|---|---|
| **滚轮** | 以鼠标位置为锚点缩放（往里缩 = 放大细节） |
| **按住拖拽** | 左右平移，看更早/更晚的一段 |
| **双击** | 回到最近 250 个交易日 |
| **`1M / 3M / 6M / 1Y / 5Y`** | 一键切换区间，当前区间按钮会高亮 |
| **悬停** | 十字线 + 当日明细（持仓占比、指数、Spread、4 只 ETF 份额与变动） |

实现上只有一条通用控制器 `attachZoom(el, view, N, render)`，三张图共用：

- `view={i0,i1}` 记录当前窗口在整段序列里的下标区间，任何交互只改这两个数；
- 改完调各图自己的 `render()` 重画；
- 重画时**左右两轴都按当前窗口重新定标**（`zRange()`），所以放大到某一段时能看清那一段的形状；
- Spread 副图的纵轴强制包含 `0` 和 `±25`，缩到再窄也不会把阈值线挤出画面；
- 宏观图左轴额外纳入 `+50 / +20 / −30` 三条阈值线，同理。

> 没有引入任何图表库，仍然是手写 SVG（0 依赖、页面 190 KB 左右），所以手机端也不会卡。

### 5. 历史缓存

`raw_data.json`（1250 交易日 ≈ 5 年 × 2 赛道）与 `ratios.json`（周K全周期）通过 `actions/cache` 跨运行滚动复用。
**滚动窗口，不会越长越胖**：`fetch_data.py` 每次写回缓存前会把窗口（`ETF_DAYS`，默认 1250 个交易日）之外的
旧日期直接丢掉，所以 `raw_data.json` 体积恒定在 1.6 MB 左右，不会一年年堆积；
`_exchange_shares.json` 同样只保留最近 `ETF_EXCHANGE_DAYS + TAIL` 天（约 260 天），恒定在 0.6 MB。
**`lsi.json` 故意不缓存**——宏观数据必须每天新算；若缓存，一旦 FRED 抓取失败就会拿前一天的旧文件顶上，
把陈旧数据当成当日结果发出去。不缓存时，宏观模块失败会让看板直接隐藏该区块，这更诚实。
**每次运行仍会强制重抓最后 8 个交易日**（ETF 份额 T+1~T+2 披露，需要回填）。

### 6. 产物

每次运行上传 `etf-lsi-report` 构件，含 PNG / HTML / summary.json / ratios.json / lsi.json，90 天内可下载。

---

## 七、本地运行

**环境**：Python 3.9+（需 `matplotlib`、`numpy`）、Node.js 18+（给 westock-data 用）、能访问外网。

```bash
pip install -r requirements.txt

# 一键跑全流程
python daily_run.py

# 或分步跑
python fetch_data.py          # 首次较慢（约 1250 交易日 × 2 赛道，20~40 分钟），之后走缓存
python fetch_ratios.py
python fetch_fred_lsi.py
python analyze_report.py
python render.py
python make_dashboard.py
python send_mail.py
```

**只预览邮件不真发**：`ETF_DRY_RUN=1 python send_mail.py`（只生成 `mail_preview.html`）。
**不发邮件**：不配 `email_config.json` 也不设 `ETF_SMTP_*` 环境变量即可，脚本会自动跳过。

### node / westock-data 的定位顺序

1. 环境变量 `NODE_BIN`
2. 随包 `runtime/node/node.exe`
3. 系统 PATH 中的 `node`
4. 找不到就抛错

`westock-data` 技能目录依次查找：仓库根 `westock-data/` → 上级目录 → WorkBuddy 内置技能目录。

---

## 八、环境变量

| 变量 | 默认 | 说明 |
| :--- | :--- | :--- |
| `ETF_SMTP_USER` | — | 发件邮箱 |
| `ETF_SMTP_PASS` | — | SMTP 授权码 |
| `ETF_MAIL_TO` | — | 收件邮箱（多个用**英文逗号**分隔，如 `a@qq.com,b@gmail.com`） |
| `ETF_SMTP_HOST` | `smtp.qq.com` | SMTP 服务器 |
| `ETF_SMTP_PORT` | `465` | 465=SSL，587=STARTTLS |
| `ETF_SMTP_USER_2` | — | 【可选】第二个发件账号（如 Gmail） |
| `ETF_SMTP_PASS_2` | — | 【可选】第二个账号的密码 / 应用专用密码 |
| `ETF_MAIL_TO_2` | — | 【可选】第二个账号的收件人，留空则与主账号相同 |
| `ETF_SMTP_HOST_2` | `smtp.gmail.com` | 【可选】第二个账号的 SMTP 服务器 |
| `ETF_SMTP_PORT_2` | `587` | 【可选】第二个账号端口（Gmail 用 587） |
| `ETF_DRY_RUN` | — | `1` = 只生成预览不发送 |
| `FRED_API_KEY` | —（必填，去 Secrets 配置） | FRED API key（不配置则宏观模块降级） |
| `ETF_REFRESH_TAIL` | `8` | 每次强制重抓的尾部交易日数（份额披露滞后回填） |
| `ETF_DAYS` | `1250` | 展示窗口交易日数（≈5 年，超出部分写回缓存时裁掉） |
| `ETF_CAL_DAYS` | `2000` | 交易日历回看的自然日数（要够 5 年 + 长假余量） |
| `ETF_KLINE_LIMIT` | `1500` | kline 单次返回行数上限（实测接口最多 1212 行） |
| `ETF_EXCHANGE_DAYS` | `250` | 交易所份额回填窗口（交易日） |
| `ETF_EXCHANGE_TAIL` | `10` | 每轮强制刷新份额的尾部交易日数 |
| `ETF_SSE_WORKERS` | `4` | 上交所第 1 轮并发数（调大更容易被限流，不建议 >6） |
| `ETF_SSE_RETRY` | `3` | 上交所单日重试次数（含直连通道） |
| `ETF_SSE_PASS2_GAP` | `1.5` | 第 2 轮串行补抓的日间隔（秒） |
| `ETF_SSE_BREAKER` | `12` | 连续失败多少天触发熔断（跳完剩余日期） |
| `ETF_MAX_SSE_CALLS` | `320` | 单轮最多抓多少个上交所日期 |
| `ETF_SZSE_CHUNK` | `20` | 深交所区间请求每段天数（单次上限 65535 行） |
| `LSI_FETCH_DAYS` | `2700` | FRED 抓取回看自然日（含 5 年展示 + 约 550 日指标预热） |
| `LSI_CAL_DAYS` | `1300` | 宏观曲线展示的观测日数（≈5 年） |
| `LSI_CAL_DAYS` | `820` | 宏观交易日历长度（观测日） |
| `RATIO_SEG_FROM` | `2010` | 周K分段抓取起始年 |
| `RATIO_PERIOD` | `week` | 比价周期 |
| `RATIO_TAIL` | `260` | 存入 JSON 的尾部周数 |
| `NODE_BIN` | — | 手动指定 node |

---

## 九、防 Bug 铁律（改动代码前必读）

以下 8 条均来自真实踩坑，严禁回退：

1. **份额披露滞后识别 `_is_stale` 不捆绑 `nav`**
   基金公司每晚会先更新单位净值 `nav`，而份额 `shares` 存在 T+1~T+2 滞后。
   判定尾部交易日份额是否未披露时，**只要 4 只 ETF 当日 `shares` 与前一日全部相同，即判定未披露并截断尾部**，严禁同时要求 `nav` 也相同。

2. **单日份额变动 `chg` 强制用相邻交易日真实差值重算**
   `chg[i] = shares[i] − shares[i−1]`，严禁直接信任接口在未披露日重复返回的静态 `sharesChg`。

3. **ETF 市值优先用 `shares × (nav or close)`**
   防止接口返回的 `size` 在份额未更新时连同净值波动一起冻结。

4. **配色统一为 A 股「红涨绿跌」**
   净申购 `+` 与正 Spread `+` → 红 `#E8453C`；净赎回 `−` 与负 Spread `−` → 绿 `#1FB37A`。
   邮件格式化用 `%+.1f`，**严禁再手动拼接 `+`**（会出现 `++12.7`）。

5. **占位符替换顺序**
   `make_dashboard.py` 已改为「全部动态内容由 JS 渲染」，从根本上消除了 `__HOLD__` 被 `__HOLD__2` 之类的子串覆盖问题。若日后改回占位符方案，必须先替换长名再替换短名。

6. **`IORB` 必须留在 `FRED_SERIES` 里，但必须留在 `_CAL_EXCLUDE` 里**
   它是 LSI 的核心项（`LSI = (SOFR − RRP) + (EFFR − IORB)`），删掉就整个公式缺一项；
   同时它是政策利率、FRED 会预填未来日期且含周末行，一旦让它参与构造交易日历，
   `lsi.asof` 就会被顶到明天（真实事故：A 股口径 `asof=2026-10-30`、宏观口径 `asof=2026-11-02`）。
   **两个位置的要求正好相反，改代码时不要只看到一处就动手。**

7. **`http_json` 的 CSV 兜底不能删**
   调用 FRED 时必须写成 `common.http_json(url, csv_id=<序列号>, observation_start=start)`。
   只传 url 就等于放弃了第二条通道——JSON API 偶发 500 且重试 3 次不保证命中，
   失败一次就是整条曲线变 null，而且退出码仍是 0，很容易被当成「今天没数据」放过。

8. **上交所份额的「开工探测 + 两轮 + 熔断」不能简化成一轮高并发**
   实测同一份代码：本机 248/248 全过、GitHub runner 10/10 全挂（报错 `JSONDecodeError: line 1 column 1`），
   说明是 runner 共享出口 IP 被 `query.sse.com.cn` 限流，**重试次数救不了，只能快速认输**。
   因此「开工先探一天」这一步必须保留（把 8 分钟空转压到 1 次请求）；
   第 2 轮**必须是单线程**并拉长间隔（并发重试只会继续撞墙）；
   同时必须保留熔断，否则 248 天会一格一格地烧完重试。
   **更不允许用前一交易日的份额顶替缺失日**——份额每天变化，顶上去就是假数据。

另外两条工程经验：
- **`.bat` 文件在中文 Windows 必须用 GBK 编码保存**，UTF-8 会被 `cmd.exe` 按 GBK 解析出错。
- **Windows 保留设备名**（`nul`、`con`、`aux`）无法用常规方式删除，脚本里不要重定向生成这类文件名。

---

## 十、常见问题 FAQ

**Q1：Actions 显示成功但没收到邮件？**
按顺序排查：① Secrets 里 3 个值是否都配了（`ETF_SMTP_PASS` 是**授权码**不是登录密码）；
② 收件箱没有就去垃圾邮件 / 广告邮件里找；③ 打开运行日志看是否有「未配置邮箱凭证，仅生成本地预览」；
④ QQ 邮箱需已在「设置 → 账户」开启 SMTP 服务；⑤ 若用 587 端口，确认 `ETF_SMTP_PORT` 已同步修改。

**Q1.5：能同时发到 QQ 邮箱和 Gmail 吗？**
能，两种方式：

1. **只是想让 Gmail 也收到（推荐，零额外配置）**：
   把 `ETF_MAIL_TO` 改成英文逗号分隔的两个地址，例如
   `你的QQ号@qq.com,yourname@gmail.com`
   ——QQ 账号会把同一封日报同时投递到这两个邮箱。
2. **想让 Gmail 也作为独立发件方再发一份（双通道备份）**：
   额外配 `ETF_SMTP_USER_2` / `ETF_SMTP_PASS_2`（Gmail **应用专用密码**，不是登录密码）。
   两个账号各发一封，任一个挂了另一封仍能到。第二账号失败不会让 Actions 变红，只在日志里告警。

> ⚠️ 中文 Windows 电脑如果「计算机名」是中文，老版本会在发信时崩在
> `'ascii' codec can't encode characters` （smtplib 发 EHLO 时用了本机名）。
> 已修：现在会自动检测并在非 ASCII 时退回 `localhost`。

**Q2：Spread 一直是大正值/大负值，是不是算错了？**
先确认是不是「份额披露滞后」造成的假象：脚本会自动截断未披露的尾部交易日，并在日志里打印
`[份额披露滞后] xxx 起的 N 个交易日沿用上一次披露值，已截断至 xxx`。
若日志里没有这行而 Spread 仍极端，通常是真实的资金与指数背离。

**Q3：为什么 RRP 一直显示「枯竭」？**
2024 年之后美联储隔夜逆回购余额已降至接近零（当前约 0.0004 T），
按原脚本阈值 `rrp_pct < 5% 或 RRP < 0.1T`，**确实会长期判定为枯竭**。这是真实现象，不是 bug。
真正要看的是它与 LSI 的组合项 —— 只有 `LSI > 20 bps 且 RRP 枯竭` 才构成「核心流动性断裂」。

**Q4：宏观数据和我在 TradingView 上看到的略有差异？**
正常。差异来自：① 数据源不同（FRED 官方 vs TradingView 二次加工，尤其 `DGS2/DGS10` 用 `TVC:US02Y` 还是 `FRED:DGS2` 会差 1 天）；
② 已剔除的私有序列不参与计算；③ GLI 改用美联储净流动性口径（不再加欧/中/日央行）；
④ 单位换算严格按 FRED 官方口径，与原 Pine 脚本对 `RRPONTSYD`、`GDP` 的单位假设不同（原脚本存在 1000 倍量纲问题）。

**Q5：为什么比价用周K不用日K？**
接口单次最多返回约 1210 根日K（≈5年）。用周K分段拼接可覆盖各标的**上市以来全周期**，
使「历史百分位」这个指标真正有意义。已实测分段重叠处数值 100% 一致。

**Q6：首次运行很慢？**
正常。需要抓取约 250 个交易日 × 2 个赛道 ×（1 次指数 + 1 次 ETF 批量）。
之后靠 `raw_data.json` 缓存，每次只增量抓新增日 + 强制重抓尾部 8 天。

**Q7：可以只跑其中一个模块吗？**
可以。三个模块产物互相独立：`fetch_data.py`+`analyze_report.py` 出 A股部分，
`fetch_fred_lsi.py` 单独出宏观部分。`render.py` / `make_dashboard.py` / `send_mail.py`
会自动检测缺失的 JSON 并隐藏对应区块。

**Q8：`fetch_ratios.py` 或 `fetch_fred_lsi.py` 失败了怎么办？**
不会阻断主流程。`daily_run.py` 会打印「降级继续」，报告中相应区块自动隐藏，A股主体照常出报告、照常发邮件。

**Q9：FRED_API_KEY 会不会泄露？**
仓库**不含任何密钥**。请务必在 Secrets 里配置自己的 `FRED_API_KEY`（免费申请：https://fredaccount.stlouisfed.org/apikeys ）。FRED 与 GitHub 的自动扫描器会作废公开仓库里出现的密钥，所以本仓库从设计上就**不内置任何 key**。

**Q10：某天看板里 GLI / RRP / 美元指数整条变 null，是数据没了吗？**
不是数据没了，是那一轮 `api.stlouisfed.org` 偶发 HTTP 500 连续 3 次没命中（见 4.3 节）。
现在已经有两道保险：① JSON 失败自动改走 `fredgraph.csv` 免密钥通道；
② `check_lsi_status.py` 会在两个通道都失败时把整轮标红 ❌ 并打 `::error::` 注解。
如果看到红色，去 run 页面 Annotations 里能看到具体是哪几个序列；
手动验证某个序列到底有没有数据，直接开
`https://fred.stlouisfed.org/graph/fredgraph.csv?id=<序列号>` 就能看到全量历史。

**Q11：`lsi.asof` 显示的是明天（或周末）？**
已修。根因是 `IORB` 会被 FRED 预填到未来日期、且含周末行，之前它参与了交易日历构造。
现在 `IORB` 从日历构造里排除（数值照常参与 LSI 计算），`build_calendar()` 另有「不晚于今天」的兜底裁剪，
`check_lsi_status.py` 还会在 `asof` 晚于今天时直接把整轮标红，防止再次悄悄回归。

---

## 十一、已知限制与免责声明

1. ETF 份额为**基金端 T+1~T+2 披露**，最新 1~2 个交易日可能是沿用值；脚本会识别并截断，但无法凭空补齐未披露数据。
2. 归一化分位基于**滚动 250 个交易日区间**的极值（每个点取自己之前的 250 日），
   所以曲线可以一路画到 5 年；而「今天」这个分位永远只由最近 250 日决定，口径不漂移。
3. 「头部 ETF」只取规模前列的 4 只，未覆盖全部同标的 ETF，占比是**相对量**而非全市场绝对持仓。
4. 宏观 FRED 数据存在**发布滞后与事后修订**（尤其 GDP、CPI），最新值可能后续被修正。
5. `WDTGAL` / `WALCL` 等为**周频**序列，前向填充后日频曲线在周内是平台状，`is_impulse_waning` 等依赖连续变化的指标触发会偏保守（与 Pine 脚本行为一致）。
6. 定时执行依赖 GitHub Actions 的调度，**不保证准时**，也可能因仓库 60 天无提交而被停用。

> **免责声明**：本工具仅用于个人研究与数据可视化，所有指标由公开行情自动计算，
> **不构成任何投资建议**。市场有风险，决策需谨慎。

---

## 附：配色说明

遵循 A 股习惯 **红涨绿跌**：净申购 / 正 Spread / 报警触发 → 红色 `#E8453C`；
净赎回 / 负 Spread / 正常未触发 → 绿色 `#1FB37A`。
（注意这与欧美「绿涨红跌」相反。）

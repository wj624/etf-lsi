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
| **看板中心（聚合入口）** | **https://wj-dashboards.pages.dev/** | 一个页面切四个看板，含本看板 |
| **🤖 发给 AI 的数据文档（llms.txt）** | **https://etf-lsi.pages.dev/llms.txt** | **把这条链接直接粘给大模型**，它就能读到本看板全部指标与结论；备用 https://wj624.github.io/etf-lsi/llms.txt |

> 两个地址是**同一份看板**，每天流水线跑完会同时更新，内容完全一致。
> 国内打不开 `github.io` 时请用主地址；图标与添加到主屏幕后的体验也完全一样。
>
> **给 AI 用（无需上传任何文件）**：复制上表「发给 AI 的数据文档」那条链接发给大模型即可。
> 它是一份**每天随看板自动更新**的纯文本快照，覆盖双宽基 ETF 诊断、宏观 LSI 20 项报警、
> 风格/股债比价、市场环境六件套与跨资产比价；同目录 `data.json` 是机器可读全量数据。
> 两条线路（Cloudflare / GitHub Pages）内容完全一致，国内优先用 `pages.dev`。

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
- 内容只在**每天 21:17 定时任务跑完后**更新一次。也就是说白天打开看到的是**前一晚 21:17 的快照**，不是实时行情。
- 想立刻刷新：去本仓库 `wj624/etf-lsi`（`main`）→ Actions → **Run workflow**，跑完约 1 分钟后网址即更新。

本仓库已公开，源码与配置都在 `main` 分支；`gh-pages` 分支**只有生成的网页文件**，不含任何邮箱凭证或 API Key（密钥只存于 Actions Secrets）。
若哪天不再需要网址，在仓库 Settings → Pages 关掉发布即可。

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
- [十二、给 AI 的维护提示词](#十二给-ai-的维护提示词)
- [十三、跨资产比价卡片（金银比 / 金油比 / 铜金比 / KOSPI-GOLD）](#十三跨资产比价卡片金银比--金油比--铜金比--kospi-gold)

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

### 4.0 数据源总表（先看这张）

本仓库是**两条完全独立的取数链路**，互不影响：宏观走 FRED（境外、需 Key），A 股走自建 Worker。

| 数据 | 来源 | 取数位置 | 需要 Key |
| :--- | :--- | :--- | :---: |
| 宏观 LSI 20+ 项序列 | 美联储 FRED 官方 API | `fetch_fred_lsi.py`（JSON 接口，失败自动降级 CSV） | 需要 `FRED_API_KEY` |
| 沪市 ETF 份额 | 上交所 `query.sse.com.cn` | `fetch_exchange.py` → Worker `/api/etf-shares?exchange=SH`，直连兜底 | 否 |
| 深市 ETF 份额 | 深交所官方 xlsx | `fetch_exchange.py` 内直连 `www.szse.cn/api/report/ShowReport` | 否 |
| ETF 单位净值 | 天天基金 pingzhongdata | `fetch_exchange.py` → Worker `/api/fund-nav`，东财直连兜底 | 否 |
| A 股交易日历 | 上证指数 K 线派生 | `fetch_exchange.py` → Worker `/api/trade-calendar` | 否 |
| ETF 行情 / 份额快照（滞后源） | 腾讯自选股 westock | `westock-data/`（Node CLI，随仓库携带） | 否 |
| 指数估值（PE/PB 分位） | 蛋卷基金 index_eva | `fetch_signals.py` → Worker `/api/index-valuation` | 否 |
| 境内资金面（SHIBOR / DR007） | 中国货币网 | `fetch_signals.py` → Worker `/api/cn-liquidity` | 否 |
| ETF 折溢价 | 腾讯行情（价）+ 东财净值 | `fetch_signals.py` → Worker `/api/etf-premium` | 否 |
| 市场宽度（涨跌家数/涨停跌停/连板） | 东财 push2ex | `fetch_signals.py` → Worker `/api/market-breadth` | 否 |
| 国债收益率曲线（2/5/10/30Y + 期限利差） | 东财 datacenter | `fetch_signals.py` → Worker `/api/cn-rates` | 否 |

> **改造边界（重要）**：2026-11 的迁移**只动了 A 股那半**（`fetch_exchange.py`）。
> `fetch_fred_lsi.py` 与 `common.py`（FRED 部分）**一行未改**，宏观 LSI 链路保持原样。
> 想改宏观部分时，不要顺手去动 Worker 那边；想改 A 股部分时，也不要碰 FRED。

**上游 / 依赖变了怎么办**

- A 股这半只消费 Worker 的 HTTP 契约。Worker 侧怎么同步上游、怎么验证、怎么部署，见
  [`wj624/a-stock-api` 的 README](https://github.com/wj624/a-stock-api/blob/main/README.md)
  —— 里面有一份**可直接复制给 AI 的同步提示词**和 Runbook。只要字段名与单位不变，本仓库无需改动。
- `requirements.txt` 现在只有 4 个依赖：`matplotlib / numpy / requests / openpyxl`。
  **已彻底移除 akshare**（连带 pandas），装依赖时间从分钟级降到秒级。
  若有人想重新引入 akshare，请先读 4.4 节，那里写了它为什么被拿掉。

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

**派生序列 `hist.us2_effr`（2026-11 新增）**：`DGS2 − EFFR`，单位 bp，存进 `lsi.json` 的 `hist`。
它不参与 LSI 计算，只用于看板 ⑤-3 的缺口小图 —— **>0 表示 2 年期高于当前政策利率，市场在定价加息；<0 表示定价降息**。
之所以单独存一条派生序列而不是让前端同时取 `us02y` / `effr` 两条再对齐空值，是因为两条序列的空值位置不一定一致，
前端做逐点减法很容易在某个点位算出 `null` 或错位，而 `compute()` 里两条序列都已前向填充、同一套日历，减法是最可靠的。

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

### 4.4 交易所份额（上交所）：多层容错 + 开工探测

上交所份额是**逐日单点请求**（一天一次），也是最容易被限流的环节。
2026-11 起这一层改成**先打自建 Worker**（`a-stock-api.wj4020410.workers.dev`），
由 Cloudflare 出口去请求 `query.sse.com.cn`，runner 共享出口 IP 被限流的问题因此消失，
详见下方「为什么迁到 Worker」。

**线上实测（2026-11-01，同一份代码）**：

| 环境 | 结果 |
| :--- | :--- |
| 本机（国内 IP） | **248/248 天成功**，耗时 34s |
| GitHub runner | **10/10 天全失败**，报错 `JSONDecodeError: Expecting value: line 1 column 1` |

同一时刻本机全过、云端全挂，说明**不是数据源挂了，是 runner 的共享出口 IP 被 `query.sse.com.cn` 限流**
（服务端直接回空响应 / HTML 页，不回 JSON，所以既不超时也不报 4xx）。此前 03:40 那轮能跑 250/250，
说明限流是**分时段**的，过一段会自己恢复。

根因还有一层：akshare 的 `fund_etf_scale_sse` 内部用 `http.get` **既没有 timeout、也没有重试**，
一次失败就丢一天 —— 这也是本仓库后来彻底去掉 akshare 的原因之一。

**为什么迁到 Worker（2026-11）**：上面的限流是「按出口 IP」的，换 IP 才有解。
Worker 跑在 Cloudflare 上，出口 IP 与 runner 完全无关，且自带 KV 缓存（同一天重复请求不再回源）。
迁移后 250 天回填从「分钟级 + 高失败率」变成「秒级 + 稳定」，顺带砍掉了 akshare→pandas 这串重依赖。

即便如此，下面的多层降级全部保留 —— Worker 也可能挂、Cloudflare 出口也可能被限：

| 层 | 做什么 | 细节 |
| :---: | :--- | :--- |
| 0 | 开工探测 | 先花**一次请求**探最近一个交易日，不可用就直接跳过整段（否则 250 天 × 6 次重试 ≈ 6 分钟白等） |
| 1 | Worker 通道重试 | `tries=3`，退避 1.5s / 3s（`_api_get` 内置）；Worker 会把上游失败包成 200 + `{"error":...}`，这种情况同样按失败重试 |
| 2 | 失败项串行补抓 | 第 1 轮并发 4 线程跑完，把失败的日期**单线程串行**再跑一遍，间隔 1.5s。并发失败大概率是被限流，降并发才救得回来 |
| 3 | 直连兜底 | 若 Worker 连 3 次都挂，改直连 `query.sse.com.cn/commonQuery.do`（**同一个接口**），自带 `timeout=25s` + `tries=3` 退避重试、**带 ±50% 抖动**（避免 4 个线程同步重试形成风暴） |

外加**熔断器**：两条通道都失败才记一笔，连续 12 天即判定「接口整段不可用」，剩余日期直接跳过。

> **绝不做的兜底**：不用「前一交易日的份额」冒充当天。份额每天在变，顶上去就是假数据。
> 取不到时的真实行为是：
> **沿用 `_exchange_shares.json` 里已有的份额**（这份缓存随仓库提交，250 天都在），
> 只有「连缓存都没有」的日期才由上层 `fetch_data.py` 回退 westock（腾讯）旧值、并自带滞后标记。
> 所以一次限流通常**只影响「最新一天是否刷新」，不会造成数据空洞**。

**三条路径的一致性均已验证**：`510300` 在 2026-11-03 于 Worker / 直连 / 迁移前的 akshare 下
都得到 `44,587,387,700` 份（上交所原始字段 `TOT_VOL` 单位是**万份**，必须 × 10000；
代码里统一 `round(..., 2)`，抹掉 `万份 × 1e4` 产生的 `...99.99999` 浮点噪声，
否则 592KB 的份额缓存每天都会出现「值没变但末位抖了」的无意义 diff）。

深市份额走深交所官方 xlsx（`www.szse.cn/api/report/ShowReport`，`CATALOGID=scsj_fund_jjgm`，
`TABKEY=tab1`，`jjlb=ETF`），区间批量取回。列是 `日期 | 基金代码 | 基金简称 | 基金规模(份)`，
**本身已是「份」，不再乘 10000**。该接口 `SHOWTYPE=JSON` 会返回 HTTP 500，只有 xlsx 可用。

**失败可见**：Actions 打 `::warning::` 注解，`_exchange_shares.json` 的
`meta.sse_failed_dates` 记录具体哪几天没刷到、`meta.sse_breaker_tripped` 记录是否熔断。
缺口不是永久的 —— 下一轮 `pick_todo()` 会把「窗口内缺失的日期 + 尾部 10 天」全部重抓。

---

### 4.5 市场环境六件套（估值 / 境内资金面 / 国债曲线 / 折溢价 / 市场宽度 / 跨资产比价）

这六项由 `fetch_signals.py` 抓取，写进 `signals.json`，供看板 ⑨～⑬ 五个面板及跨资产比价卡片使用。
**各端点彼此独立**：任意一个失败，只让对应面板消失，不影响主看板、ETF 背离与宏观 LSI。

| 端点 | 数据源 | 口径要点 | 已知限制 |
| :--- | :--- | :--- | :--- |
| `/api/index-valuation` | 蛋卷基金 | `pe_pct` = 上游 `pe_percentile`，0~1、越大越贵；`pe_over_history` 是它的互补值（1 − pe_pct），**两者互为倒数，只用前者** | 分位基于该指数 2016 年以来的历史 |
| `/api/cn-liquidity` | 中国货币网 | SHIBOR 八期限 + 银行间回购定盘；`FDR001/007/014` 就是 **DR001/DR007/DR014**，单位 % 年化 | 回购定盘**只回最近约 1 个月**且忽略 startDate，而 SHIBOR 能回 60+ 天 —— 看板因此从「首个 DR007 有效点」起画，否则左侧会出现一大段没有 DR007 的空白 |
| `/api/etf-premium` | 腾讯价 + 东财净值 | 折溢价 =（市价 − 净值）/ 净值 × 100 | 用的是**收盘价与当日净值**，不是盘中 IOPV。净值未更新时（`stale=true`）该值只反映相对上一日净值的偏离，看板会用 `*` 标注。面板每行左侧同时显示 **代码 + 基金简称**（取自腾讯行情 `name` 字段），不必再对照底部图例 |
| `/api/market-breadth` | 东财 push2ex | 涨跌家数由「涨跌幅分布直方图」求和；涨停/跌停取池子 `tc`；连板高度取池内 `lbc` 最大值 | **只返回当日快照、不支持按日期查询**，无法回填历史。本仓库每天存一份到 `_breadth_history.json`（随仓库提交）自建序列，满 5 天才画趋势 |
| `/api/cn-rates` | 东财 datacenter | 2/5/10/30Y 到期收益率（%）；`cn_10y_2y` 等利差列单位是 **%**，×100 才是 bp；`derived.*_bp` 已是 bp | 上游偶发「只有日期、各期限全 null」的占位行，Worker 已整行剔除，所以 `count` 会小于请求的 `days`（250 → 约 234），**不是漏数** |

**为什么估值换了数据源**：原方案用 legulegu，对云端出口返回 401；中证官网估值页已改版、老接口 404。
蛋卷 `index_eva` 免 Key、含 PE/PB 双分位 + ROE + 股息率，是目前最省事的替代。

**为什么宽度的历史要自己攒**：东财这三个接口忽略 `date` 参数，传历史日期它仍然回当天。
所以「回填」在数据源层面就不可能，只能每天抓一次当日快照。这也是为什么
`_breadth_history.json` 必须随仓库提交（和 `_exchange_shares.json` 一个道理，不提交就永远只有 1 天）。

**准确性怎么保证**：涨跌家数做了交叉校验 —— 用「涨跌幅分布求和」与东财 push2 的
`f104/f105/f106`（涨/跌/平家数）对比，实测差异 <2%（涨 1600 vs 1598、合计 5377 vs 5295），
差异来自是否含北交所与停牌股。**方向与量级都可信，但不做「精确到个位」的承诺**，
所以看板只展示家数与占比，不做「今日上涨家数同比昨日 ±N」这类依赖精确值的推论。

### 4.6 ⑬ 国债曲线面板怎么读（两张图的横轴不同）

这是整个看板最容易误读的一节：**上下两张图的横轴含义完全不同**。

| | 上图 `ratesCurve` | 下图 `ratesSpread` |
| :--- | :--- | :--- |
| 横轴 | **期限**：2Y / 5Y / 10Y / 30Y | **交易日**：最近约 250 天 |
| 纵轴 | 该期限的到期收益率（%） | 所选期限段的利差（bp），可切换 `10Y−2Y` / `30Y−10Y` |
| 线 | 三条，同一条曲线在三个日期的**快照** | 一条，利差的**时间序列** |

三条快照线分别取 `rows[n-1]`（当期）、`rows[n-61]`（60 个交易日前）、`rows[0]`（序列首日，约一年前）。
留这三个时点是为了对比曲线形态：**整体上下平移**＝无风险利率水平变了，**斜率变陡或变平**＝长短端相对变化。

**两图的关联**：上图任一条线上**所选两个期限点的落差**，就是下图在那一天的一个点。
当期橙线的落差对应下图最右端的标注值，蓝色、灰色同理。换句话说，
**下图是把上图的斜率沿时间铺开**，不是另一个独立指标。

**切换两条利差**：`ratesSpread` 上方有两个按钮，默认 `cn_10y_2y`，可切到 `cn_30y_10y`。
切换时由 `drawSpread(key)` 同时更新数据、小标题、按钮高亮与右侧提示 —— **判读口径一并更换，不只是换一条线**：

| 期限段 | 看什么 | 为负意味着 |
| :--- | :--- | :--- |
| `10Y − 2Y` | 短端贴政策利率；走阔多对应宽松预期升温 | 倒挂，市场定价强宽松（历史上极少见） |
| `30Y − 10Y` | 超长端**期限溢价**：走阔＝长端要求更高补偿（供给 / 增长预期 / 久期），走平＝溢价压缩 | 超长端倒挂，与美债衰退叙事不是一回事 |

加第二条的用途：`10Y−2Y` 只看中短段，长端单独走高再回落的那段剧情它完全看不见
（曾出现 `10Y−2Y` 一年下来几乎没变、而 `30Y−10Y` 明显走阔再收窄的情况）。
配色沿用主图橙色；这张图固定近 250 日，**不接缩放**（缩放只作用于前三张主图）。

几个易错点：

- 数据里 `cn_10y_2y` / `cn_30y_10y` 等利差列的单位是 **%**（如 0.3936），看板 ×100 显示成 **bp**（39.4）；`derived.*_bp` 已经是 bp。
- 「250 日前」是名义叫法。`cn-rates` 会整行剔除上游偶发的全空占位行，请求 250 天通常只剩约 **234 条**（见 4.5 表格），
  `rows[0]` 是序列首日、约一年前，并非精确的 250 个交易日前。曲线末端标签同时写相对描述与真实月日，**以日期为准**。
- 三条线在 30Y 附近可能交叉（长端与短端走势不同步），这是真实形态，不是画错；末端标签为避免重叠做了 13px 强制避让，
  所以标签位置不一定贴着对应线的真实高度。
- 红色虚线 0 轴是**所选期限段**的倒挂分界。中国国债这两段利差长期为正，0 轴通常离当前值很远；注意 `30Y−10Y` 为负是**超长端倒挂**，不要套用美债 `10Y−2Y` 倒挂那套衰退叙事。

与 ⑨ 的分工：⑨ 看银行间**资金价格**（DR007 / SHIBOR，回答「钱紧不紧」），
⑬ 看**债券收益率曲线**（回答「钱贵不贵」）；算股债性价比时，分母用的是 10Y 国债收益率。

---

## 五、流水线与产物

```
daily_run.py
 ├─ fetch_exchange.py    交易所官方 ETF 份额/净值（T+0）          → _exchange_shares.json（失败降级）
 ├─ fetch_data.py        沪深300 + 创业板：2 个指数 + 8 只 ETF  → raw_data.json
 ├─ fetch_ratios.py      三大风格/股债比价（周K全周期）        → ratios.json      （失败降级）
 ├─ fetch_fred_lsi.py    FRED 20 序列 + LSI + 20 项报警         → lsi.json         （失败降级）
 ├─ analyze_report.py    双宽基诊断                             → summary.json / series_<key>.json
 ├─ fetch_signals.py     市场环境六件套（估值/资金面/国债/折溢价/宽度/跨资产比价）→ signals.json（失败降级）
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
| `fetch_signals.py` | 市场环境六件套取数（指数估值 / 境内资金面 / 国债曲线 / ETF 折溢价 / 市场宽度 / 跨资产比价），六项独立容错，写 `signals.json` + 追加 `_breadth_history.json` |
| `render.py` | matplotlib 四行布局 PNG |
| `make_dashboard.py` | 自包含交互 HTML（无外部依赖，离线可看） |
| `send_mail.py` | 汇总邮件（标题含三状态，正文六段：① ② 双宽基诊断 → ③ 风格/股债性价比 → ④ 宏观 LSI（核心表含 `US02Y − EFFR` 加息/降息周期判据）→ ⑤ 市场环境六件套（估值/资金面/国债/折溢价/宽度/跨资产比价，末尾附「一句话综合」）→ ⑥ 内嵌 PNG） |
| `daily_run.py` | 编排入口 |
| `westock-data/` | 腾讯自选股取数 CLI（Node，零第三方依赖，随仓库携带） |

运行期产物（不提交进仓库）：`raw_data.json`、`ratios.json`、`summary.json`、`lsi.json`、
`lsi_status.json`（数据完整性报告）、`signals.json`、`etf_lsi_dashboard.html`、`etf_lsi_monitor_latest.png`。

**随仓库提交的数据资产**（两个，删了才有麻烦）：
`_exchange_shares.json`（沪市份额 250 天）与 `_breadth_history.json`（市场宽度日快照）——
它们不是产物，是「取不到时唯一的兜底」和「上游不支持历史查询时唯一能攒出序列的地方」。

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

### 2. 配置密钥（Actions Secrets，必填项）

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

#### 密钥配置清单（必填项，以 `.github/workflows/daily.yml` 实际引用为准；本仓库不含任何明文）

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

### 4.5 看板图表交互（三张图能缩放，另有一张固定 250 日的小图）

看板上有四张手写 SVG 图：沪深300 双轴、创业板双轴、宏观 LSI vs GLI（这三张可缩放）、以及 ⑤-3 的 `US02Y − EFFR` 缺口图。前三张支持同一套操作：

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

**⑤-3 `US02Y − EFFR` 缺口图**是唯一一张**不接缩放控制器**的图：固定取最近 250 个交易日（约 1 年），
因为它的用途是「看周期有没有切过来」，不需要放大到某几天。实现上把同一条 `<path>` 画两遍，
分别用 `clipPath` 裁到零轴上下两个矩形里着色（上红＝定价加息、下绿＝定价降息），
比用两条线各自断开更简单，也不会在穿越零点处出现断口。刻度用「整齐步长」
（`1/2/5 × 10^n`）而不是等分，否则会出现 `130 / 72 / 14 / −44` 这种读不出量级的轴。

> 没有引入任何图表库，仍然是手写 SVG（0 依赖、页面 190 KB 左右），所以手机端也不会卡。

### 5. 历史缓存

`raw_data.json`（1250 交易日 ≈ 5 年 × 2 赛道）与 `ratios.json`（周K全周期）通过 `actions/cache` 跨运行滚动复用。
**滚动窗口，不会越长越胖**：`fetch_data.py` 每次写回缓存前会把窗口（`ETF_DAYS`，默认 1250 个交易日）之外的
旧日期直接丢掉，所以 `raw_data.json` 体积恒定在 1.6 MB 左右，不会一年年堆积；
`_exchange_shares.json` 同样只保留最近 `ETF_EXCHANGE_DAYS + TAIL` 天（约 260 天），恒定在 0.6 MB。
**`lsi.json` 故意不缓存**——宏观数据必须每天新算；若缓存，一旦 FRED 抓取失败就会拿前一天的旧文件顶上，
把陈旧数据当成当日结果发出去。不缓存时，宏观模块失败会让看板直接隐藏该区块，这更诚实。
**每次运行仍会强制重抓最后 5 个交易日**（ETF 份额 T+1~T+2 披露，需要回填）。

### 6. 产物

每次运行上传 `etf-lsi-report` 构件，含 PNG / HTML / summary.json / ratios.json / lsi.json，14 天内可下载。

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
| `ETF_REFRESH_TAIL` | `5` | 每次强制重抓的尾部交易日数（份额披露滞后回填） |
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
之后靠 `raw_data.json` 缓存，每次只增量抓新增日 + 强制重抓尾部 5 天。

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

## 十二、给 AI 的维护提示词

> 这一章是写给「下一次接手这个仓库的 AI」的操作手册。人类读者可以跳过；但如果你的任务涉及改代码、
> 修数据、换标的、加面板，**请先读完 12.1～12.4 再动手**，12.5 是可整段复制给 AI 的提示词。

### 12.1 仓库速览：哪个文件能改、改了会炸什么

| 文件 | 职责 | 改之前必须知道 |
| :--- | :--- | :--- |
| `config.py` | 全部口径与常量：`TRACKS`（4+4 只 ETF、指数代码、文案）、`RATIO_PAIRS`、`FRED_SERIES`、`LSI_TH`、配色（红涨绿跌） | **单一事实源**。改标的、改阈值、改文案都只在这里改；`ORDER = ['hs300','cyb']` 决定渲染顺序，别乱动 |
| `fetch_exchange.py` | A 股链路取数：沪份额（Worker→直连）、深份额（xlsx）、净值（Worker→东财）、交易日历（Worker） | 这是 2026-11 迁移**唯一**改过的文件。它只消费 Worker 的 HTTP 契约，不依赖 akshare |
| `fetch_data.py` | ETF 行情 / 市值 / 周K，维护 `raw_data.json`、`ratios.json` 滚动缓存 | 缓存窗口裁剪在这里；写回前会丢弃 `ETF_DAYS` 之外的旧日期 |
| `fetch_fred_lsi.py` | 宏观 20+ 条 FRED 序列 → LSI、报警、`lsi.json`、`lsi_status.json` | **宏观链路，禁止顺手改**（除非任务明确要求动宏观）。改坏了看板整块变 null，而退出码仍是 0 |
| `common.py` | FRED 请求封装 `http_json(url, csv_id=…)`，JSON 挂自动走 CSV | `csv_id` 参数**不能省**，省了就等于放弃第二条通道（见铁律 7） |
| `make_dashboard.py` | 手写 SVG 渲染整张看板（无图表库，0 依赖） | 所有动态内容由 JS 渲染，不存在占位符子串覆盖问题（见铁律 5） |
| `render.py` / `analyze_report.py` / `send_mail.py` | PNG 渲染 / 六步指标计算与五档判定 / 邮件组装发送 | 邮件用 `%+.1f`，**别再手动拼接 `+`**（会出 `++12.7`） |
| `check_lsi_status.py` | **数据完整性闸门**，读 `lsi_status.json`，空序列/兜底异常就非 0 退出 | 工作流最后一步跑它，故意放在「发看板 / 上传 artifact」之后，让当天仍能拿到降级看板 |
| `fetch_signals.py` | 市场环境六件套（估值/资金面/国债/折溢价/宽度/跨资产比价）→ `signals.json` + `_breadth_history.json` | 六项**各自独立容错**，全挂也只是对应面板不出现；新增面板只动这个文件 + `make_dashboard.py` |
| `daily_run.py` | 本地一键跑全流程 | — |
| `.github/workflows/daily.yml` | 调度 + 发布 + 闸门 | `cron: "17 13 * * 1-5"`（北京 21:17）有原因，见 12.3 第 5 条 |
| `_exchange_shares.json` | 沪市份额缓存（约 260 天，600 KB 上下），**随仓库提交** | 它是「取不到时的真实兜底」，删了就等于把一次限流放大成数据空洞 |
| `westock-data/` | 腾讯自选股 Node CLI，仅作滞后快照源 | 需要 `node 20`，工作流已配 |

### 12.2 两条链路的边界（最容易越界的地方）

```
宏观（境外）  fetch_fred_lsi.py ─┐
                                  ├─ common.py ── FRED API ── 需 FRED_API_KEY
                                  ┘   ← 2026-11 迁移「一行未改」

A 股（境内）  fetch_exchange.py ── a-stock-api Worker ──┬─ query.sse.com.cn
                               └─ 直连兜底 ─────────────┴─ www.szse.cn / fund.eastmoney.com
                                   ← 迁移只动了这半
```

- **改 A 股部分**：不要碰 `fetch_fred_lsi.py` / `common.py`。
- **改宏观部分**：更不要顺手去动 Worker，那是另一个仓库（`wj624/a-stock-api`）的事。
- **Worker 挂了怎么办**：先去看 [`a-stock-api` 的 README](https://github.com/wj624/a-stock-api/blob/main/README.md)，
  里面有上游映射表、Runbook 和一份可直接复制给 AI 的同步提示词。
  只要 `/api/etf-shares`、`/api/fund-nav`、`/api/trade-calendar` 的**字段名与单位**不变，**本仓库一行都不用改**。

### 12.3 六个必踩坑（按踩坑频率排序）

1. **「200 + 空数组」不等于「当天没数据」**（2026-11 的真实事故）
   Worker 曾把上游失败吞成 `200 + {"data":[],"count":0}` 并写进 KV 缓存一小时，客户端把空表当「当天无披露」直接跳过，
   于是 9 天里静默丢了 5 天，日志仍然是一片绿。现在的正确写法在 `fetch_sse()` 里：
   ```python
   try:
       out = _sse_via_worker(date_compact)
       if out:
           _BREAKER.ok(); return out
       err1 = RuntimeError('Worker 返回空表')      # 空表 → 当作失败，改直连复核
   except Exception as e1:
       err1 = e1
   ```
   **只有「直连也是空」才算真的没有数据。** 任何新加的接口调用都要照这个模式写。
2. **单位：沪市 ×10000，深市不乘**
   上交所原始字段 `TOT_VOL` 是**万份**，`× 10000` 才是「份」；深交所 xlsx 的 `基金规模(份)` **本身已是份**，再乘就是 10000 倍错误。
   两条路径都统一 `round(..., 2)`，抹掉 `万份 × 1e4` 产生的 `…99.99999` 浮点噪声，
   否则 600 KB 的份额缓存每天都会出现「值没变但末位抖了」的无意义 diff。
   验证锚点：`510300` 在 2026-11-03 应为 `44,587,387,700` 份。
3. **`IORB` 必须同时「在 `FRED_SERIES` 里」和「在 `_CAL_EXCLUDE` 里」**
   `LSI = (SOFR − RRP) + (EFFR − IORB)`，删了就少一项；但它是政策利率，FRED 会预填未来日期且含周末行，
   一旦参与构造交易日历，`lsi.asof` 就会被顶到明天（真实事故：A 股口径 `asof=2026-10-30`、宏观口径 `asof=2026-11-02`）。
   **两个位置要求正好相反，看到一处不要就动手。**
4. **缓存策略是设计，不是随手**
   - `lsi.json` **故意不缓存**：宏观数据必须每天新算。缓存了，FRED 一失败就拿旧文件顶上，把陈旧数据当当日结果发出去。不缓存时宏观失败会让看板隐藏该块——这更诚实。
   - `_exchange_shares.json` **必须随仓库提交**（不走 `actions/cache`，那份缓存 7 天不用会被清掉，届时又要全量重抓 250 天）。
   - `raw_data.json` / `ratios.json` 走 `actions/cache`，写回前按 `ETF_DAYS`（默认 1250）裁剪窗口，体积恒定 1.6 MB，**不会越长越胖**。
   - 每次运行强制重抓最后 **5 个交易日**（份额 T+1~T+2 披露，要回填）。
5. **`cron` 是 21:17 而不是 19:00，`timeout` 是 45 而不是 55**
   纽约联储每天美东 08:00 才公布当日 SOFR / EFFR / IORB，换北京时间是夏令时 20:00 / 冬令时 21:00；
   19:00 跑只能拿到前一天的旧利率。21:17 在两种时制下都晚于美东 08:00，也晚于沪深晚间披露。
   一天只跑一次（避免两封邮件），当天补跑用 `workflow_dispatch`。
   超时 45 分钟是迁移 Worker 之后重算的：250 天回填从「分钟级 + 高失败率」变成「秒级」，依赖从 akshare（连带 pandas）瘦到 4 个包。

6. **市场环境六件套的四个口径陷阱**（2026-11 新增，最容易「看着对其实错」）
   - **估值字段互补**：`pe_pct` 与 `pe_over_history` 相加恒等于 1，互为倒数关系。看板只用 `pe_pct`，误用另一个会把「贵」看成「便宜」，且数字本身完全合理、不会报错。
   - **回购定盘只回 1 个月**：中国货币网的 `FrrHis` 忽略 `startDate`，永远只返回最近约 21 个交易日，而 SHIBOR 能给 60+ 天。若照原样画，图左侧会出现一大段「只有 SHIBOR、没有 DR007」的空白——现在从首个 DR007 有效点起画。
   - **宽度没有历史**：东财 `push2ex` 三个接口都忽略 `date` 参数，传历史日期仍回当天。所以「回填」在数据源层面不可能，只能每天存一份到 `_breadth_history.json`（**必须随仓库提交**，不提交就永远只有 1 天）。
   - **利差是 % 不是 bp**：`cn-rates` 的 `cn_10y_2y` / `cn_5y_2y` / `cn_30y_10y` 都是「百分点」，上游给的 `0.3936` 表示 **39.4 bp**。直接当 bp 用会小 100 倍，而且数字看起来依旧「像那么回事」，不会报错；只有 `derived.*_bp` 三个字段才是 bp。

**可调旋钮（全部走环境变量，代码里有默认值，一般不用改）**

| 变量 | 默认 | 作用 |
| :--- | :---: | :--- |
| `ETF_API_BASE` | `https://a-stock-api.wj4020410.workers.dev` | Worker 地址；换域名只改这里 |
| `ETF_API_TIMEOUT` | `30` | Worker 单次请求超时（秒） |
| `ETF_EXCHANGE_DAYS` | `250` | 份额缓存窗口（交易日） |
| `ETF_EXCHANGE_TAIL` | `10` | 尾部强制重抓天数 |
| `ETF_SSE_WORKERS` | `4` | 第 1 轮并发线程数 |
| `ETF_MAX_SSE_CALLS` | `320` | 单轮沪市请求上限（防失控） |
| `ETF_SSE_RETRY` | `3` | 单日重试次数 |
| `ETF_SSE_BREAKER` | `12` | 连续失败多少天触发熔断 |
| `ETF_SZSE_CHUNK` | `20` | 深交所 xlsx 每次请求的日期跨度 |
| `ETF_DAYS` | `1250` | `raw_data.json` 滚动窗口（交易日） |
| `FRED_API_KEY` | 空 | **必填**，空则宏观模块自动降级、其余正常 |

### 12.4 四类常见任务的 SOP

**A. 上游 / Worker 变了，本仓库要不要改？**
① 先读 `a-stock-api` 的 README 与 `/api/etf-shares` 契约；② 拿一个已知日期核对字段名与单位（`unit` 字段写着 `shares_10k = 万份`）；
③ 单位或字段名变了 → 只改 `fetch_exchange.py` 的 `_sse_via_worker` / `_nav_via_em_direct`；④ **不要**在这里重新引入 akshare。
验证：本地 `python fetch_exchange.py`，再用 `python -c` 读 `_exchange_shares.json` 对比 `510300` 的值。

**B. 换标的 / 加一只 ETF**
只改 `config.py` 的 `TRACKS[...]['etfs' | 'etf_list' | 'labels']`，`etf_list` 与 `etfs` 必须**同步**（前者带显示用纯数字代码）。
`out_prefix` 决定产物文件名，改名会让历史缓存对不上，**非必要不改**。
验证：跑一轮，确认新代码在 `_exchange_shares.json` 里有值，且看板「近 5 日份额明细」行数正确。

**C. 份额有缺口（`meta.sse_failed_dates` 非空 / `sse_breaker_tripped: true`）**
① 看是「Worker 通道挂」还是「两条都挂」——日志里 `~ sse ... Worker 返回空表，改直连核对` 是前者；
② 缺口不是永久的：下一轮 `pick_todo()` 会把「窗口内缺失日期 + 尾部 10 天」全部重抓，通常第二天自愈；
③ 如果连续多天都缺，去查 Worker（`a-stock-api` README §10 排障手册），**不要**在客户端加「用前一日份额顶替」的兜底——
份额每天在变，顶上去就是假数据。

**D. Action 红了怎么读**
先看**最后一步**是不是 `Check LSI data completeness`——它红了说明数据缺项（看板已发出，但内容降级），
去看 `lsi_status.json` 里的空序列清单，再看 FRED 是不是挂了；
如果红在更前面（取数 / 渲染 / 发信），按报错原文定位，注意 `JSONDecodeError: line 1 column 1` 基本等于「源站回了空响应 / HTML」，不是格式问题。

### 12.5 可复制给 AI 的提示词

```text
【任务】维护 https://github.com/wj624/etf-lsi（沪深300 + 创业板 ETF 持仓背离 + 宏观 LSI 压力指数日报）。

【先读什么】
1. README 第四章「数据源、单位换算与剔除项」→ 认两条链路：宏观走 FRED，A 股走自建 Worker。
2. README 第九章「防 Bug 铁律」8 条 → 都是真实踩坑，禁止回退。
3. README 第十二章（本章）→ 12.1 文件职责表、12.3 六个坑、12.4 SOP。
4. 要动 A 股取数时，再去读 https://github.com/wj624/a-stock-api 的 README（有上游映射表与同步提示词）。

【硬约束，违反即算错】
- 只改 A 股那半（fetch_exchange.py）时，fetch_fred_lsi.py 与 common.py 一行不许动；反之亦然。
- Worker 返回 200 + 空数组 ≠ 当天没数据。必须直连复核，只有「直连也空」才算真无数据。
- 单位：上交所 TOT_VOL 是万份 → ×10000；深交所 xlsx 已是份 → 不许再乘。两条路径都要 round(...,2)。
- IORB 必须留在 FRED_SERIES，同时必须留在 _CAL_EXCLUDE（两处要求相反）。
- lsi.json 不缓存；_exchange_shares.json 随仓库提交；不许引入 actions/cache 存它。
- 红涨绿跌（净申购/正 Spread 红 #E8453C，净赎回/负 Spread 绿 #1FB37A），格式化用 %+.1f，不要手拼 "+"。
- 不允许「用前一交易日份额顶替缺失日」这种兜底。
- 不要重新引入 akshare（requirements.txt 只保留 matplotlib / numpy / requests / openpyxl）。
- 市场环境六件套（`fetch_signals.py`）必须保持「各项独立容错」：任一端点失败只让对应面板消失，
  绝不能因为拉不到估值就让整轮看板失败。
- 估值只用 `pe_pct`，不要用 `pe_over_history`（两者互补，用错会把贵看成便宜且不报错）。
- `_breadth_history.json` 与 `_exchange_shares.json` 都是随仓库提交的数据资产，不要当产物清理。

【改完必须自检】
1. python fetch_exchange.py → 日志应出现「第 1 轮 N/N 天成功，失败 0」，不应出现熔断。
2. 读 _exchange_shares.json：510300 在 2026-11-03 应为 44587387700.0 份（锚点，用于确认单位没跑偏）。
3. python check_lsi_status.py → 退出码 0；若宏观降级，说明 lsi_status.json 有空的 FRED 序列，需说明原因。
4. 本地跑一轮后看 etf_lsi_dashboard.html：宏观块与 ETF 块都要有数，不是 null。
5. 提交前确认没有把任何密钥写进代码（FRED key、SMTP 授权码只存在于 Actions Secrets）。

【提交规范】
commit message 用中文，说明「改了什么 + 为什么」，涉及口径的改动要同步更新 README 第四 / 第九章。
```

### 12.6 动手前的三行自检

- 我要改的文件属于**宏观半**还是**A 股半**？越界了吗？
- 这次改动会不会让某个「本来有值」的字段变成空 / null，而退出码照样是 0？
- 改完能不能用 `510300 = 44587387700.0` 这个锚点验证单位没跑偏？

---

## 十三、跨资产比价卡片（金银比 / 金油比 / 铜金比 / KOSPI-GOLD）

表头 9 张卡之后单独一行「跨资产比价 / 风险偏好」，4 张卡，数据来自自建 Worker 的
`/api/macro-ratios`（`wj624/a-stock-api`），由 `fetch_signals.py` 的 `get_macro_ratios()` 抓取，
写进 `signals.json` 的 `macro_ratios`，再由 `make_dashboard.py` 注入 `D.signals.macro_ratios`。

| 卡片 | 口径 | 显示 |
|---|---|---|
| 金银比 | 纽约黄金 `GC`(美元/盎司) ÷ 纽约白银 `SI`(美元/盎司) | 当前值、20 交易日变化、近 250 日分位 |
| 金油比 | `GC` ÷ WTI 原油 `CL`(美元/桶) | 同上 |
| 铜金比 | 美铜 `HG`(美分/磅) ÷ `GC` × 1000 | 同上 |
| KOSPI / 黄金 | `znb_KOSPI` 点位 ÷ `GC` 日 K 收盘（美元/盎司） | 当前值、固定阈值信号、距上下限百分比 |

**KOSPI/GOLD 阈值**：`> 1.85` → 数值红色 + 「卖股票」；`< 1.10` → 数值绿色 + 「买股票」；
中间为默认色 + 「中性」。这是**固定值，不随分位数漂移**。说明行额外显示「距上限 / 距下限」，
含义是**当前值还需变动多少百分比才触线**（上限为正＝要涨，下限为负＝要跌）。

**注意两处口径**：
1. 这一行的红绿是**买卖信号色**，不是全站「红涨绿跌」的涨跌色，别混着读。
2. 外盘日 K 最后一根是**当日盘中快照**、非结算价；KOSPI 是实时/收盘快照，两者时点略有错位。
   三个比值的分位基于 2016-11 以来的共同交易日（约 2500 根），KOSPI 没有免费历史源，故不给分位。

**降级**：`/api/macro-ratios` 失败时只让这一行 4 张卡与小标题不显示，错误写进
`signals.json` 的 `errors`，主看板 / ETF 背离 / 宏观 LSI 完全不受影响。

---

## 附：配色说明

遵循 A 股习惯 **红涨绿跌**：净申购 / 正 Spread / 报警触发 → 红色 `#E8453C`；
净赎回 / 负 Spread / 正常未触发 → 绿色 `#1FB37A`。
（注意这与欧美「绿涨红跌」相反。）

---

## 附录 · 2026-11-05 全量整改记录（给维护者 / 给 AI 读）

> **这一节是什么**：AI 维护助手在 2026-11-05 对账号下 6 个仓库做完一次「大范围彻底修复」后追加的说明。目的只有一个——**让下一次维护（不管人或 AI）能看懂每个改动为什么做、哪些绝对不能回退**。
>
> **怎么读**：改任何代码之前，先读本 README 前文的「维护须知 / 铁律 / 给 AI 的维护提示词」，再读本附录。**两者冲突时以前文铁律为准**；本附录只解释本次改动，不新增、不覆盖任何设计口径。
>
> **本次原则**：用户要求「稳定、基本无维护、占用空间少、不自动生成垃圾」，并明确「修改前先看 README 的设计思路与维护须知」。因此本次只修**确定性 bug、静默失败、危险工作流行为、文档与代码不一致、依赖版本失控、运行时垃圾文件**；**没有做架构改造，没有删任何数据资产，没有改任何口径/阈值/单位/cron/构建顺序**。
>
> **本次改动范围**：6 仓共 40 个文件、0 删除；逐仓白名单精确提交，全程无 `--force`、无 rebase 冲突。**上线后的串行补测又追加了一次 pandas 3.x 兼容性修复（3 仓 6 文件，见 F 节），所以最终线上状态以 F 节为准，A 表里凡是写 `pandas<4` 的地方都已收紧为 `pandas<3`**。

### A. 本次改了什么（逐文件）

| 文件 | 原始缺陷（为什么必须改） | 本次修法 | 依据 / 约束 |
|---|---|---|---|
| `common.py`（4 处） | 导入期就执行 `NODE = find_node()` / `IDX = os.path.join(find_skill(), ...)`，且硬编码 3 条 **Windows 本机绝对路径**；只想用字体/表格工具的模块（`render.py` 等）也会因缺 node 崩掉 | 删本机绝对路径；`find_node()` / `find_skill()` 缺依赖返回 `''`，**导入期不再抛错**；`run()` 在真正取数时缺依赖则**显式 `RuntimeError`**——刻意不返回空串，避免下游 `first_table` / `split_by_code` 把空串变成 `None` 静默写进数据资产 | §9 防 Bug 铁律、§12.5 硬约束（不用空数据顶替）；`westock-data` 不能删 |
| `check_lsi_status.py` | **数据完整性闸门**读 `lsi.json` 失败只打 warning，仍可能 0 退出，坏数据会放行 | 改 `error` 且 `bad = 1`（非 0 退出） | README 明确它是「数据完整性闸门」 |
| `fetch_data.py` | 单日抓取失败 / 缓存不可用被静默吞掉 | 升级为 `::warning::`（CI 可见），不改回退链 | 取数容错链路 |
| `.github/workflows/daily.yml`（4 处） | `actions/cache` 的 key 用 `github.run_id`（每次不同，**缓存永不命中**）；`rebase` 失败 `exit 0` 假装成功；缺缓存文件静默；Pages 未生成看板 `exit 0` | key 改稳定 `hashFiles('requirements.txt')`；rebase 失败 `exit 1` + `::error::`；缺缓存改 warning（降级模块可容忍）；Pages 未生成看板 `exit 1` | gh-pages + Cloudflare Pages 双发布链路**保留**（README 未授权删） |
| `.github/workflows/monthly-snapshot.yml` | 每月自动 force 重写历史，会抹掉 `_exchange_shares.json` 等数据资产历史 | **停用 `schedule`**，保留 `workflow_dispatch`；guard 增加 `*.json` 校验；回滚 SHA `retention-days` 90 → 365 | 不删文件、不改主体 |
| `requirements.txt` | 依赖无上界 | `matplotlib<4` / `numpy<3` / `requests<3` / `openpyxl<4` | 「只保留四个依赖」口径 |
| `.gitignore` | `.env.example` 声称 `.env` 已被忽略，实际没有 | 追加 `.env` | 凭证不进代码 |
| `README.md` | 19:00 应为 21:17；「强制重抓最后 8 个交易日」应为 5；90 天应为 14 天；件套数不统一；重复 `LSI_CAL_DAYS 820`；指向已删私有库 `wj624/etf-lsi-monitor`；目录缺十二、十三；「五个必踩坑」实为六个 | 逐项订正 | §9 防 Bug 铁律 8 条、§12.4 SOP、§12.5 硬约束**全部保留** |

### B. 本次坚决没改（硬约束，改了就是破坏设计）

- **`_is_stale` 不捆绑 `nav`**；**`chg[i] = shares[i] − shares[i−1]`** 未改。
- **`IORB` 必须同时在 `FRED_SERIES`（`config.py`）与 `_CAL_EXCLUDE`（`fetch_fred_lsi.py`）里**。
- **`http_json(url, csv_id=...)` 的 CSV 兜底不能删**；上交所份额「开工探测 + 两轮 + 熔断」不能简化。
- **不允许用前一交易日份额顶替缺失日**；利差单位是 `%` 不是 bp。
- **`_exchange_shares.json` 与 `_breadth_history.json` 必须随仓库提交**；`westock-data` 保留。
- **cron 21:17、`TZ=Asia/Shanghai` 保留**；gh-pages / Cloudflare Pages 双发布链路保留。

### C. 明令作废的旧建议（别再走回头路）

第一轮「只读体检报告」里提出过若干架构建议，**读完各仓 README 的维护须知后已全部作废**，本次一个都没采纳：

- ❌ **「产物不入库 / 数据与页面不进 git」**：本仓产物是 Pages / EdgeOne Pages / GAS 的**数据源本身**，从仓库检出，必须入库。
- ❌ **「删 `cache/` / 改回 `actions/cache`」**：`cache/` 是断网降级与历史累积的命根子。
- ❌ **「删数据资产 / 删摘要文件 / 清理 `echarts.min.js` / 删 `akshare` / 删 `westock-data`」**：均被 README 明确点名保护。
- ❌ **「把 `except: pass` 全改抛错」**：局部容错（TTL 状态、日志编码、临时文件清理、上游回退链）是设计，不是缺陷；本次只把**主流程**的静默失败改成显式失败。
- ❌ 早期报告曾把 GAS 脚本里的 `RECEIVER_EMAIL` 硬编码列为 bug —— **不是 bug**，它是 `CONFIG` 里明确列出的默认配置项，本次未改。

> 若下次 AI 读到 `wj624-仓库体检与整改思路.md` 或 `wj624-整改落地手册.md` 里的 P1/P2 建议，请以本附录为准：**那两份是整改前的中间产物，已作废**。


### D. 给 AI 的维护边界（可复制这段）

```
你在维护 wj624/etf-lsi。动手前：
1. 先读 README 九、防 Bug 铁律（8 条）与十二、给 AI 的维护提示词（12.4 SOP / 12.5 硬约束），再读本附录。
2. 绝对不要：删 _exchange_shares.json / _breadth_history.json / westock-data；删 http_json 的 CSV 兜底；
   简化上交所「开工探测 + 两轮 + 熔断」；用前一日份额顶替缺失日；把 IORB 从 _CAL_EXCLUDE 里拿掉；
   改 cron 21:17 或 TZ；恢复 monthly-snapshot 自动 schedule；用 force push。
3. common.py 的 run() 在缺依赖时必须显式抛错，不要「返回空串」——下游会把空串变成 None 静默写进数据。
4. check_lsi_status.py 是数据完整性闸门，任何读取失败都必须非 0 退出。
5. 改了数据源/单位/调度，同步 README 四（数据源与单位换算）、五（流水线与产物）、九（铁律）、十二（提示词）。
6. 线上写操作：精确 git add、中文 commit、git pull --rebase、绝不 force。
```
### E. 验证与回滚

| 项目 | 说明 |
|---|---|
| 本地验证 | 补丁脚本在从原仓库 `git archive HEAD` 导出的**干净副本**上端到端重跑：59/59 替换、2 处追加、2 个新建 `.gitignore`、5 个 `monthly-snapshot.yml` 降级；`.py` 用 `ast.parse`、`worker.js` 用 `node --check`、`.yml` 用 `yaml.safe_load`，语法自检 26 项全 PASS |
| README 硬约束复核 | 61 项，实际 61/61 通过（初检 5 项 FAIL 均为检查规则误报） |
| 线上内容核验 | GitHub API 独立核验：commit 主题、变更文件集合与白名单逐仓一致、**0 删除**、关键修复内容、数据资产 12/12 在线 |
| 线上实测 | 2026-11-05 串行手动触发 4 个核心 workflow 并逐个核验：4/4 全部 success、每仓产物 commit 均 removed=0、关键数据资产完好。第一次补测在 rotation-monitor 暴露 pandas 3.x 移除 resample('M') 的问题，双保险修复后重跑通过。明细与最终线上 HEAD 见下方「F. 补测实测记录」 |
| 令牌 / 垃圾 | 交付文件 `ghp_` / `github_pat_` 0 命中；仓库内不生成 `__pycache__` |

**回滚**：优先 `git revert <整改 commit>` 生成反向 commit 再 push（保留历史、无需 force）。整改前基线 `efe6dc4b`，整改 commit `606958f1`（`git revert 606958f1`）。**本仓 `daily.yml` 是 `push` 触发**，本次整改 commit 的 `ETF + LSI daily report` 已 `success`；该 run 之后按 README 设计又产生了自动产物 commit（写本附录时线上 HEAD 已到 `8e8f74f`，会继续前移，这是正常行为，不要当异常）。回滚时若其后已有自动产物 commit，按需一并评估。

**下次改代码前的三行自检**（沿用前文铁律）：
1. 这个文件是源码还是产物？产物只能靠重跑生成，不能手改。
2. 改动会不会破坏「数据资产 / 口径 / 阈值 / 单位 / cron / 构建顺序」？会就停手。
3. 改完要跑什么验证、要同步 README 哪几节？写进 commit body。

### F. 补测实测记录（2026-11-05，含 pandas 3.x 兼容性二次修复）

整改 commit 上线后，用户要求对 4 个「`push` 不触发、只在 `schedule` / `workflow_dispatch` 跑」的核心抓数流水线做**串行手动触发补测**：一个跑完、核验通过，再触发下一个，避免并发写 `main` 冲突。

**第一次补测在 `rotation-monitor` 失败**，日志关键行：

```
ValueError: 'M' is no longer supported for offsets. Please use 'ME' instead.
  File ".github/workflows/generate_page.py", line 130, in ...
    monthly = bd.set_index('date')['close_cyb'].resample('M').last()
```

根因：pandas 3.1.1 于 2026-11-04 发布，移除了 `resample('M')` 别名，并默认开启 Copy-on-Write、改变字符串 dtype。**整改前依赖本无上界**；本轮整改把上界写成 `<4` 过宽，且 `daily_update.yml` 的 `pip install` 行仍是完全无上界 —— 这是策略失误，已按下面「双保险」纠正。

**双保险修复（3 仓 6 文件）**：

1. **代码**：`rotation-monitor/.github/workflows/generate_page.py` 的 `resample('M')` → `resample('ME')`（pandas 2.3.3 与 3.0.0 下语义一致，均为月末重采样，本地实测两种版本输出一致）。
2. **依赖**：所有 pandas 约束收紧为 `<3`，且 **`requirements.txt` 与 workflow 的 `pip install` 行两处同步** —— 线上实际执行的是 workflow 里的 pip install，不是 requirements.txt，只改一处等于没改。
3. **二次 commit**：`rotation-monitor` `ee80a439`、`earl-etf-dashboard` `af8b5237`、`national-team-etf-flow` `b0ef1c6c`。

**修复后重跑，4/4 全部通过**：

| 仓库 / workflow | run id | 结论 | 产物 commit（前 → 后） | 删除 | 关键资产 |
|---|---|---|---|---|---|
| `rotation-monitor` / `daily_update.yml` | 41990306988 | success | `ee80a439` → `1c6dd808` | 0 | `public/index.html` 完好 |
| `us-world-economy-dashboard` / `update.yml` | 41990418511 | success | `e9ee6da9` → `0b18f069` | 0 | `cache/` · `index.html` · `llms.txt` · `snapshot.md` · `version.txt` 完好 |
| `earl-etf-dashboard` / `update.yml` | 41990472730 | success | `af8b5237` → `abdee20d` | 0 | `cache/` · `version.txt` · `llms.txt` · `latest.json` · `index.html` 完好 |
| `national-team-etf-flow` / `daily-refresh.yml` | 41990810766 | success | `b0ef1c6c` → `5110f0f1` | 0 | `_etf_shares_cache.json` · `echarts.min.js` · `index.html` 完好 |

> `a-stock-api`（Worker 部署 + 13 个冒烟端点）与 `etf-lsi`（daily report）由 `push` 触发，整改当时即 `success`，不在上表。

**写本附录时各仓 `main` 的线上实况**（均为短 SHA，位数不影响定位）：

| 仓库 | 整改 commit | pandas 二次修复 | 补测产物 / 当前 HEAD |
|---|---|---|---|
| `a-stock-api` | `daea02a` | — | `daea02a` |
| `us-world-economy-dashboard` | `e9ee6da` | — | `0b18f06` |
| `earl-etf-dashboard` | `75255bd` | `af8b523` | `abdee20` |
| `national-team-etf-flow` | `016a401` | `b0ef1c6` | `5110f0f` |
| `rotation-monitor` | `b5f01af` | `ee80a43` | `1c6dd80` |
| `etf-lsi` | `606958f` | — | `8e8f74f`（自动产物 commit 会继续前移，属正常） |

> **给 AI 的硬约束**：这 3 个仓的 pandas **必须锁 `<3`**，不要「简化」成 `<4` 或去掉上界；`resample('ME')` 不要改回 `'M'`。改依赖时**必须同时改 `requirements.txt` 和 workflow 的 `pip install` 行** —— 第一次补测就是这样崩的。另外这 6 仓**没有单元测试套件**，上述「实测」指真实 workflow 执行 + 产物核验，改完代码仍应手动 dispatch 一次确认。

### G. 后续策略调整 · 按体积自动清理（2026-11-05 同日）

> **本仓情况**：本仓有 `monthly-snapshot.yml`，已按本节改制；`KEY_FILE` 为 `daily_run.py`，不要改错。
>
> **优先级说明**：A / B / D 节记录的是当天**第一版**整改状态，原文保留不改以便追溯决策过程；关于「每月清理」的部分自本节起**以本节为准**：
> - A 表里的「停用 `schedule`」= 停用**旧版「每月 1 号无条件 force 重写 main」**的 schedule；
> - D 节「绝对不要恢复 monthly-snapshot 自动 schedule」= 不要恢复**上面那个旧版**；
> - 本节新增的「按体积体检 schedule」是**有意保留的新机制，不要删、不要改回每月无条件执行**。

#### 为什么要调整

用户指出：当初设计每月清理，是为了防止「每日产物入库」让仓库长期运行后体积膨胀。第一版整改只从「安全 / 可回滚」角度停用了 schedule，**没有回应「空间封顶」这个原始诉求**，等于把自动能力关掉了。实测后确认这个担心成立：

| 实测项 | 数值 |
|---|---|
| 6 仓当时合计体积 | 约 67 MB |
| 最大单个文件 | 4.4 MB（GitHub 单文件硬限 100 MB） |
| 仓库年龄 | 2~6 天（全部建于 2026-10-31 ~ 11-04） |
| 稳定后估算增长 | 约 1~2 MB/天（前几天叠加了整改提交，偏高） |
| 放着不管碰线时间 | 大半年 ~ 2 年到 1 GB 建议线 |
| GitHub 官方口径 | 理想 < 1 GB、强烈建议 < 5 GB，**不是免费版封顶** |
| 6 仓可见性 | 全部 **public**，Actions 分钟数免费不限量 |

结论：不会立刻被封，但会变慢、可能收到 GitHub 提醒邮件，所以「自动封顶」确实需要保留——只是不能再用「每月无条件强推」这种不可回滚的方式。

#### 改成什么

`.github/workflows/monthly-snapshot.yml`：

- `on.schedule` 改为**每周一 UTC 03:00（北京 11:00）只做一次「体积体检」**：读一次仓库 `size`，**低于 500 MB 就直接结束，一个字节都不改、绝不碰 `main` 历史**。
- 仅当 `size >= 500 MB（512000 KB）` 时才执行剪断。按 67 MB 起步、1~2 MB/天估算，约 8 个月~1 年才第一次真正动刀；清完回到约 10 MB 再重新累积，永远远低于 1 GB。
- `workflow_dispatch` 保留，新增 `force` 布尔输入（**默认 false**）：手动触发默认「只体检、不改动」，勾选 `force` 才忽略阈值立即清理。
- 原有护栏**全部保留**：`README.md` / `KEY_FILE` 存在、`git ls-files >= 8`、JSON 合法性校验、root commit 用 Git Data API（`parents: []`）、不走 `git push --force`、不触发 push 工作流、旧 HEAD 记入 artifact `retention-days: 365`、回滚命令写进日志、`concurrency` 互斥。
- **针对「按体积触发」新增一道护栏**：所有被跟踪文件必须 < 50 MB。体积突然暴涨通常是误提交大文件，绝不能把这种异常树固化成「唯一的 root commit」。
- guard 的 JSON 校验从「只查根目录 `*.json`」扩展到「`git ls-files -z '*.json'` 的全部被跟踪 JSON」。
- 体积读取优先 `gh api repos/... --jq .size`，失败回落 `github.event.repository.size`；两者都取不到时**安全跳过、不清理**。

#### 给 AI 的维护边界（追加，不替代 D 节）

1. **不要**把 `on.schedule` 改回「每月 1 号无条件执行」，不要删掉体积判断或改掉 `THRESHOLD_KB`。
2. **不要**把 `force` 默认值改成 `true`，不要去掉手动入口「默认只体检」的语义。
3. **不要**删掉 50 MB 单文件护栏或全量 JSON 校验；它们是「按体积自动」特有的防误固化措施。
4. 想立刻清理：Actions 页手动 dispatch 并**勾选 force**；只想体检：直接 dispatch 不勾选。
5. 清理后 `main` 变成 root commit，**外部克隆 / fork 需要重新 clone**；回滚命令在 run 日志与 artifact 里，保留 365 天。
6. 阈值 500 MB 可调，但**不要调到 1 GB 以上**（失去提前封顶意义），也**不要调到 100 MB 以下**（频繁剪历史）。
7. 判断是否需要清理看的是仓库 `size`（`gh api repos/<owner>/<repo> --jq .size`，单位 KB），不是文件个数或提交数。
8. 线上写操作照旧：精确 `git add`、中文 commit、`git pull --rebase`、**绝不 force**。

#### 验证与回滚

- 验证：改完用 `yaml.safe_load` 校验；在 Actions 手动 dispatch（**不勾选 force**）应看到 `below threshold: nothing to do, main history untouched`，且 `main` HEAD 不变、工作区无改动。
- 回滚本策略：`git revert <本策略 commit>` 即可回到「仅手动入口」的第一版状态；数据资产与其它 workflow 均不受影响。


---

## 附录 · 2026-11-08 新增「给 AI 读的文档」llms.txt / data.json（给维护者 / 给 AI 读）

> **怎么读**：改任何代码前，先读本 README 第九章「防 Bug 铁律」8 条与第十二章「给 AI 的维护提示词」
> （12.4 SOP / 12.5 硬约束），再读本附录。**冲突时以前文铁律为准**；本附录只解释本次改动，
> 不新增、不覆盖任何设计口径。

### A. 这次要解决什么

用户要把一个**链接直接发给 AI**，让 AI 读到本仓库「所有输出数据及内容」，而无需打开 556 KB 的看板 HTML
（里面全是 JS，AI 抓不动）或手动上传文件。参照 `wj624/earl-etf-dashboard` 的 `llms.txt` 约定，
新增一份每日自动更新的纯文本快照，并把链接登记在文首「📱 手机端访问地址」表格里。

### B. 交付物与链接

| 文件 | 用途 | 主地址 | 备用地址 |
| :--- | :--- | :--- | :--- |
| `llms.txt` | 人话快照，约 25 KB，AI 抓取入口 | https://etf-lsi.pages.dev/llms.txt | https://wj624.github.io/etf-lsi/llms.txt |
| `data.json` | 机器可读全量数据，约 420 KB | https://etf-lsi.pages.dev/data.json | https://wj624.github.io/etf-lsi/data.json |

两个域名内容完全一致：`daily.yml` 把两者一起复制进 `public/`，同一份 `public/`
既 `git push --force` 到 `gh-pages` 分支，又由 `wrangler pages deploy public` 上传到 Cloudflare Pages。

### C. 单一真相源（最重要的一条）

`make_llm_summary.py` **只读 `make_dashboard.py` 刚生成的 `etf_lsi_dashboard.html` 里内嵌的 `const D`**。
`const D` 本身就是看板页面上展示的全部数据（两条 ETF 主线、LSI 20 项报警、ratios、signals 六件套、
跨资产比价），因此：

- **不重新取数、不联网、不读任何密钥、不新增依赖**；
- AI 读到的数值与用户在页面上看到的**逐值一致**，不存在两份口径；
- 改指标口径 / 阈值 / 单位只需照旧改 `config.py` 等上游，`llms.txt` 会自动跟着变；
- `data.json` 就是 `const D` 原样导出（`json.dumps` 紧凑格式），不做任何加工。

> 不要为了「让 AI 读起来更全」去另写一份抓数逻辑。那会造出第二条数据链路，正是本仓铁律最忌讳的。

### D. 每天怎么自动更新

```
daily.yml (北京 21:17, 周一~周五)
  → python daily_run.py
       … fetch_* → analyze_report → render → make_dashboard.py（生成 etf_lsi_dashboard.html）
       → make_llm_summary.py（本附录新增；fatal=False，读上面那个 HTML，写 llms.txt / data.json）
       → send_mail.py
  → Persist caches
  → Upload artifacts（清单已加 llms.txt / data.json）
  → Publish dashboard to GitHub Pages：复制进 public/ → push --force 到 gh-pages
  → Publish to Cloudflare Pages：wrangler pages deploy public
  → Check LSI data completeness（数据闸门，位置不变）
```

- `daily_run.py` 的 `STEPS` 里，`make_llm_summary.py` **必须排在 `make_dashboard.py` 之后**（要读它的产物），
  且登记为 `fatal=False`（降级不阻断）。
- `daily.yml` 的 `public/` 组装用 `if [ -f … ]; then cp …; else echo "::warning::…"`，
  **缺文件只告警、看板照常发布**，不新增任何失败点；cron、push 路径、取数步骤、发信、数据闸门一律未动。

### E. 降级边界（为什么不会把主报告搞挂）

生成器内置三层保护：源 HTML 缺失 / `const D` 解析失败 / 生成或写文件异常 →
一律打印 `::warning::` 并 `return 0`，**绝不写空文件、绝不抛异常、绝不让主报告失败**。
字段缺失时用 `.get()` 兜底显示「—」，不会 KeyError；`llms.txt` 里也明确写了
「— = 本轮该模块降级隐藏，不等于数值为 0」，避免 AI 误读。

因此最坏情况只是「这次没有 AI 文档」，看板、邮件、告警全部照常。
`llms.txt` / `data.json` 未生成时，`public/` 里那两行会打印 warning，日志可查。

### F. 产物为什么不提交到 main

`llms.txt` / `data.json` 是**每天重建的发布产物**，只放进 `public/` 由 `gh-pages` / Cloudflare Pages 托管：

- 提交到 `main` 会留下永不更新的过期副本，AI 若读到 main 上的那份就会拿到旧数据；
- `gh-pages` 每次是 `git init` + 单 commit + `--force`，**历史不累积**，420 KB/天不会把仓库撑大；
- `monthly-snapshot.yml` 的 50 MB 单文件护栏扫的是 `main` 的 `git ls-files`，与这两个产物无关。

本地调试用 `python make_llm_summary.py --check`（只打印不写文件）或
`--out /tmp/xxx --src /path/to.html`，不要往工作区根目录留产物。

### G. 给 AI 的维护边界（可复制这段）

1. 先读第九章铁律 8 条、第十二章 12.4/12.5，再读本附录。
2. **不要**手改 `index.html` / `etf_lsi_dashboard.html` / `llms.txt` / `data.json` —— 全是构建产物，
   会被下次流水线覆盖。要改 `llms.txt` 的内容，只改 `make_llm_summary.py`。
3. **不要**删 `daily_run.py` 里 `make_llm_summary.py` 那一步，也不要把它挪到 `make_dashboard.py` 之前。
4. **不要**删 `daily.yml` 里 `public/` 组装的两行 `if [ -f … ]`，也不要把 `|| true` 改成无容错的 `cp`
   （那样生成器降级时会新增一个失败点，违反「降级只隐藏对应区块」的设计）。
5. **不要**给生成器加联网抓数、加密钥、加 pip 依赖；它只读本地 HTML。
6. 新增指标 / 改字段名时，同步改 `make_llm_summary.py` 的 `CORE_CN`、`RATIO_ORDER` 与对应段落；
   缺字段会显示「—」，但不会报错。
7. 改了数据源 / 单位 / 调度，照旧同步 README 第四章、第九章、第十二章。
8. 线上写操作照旧：精确 `git add`、中文 commit、`git pull --rebase`、**绝不 force**。

### H. 验证与回滚

- 本地验证脚本 `verify_etf_lsi_llm.py`：内容覆盖、与 `const D` 逐值一致、`--check` 不写文件、
  5 类降级路径（源缺失 / 无 `const D` / 非法 JSON / 极简 D / 默认源发现）共 **82 项**，全部通过。
- 改 `daily.yml` 会按仓库原有设计（`on.push.paths`）**自动触发一次完整流水线**，用于实测。
- 线上核验：两个域名的 `llms.txt` / `data.json` 均 HTTP 200 且内容一致、`index.html` 未受影响、
  `gh-pages` 分支含这两个文件。
- 回滚：`git revert <本次 commit>` 即可。生成器是纯新增文件，删掉它并回退
  `daily_run.py` / `daily.yml` / `README.md` 三处增量，看板与邮件链路完全不受影响。

### I. 云端 workflow 实测记录

> 待本次提交推送后回填（run 编号、产物提交、线上核验结果）。

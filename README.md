# Arknights Analytics

《明日方舟》IP 周边的商品运营分析工作台。

## 这个工作台要处理的事

周边选品的常见做法是看声量：哪个角色讨论多，就多做哪个。问题是曝光和需求不是一回事。老内容天然积累了更多播放，角色在B站、微博、小红书上的讨论结构也各不相同；只按播放量排序，热门角色容易备货过量，长尾角色的需求又常常被漏掉，高客单品类还容易压库存。

这个仓库把公开内容热度、跨平台一致性、用户问卷、电商公开商品信号和一套模拟 ERP 经营数据串到同一条链路上，让“选哪个角色、做哪个品类、定在什么价位、备多少货、怎么复盘”每一步都能指回证据。分析结论和模拟经营结果分开存放，模拟数据不会被写成真实业绩。

## 工作台构成

前端是本地单用户工作台，共 12 个页签，每个页签对应一个具体的运营动作。

| 页签 | 主要动作 |
| --- | --- |
| 运营总览 | 三类运营简报、关键指标、Markdown 导出 |
| 日常运营待办 | 简报建议转任务，登记负责人、截止日期与处理状态 |
| 商品信息维护 | SPU/SKU 主档编辑、CSV 批量预检、字段级审计与版本锁 |
| ERP 数据处理 | 订单、库存、采购、售后的筛选、金额对账与结果导出 |
| 周边用户调研 | 243 份匿名问卷的分群、角色偏好与价格接受度 |
| 角色与选品 | 内容、问卷、森空岛与商业信号的角色需求融合榜 |
| 角色生命周期 | 事件窗口、复采增量与“待验证”状态标记 |
| GMV 驱动分析 | 连续两个 28 日窗口的订单数/客单价拆解与四类策略演练 |
| 渠道与 SKU 配置 | 210 个模拟 SKU × 7 类渠道的适配评估与费率复核 |
| 商业数据决策 | 售出占比、周转天数、可售天数与库存成本诊断 |
| 决策证据 | 来源性质审计、权重与去源实验、商品身份复核 |
| 数据与服务 | 数据口径、字段字典与服务运行状态 |

## 跑起来

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\run_pipeline.py
```

生成经营分析、商品主档与 SQL 报告：

```powershell
.\.venv\Scripts\python.exe scripts\build_erp_operations.py
.\.venv\Scripts\python.exe scripts\build_product_catalog.py
.\.venv\Scripts\python.exe scripts\collect_skland_strategy.py
.\.venv\Scripts\python.exe scripts\build_operational_analytics.py
.\.venv\Scripts\python.exe scripts\run_sql_analysis.py
```

前端构建后启动平台：

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm build
cd ..
.\.venv\Scripts\python.exe scripts\run_platform.py
```

访问 <http://127.0.0.1:8765/>。平台是本地单用户服务，接口文档在 `/docs`，Prometheus 指标在 `/metrics`。

问卷门户与试点控制台单独跑在 8767：

```powershell
.\.venv\Scripts\python.exe scripts\run_pilot_portal.py --port 8767
```

需要复现问卷链路时，先做质量校验和去标识化导入，再刷新流水线：

```powershell
.\.venv\Scripts\python.exe scripts\import_questionnaire_text.py path\to\明日方舟问卷_243份答案.txt
.\.venv\Scripts\python.exe scripts\run_pipeline.py
```

打印版问卷由脚本直接生成，落盘在 `output/pdf/`：

```powershell
.\.venv\Scripts\python.exe scripts\export_printable_questionnaire.py
```

## 数据来源与规模

| 来源 | 规模 | 口径 |
| --- | --- | --- |
| B站官号 | 549 条历史内容（2019—2026，8 类） | 聚合互动指标，不含评论正文 |
| 微博官号 | 近期 100 条公开博文 | 只对明确命中的角色形成交叉验证 |
| 小红书 | 4 期品牌生态快照 | 衡量平台大盘，不冒充角色级官号数据 |
| 森空岛攻略站 | 60 名角色的搜索快照 | 只读公开搜索结果，不触发浏览计数 |
| 淘宝 | 84 条公开商品快照 | 只记录商品 ID、价格、公开收货人数下界与排名 |
| 匿名问卷 | 243 份回收 | 拆出 729 条角色 Top-3 排序、1,701 条品类价格带观测 |
| 模拟 ERP | 210 个 SKU、6,000 张订单、7,652 条明细 | 全部带 `is_simulated=true` 与固定随机种子 |
| 海外官方商店 | 228 个商品档案、531 个规格 | 2026-09-12 扩充批次，独立存放 |

角色锚点用 30 条显式干员 PV，形成 30 名角色、271 条上线 Campaign 关联。问卷属于便利样本，不代表全部玩家。

## 四条分析主线

**角色需求。** 内容热度、问卷意愿、森空岛攻略浏览与淘宝商业信号各自归一化后动态加权，输出角色需求榜和证据来源数。5 套业务权重下的排名稳定性单独留档，方便看出哪些名次是权重撑起来的。

**商品主数据。** 19 项字段规范约束角色、品类、价格、授权与履约信息，覆盖 210 个模拟内部 SKU 和 83 个去重公开商品档案。编辑走独立 SQLite 工作层，不回写原始采集文件，识别出 75 条待复核商品。

**经营诊断。** 模拟订单与 90 天库存账核对后，给出 ABC-XYZ 分类、GMROI、缺货损失代理、补货建议和品类售后 Pareto；7 类渠道按支付率、客单价、退款率与毛利代理对比。所有金额都在模拟口径内解释。

**试点闭环。** 候选审批、内容预热、意向登记、供应商比价、订单、履约、售后与购后评价八类业务表只接受 `is_simulated=false` 的记录，未达阶段门禁时报告明确标记为 `blocked`，不预填曝光或订单结果。

## 主要产物

- `data/processed/`：角色热度矩阵、内容×商业矩阵、问卷汇总、SKU 时序与主档质量表
- `data/survey/`：243 份去标识化问卷主表，以及角色排序与价格观测明细
- `data/simulated/`：200 份可复现的模拟画像答卷，与真实答卷严格隔离
- `reports/generated/`：分析报告、经营报告、商品主档报告与两个可筛选工作簿
- `reports/generated/operations.db`：可直接执行分析 SQL 的 SQLite 库
- `reports/figures/`：核心可视化
- `output/pdf/`：打印版问卷
- `web/pilot/`：匿名专项问卷、商品关注埋点与本机运营控制台

字段定义见 [数据字典](docs/data_dictionary.md)，方法口径见 [方法与口径](docs/methodology.md)，平台治理与演示步骤见 [平台使用指南](docs/platform_guide.md)。

## 口径与边界

- **真实数据**：B站与微博官号的公开内容聚合互动指标，不采集评论正文和个人信息。
- **生态数据**：小红书品牌榜快照与森空岛公开搜索聚合值，只代表采集时点的公开视图。
- **商业快照**：淘宝登录后公开展示的自然搜索结果，只保留商品 ID、标题、价格、公开收货人数下界、排名与服务标签。只有明确标注官方或授权的商品进入核心商业指标。
- **人工规则**：品类、生产难度、直播适配度等判断由项目维护者记录并保留来源。
- **用户调研**：243 份匿名回收经批次所有者确认为真实，但属于便利抽样。原始导出缺少提交时间与填写时长，系统不做伪造补全。
- **模拟 ERP**：订单、库存、采购、售后与财务数据用于展示分析方法，不得表述为企业经营业绩。
- **真实试点**：只接受实际记录，达不到门禁就标 `blocked`。
- 互动量是关注度的代理变量，不等同于销量或购买意愿。

## 目录结构

```text
src/arknights_merch_analytics/   分析、采集、报表与平台 API
scripts/                         流水线、构建、采集、导入与导出入口
sql/                             业务视图与分析查询（经营、商品、试点、决策）
config/                          来源、问卷、渠道与情景参数
frontend/                        Vue 3 + Vite 工作台
web/pilot/                       问卷门户与试点控制台静态页
docs/                            方法、口径、协议与运行手册
tests/                           pytest 用例
reports/                         生成的报告、图表与数据库
```

## 采集与合规

采集器只访问公开聚合数据，默认限速并缓存结果，遇到风控或验证码立即停止，不尝试绕过。小红书开放平台不提供任意账号笔记的读取能力，改用 `data/manual/xiaohongshu_operator_posts_template.csv` 人工导入；淘宝不提供免授权的大规模抓取通道，只保存人工核验或当前浏览器可见的低频快照，并提供 `scripts/import_taobao_snapshot.py` 做可追溯导入。请遵守各数据源的服务条款、robots 约束和访问频率限制。

## 测试与 CI

```powershell
.\.venv\Scripts\python.exe -m pytest
```

当前 149 项测试通过，语句覆盖率 79.82%，覆盖规则校验、版本冲突、同口径导出和经营简报的证据边界。GitHub Actions 跑前端构建、pytest 覆盖率与一次 `--use-fixture` 流水线（`.github/workflows/ci.yml`）。

## 部署

`compose.yaml` 与 `deploy/` 提供 Nginx、Redis、Prometheus 与平台服务的容器编排，面向本地或单机演示。Redis 用于查询缓存，Prometheus 暴露 `/metrics`。这些属于配套配置，项目未接入真实交易后台。

## License

MIT

# Arknights Analytics

## 《明日方舟》IP周边选品与商品运营分析平台

使用 B站、微博、小红书与淘宝公开数据构建“内容热度—商业信号—商品策略”矩阵，结合243份匿名用户问卷验证角色、品类、价格与渠道偏好；在模拟 ERP 经营分析之外，新增真实商业试点数据契约，以候选审批、内容预热、意向登记、供应商比价、订单、履约、售后和购后评价形成可审计的商品运营链路。

## 项目边界

- **真实数据**：B站与微博官号公开内容的聚合互动指标，不采集评论正文或用户个人信息。
- **生态数据**：小红书公开品牌榜快照用于衡量 IP 在平台中的整体种草生态，不冒充角色级官号数据；森空岛攻略站使用公开搜索结果中的浏览、收藏、点赞与评论聚合值，不打开文章、不触发浏览计数写入。
- **商业快照**：淘宝登录后公开展示的自然搜索结果，仅记录商品 ID、标题、价格、公开收货人数下界、排名和服务标签，不采集买家信息；只有明确标注官方/授权的商品进入核心商业指标，同人及未标明商品仅用于质量审计。
- **人工数据**：商品品类、生产难度和直播适配度等运营规则，由项目维护者记录并保留来源。
- **用户调研**：243份匿名回收答卷，经项目维护者确认属于真实回收；源TXT标题误标为模拟数据。原始导出不包含提交时间和填写时长，系统不会伪造补全，结论仅代表本次便利样本。
- **模拟 ERP**：订单、库存、采购、售后和财务数据仅用于展示经营分析方法，所有业务表保留 `is_simulated=true` 与固定随机种子。
- **真实商业试点**：试点表只接受 `is_simulated=false` 的实际记录；当前不预填曝光、供应商或订单结果，未达到阶段门禁时报告明确标记为 `blocked`。
- 互动量是角色关注度的代理变量，不等同于真实销量或购买意愿。

仓库内置 549 条通过IP实体校验的B站官号历史内容、100 条微博近期官号公开内容、4 期小红书品牌生态快照、首批 84 条淘宝公开商品快照，以及面向60名角色采集的森空岛攻略站公开搜索快照。B站内容覆盖 2019—2026 年并拆分为 8 类，使用30条显式干员PV作为角色锚点，形成30名干员、271条上线Campaign关联；共享活动流量与角色直接内容分层保存。微博仅对近期明确命中的角色形成交叉验证，小红书角色级字段保留为缺失，淘宝首批横截面只作为商业验证样本，禁止把公开收货人数下界写成精确销量。

## 分析链路

```text
B站官号角色内容 ----> Reach / Momentum / Engagement / Intent
微博官号近期内容 ----> 角色实体识别 / 跨平台一致性 / Confidence
森空岛攻略搜索 ------> 角色攻略浏览 / 收藏 / 评论 / 深度兴趣
小红书品牌生态 ------> 平台校准，不直接参与角色排序
淘宝销量页快照 ------> 商品相关性 / 价格带 / 供给 / 销量代理
                               |
                               v
                    内容×商业矩阵 -> 候选池 -> 内容预热 -> 意向验证
                                           |              |
                                           v              v
                                      模拟 ERP分析    供应商 -> 订单 -> 履约 -> 复盘
```

## 技术栈

`Python / Pandas / NumPy / SQL / SQLite / Excel / Matplotlib / pytest / Requests / BeautifulSoup`

其中 ERP 数据处理覆盖 `SKU Master、Order Header、Order Line、Inventory Snapshot、Purchase Order、After-sales、Financial Summary` 七类业务表；使用 `JOIN、CTE、Window Function、CASE WHEN、Conditional Aggregation、Composite Index、EXPLAIN QUERY PLAN` 完成经营对账与决策查询。

真实试点层覆盖 `Candidate Decision、Campaign、Intent Lead、Supplier Quote、Order、Fulfillment Event、After-sales、Review` 八类业务表，并通过授权校验、匿名化、金额对账、跨表引用和状态门禁阻止不完整数据进入经营结论。

## 快速开始

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\run_pipeline.py
.\.venv\Scripts\python.exe scripts\build_erp_operations.py
.\.venv\Scripts\python.exe scripts\collect_skland_strategy.py
.\.venv\Scripts\python.exe scripts\build_operational_analytics.py
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts\build_commercial_pilot.py
```

启动真实商业试点门户：

```powershell
.\.venv\Scripts\python.exe scripts\run_pilot_portal.py
```

- 用户调研：`http://127.0.0.1:8765/`
- 本机运营控制台：`http://127.0.0.1:8765/admin`
- 调研链接可追加`?source=bilibili`、`?source=weibo`等渠道参数。
- 匿名意向和供应商报价先保存在被Git忽略的`pilot_capture.db`，避免未经同意的逐条调研数据进入公开仓库。

完成一轮采集后，一键校验、导出并刷新商业试点报告：

```powershell
.\.venv\Scripts\python.exe scripts\export_pilot_capture.py
```

每日采集结束可先制作经过完整性校验的本地备份：

```powershell
.\.venv\Scripts\python.exe scripts\backup_pilot_capture.py
```

`--use-fixture` 仅用于测试完整链路。更新公开数据时请控制请求频率；若平台返回风控，采集器停止并保留旧快照：

```powershell
.\.venv\Scripts\python.exe scripts\collect_multiplatform.py
.\.venv\Scripts\python.exe scripts\run_pipeline.py
```

首次建立或增量扩展 B站官号历史库时，可使用低频 related 图采集器；出现 412/429 时程序停止且不覆盖旧数据：

```powershell
.\.venv\Scripts\python.exe scripts\collect_bilibili_archive.py --max-videos 800 --max-requests 500 --interval 0.7
```

后续复采同一批淘宝 SKU 时，可填写模板并导入新的日期快照：

```powershell
.\.venv\Scripts\python.exe scripts\import_taobao_snapshot.py data\manual\taobao_snapshot_template.csv `
  --query "明日方舟 新约能天使 周边" --target-operator "新约能天使"
.\.venv\Scripts\python.exe scripts\run_pipeline.py
```

也可以直接从固定商品注册表导出到期复采队列：

```powershell
.\.venv\Scripts\python.exe scripts\export_sku_recapture_queue.py --operator 新约能天使 --limit 30
```

真实匿名问卷导出后，先执行质量校验和去标识化导入，再刷新流水线：

```powershell
.\.venv\Scripts\python.exe scripts\import_survey_responses.py path\to\survey_export.csv
.\.venv\Scripts\python.exe scripts\run_pipeline.py
```

本项目当前243份匿名答卷来自文本批次，可使用专用解析器复现三表拆分和汇总分析：

```powershell
.\.venv\Scripts\python.exe scripts\import_questionnaire_text.py path\to\明日方舟问卷_243份答案.txt
.\.venv\Scripts\python.exe scripts\build_erp_operations.py
```

若需要在正式投放前验证问卷字段、分群和分析代码，可生成200份以18～22岁大学生为主的模拟画像答卷：

```powershell
.\.venv\Scripts\python.exe scripts\simulate_survey_responses.py
```

模拟答卷与真实答卷严格隔离，固定保存在 `data/simulated/`，并带有
`is_simulated=true`、`data_type=synthetic_persona` 和 `simulation_seed` 标记；其统计结果只能用于演示分析方法，不能描述为真实市场调研结论。

项目已提供可直接部署到问卷平台的25题衍生品用户调研、三阶段样本方案和机器可读配置：

- `docs/derivative_merch_user_questionnaire.md`
- `config/survey_questionnaire.json`
- `data/manual/survey_template.csv`

只需要基于现有 SQLite 数据库刷新 SQL 运营分析时，可运行：

```powershell
.\.venv\Scripts\python.exe scripts\run_sql_analysis.py
```

刷新“角色需求—品类价格—ERP经营诊断”三条主分析链路：

```powershell
.\.venv\Scripts\python.exe scripts\collect_skland_strategy.py
.\.venv\Scripts\python.exe scripts\build_erp_operations.py
.\.venv\Scripts\python.exe scripts\build_operational_analytics.py
```

森空岛采集器每个角色只读取攻略站公开搜索的热度榜与时间榜Top 20，不调用文章浏览写入接口；输出只代表当前搜索快照，并非全站总浏览量。

## 主要输出

- `data/processed/character_heat_matrix.csv`：角色跨平台热度及多维特征
- `data/processed/bilibili_official_archive.csv`：2019—2026 年B站官号历史内容、分类及互动指标
- `data/processed/bilibili_operator_campaign_content.csv`：角色直接内容与前后14天Campaign窗口归因
- `data/processed/bilibili_operator_campaign_summary.csv`：30名角色的Campaign内容深度与加权曝光
- `data/processed/bilibili_content_type_summary.csv`：8类官号内容的供给和表现结构
- `data/processed/bilibili_yearly_summary.csv`：年度内容数量、类型与互动趋势
- `data/processed/official_content_scores.csv`：官号内容级评分与角色归因
- `data/processed/platform_ecosystem.csv`：小红书品牌生态快照
- `data/processed/taobao_public_snapshots.csv`：淘宝公开商品字段及质量标签
- `data/processed/taobao_role_signals.csv`：全 IP 自然销量页的角色商业信号
- `data/processed/content_commerce_matrix.csv`：内容热度 × 商业热度及验证优先级
- `data/public/skland_strategy_operator_search_snapshot.csv`：森空岛攻略站60名角色的公开搜索结果快照
- `data/processed/skland_operator_summary.csv`：清洗异格同名和单字误匹配后的角色攻略浏览与互动汇总
- `data/processed/operator_demand_fusion.csv`：内容、真实问卷、森空岛与淘宝信号的动态加权角色榜
- `data/processed/operator_rank_sensitivity.csv`：5套业务权重下的角色排名稳定性
- `data/processed/category_price_architecture.csv`：七类正版周边的问卷P25/P50/P75价格梯度与市场校准
- `data/processed/operator_category_portfolio.csv`：角色×品类组合评分、样本量与下一步动作
- `data/processed/taobao_target_query_qa.csv`：定向搜索相关率、价格带和集中度
- `data/processed/sku_tracking_registry.csv`：固定商品 ID、基线值和下一次复采日期
- `data/processed/sku_timeseries_metrics.csv`：价格、销量代理、排名变化和时间序列证据等级
- `data/processed/survey_response_audit.csv`：匿名问卷有效性及排除原因
- `data/processed/survey_operator_category_summary.csv`：角色 × 品类购买意愿和价格接受度
- `data/processed/survey_segment_summary.csv`：核心购买者、偶发购买者、潜在购买者与观察者分群
- `data/processed/survey_barrier_summary.csv`：购买阻力人数与占比
- `data/processed/survey_price_summary.csv`：方向性价格区间及可接受价格四分位
- `data/survey/anonymous_responses_243.csv`：243份去标识化问卷受访者主表
- `data/survey/anonymous_operator_rankings_243.csv`：729条角色Top-3偏好排序
- `data/survey/anonymous_category_prices_243.csv`：1,701条全品类价格带观测
- `data/processed/survey_243_*_summary.csv`：样本、年龄、分群、角色、品类、渠道、阻力、属性和价格汇总
- `data/simulated/survey_responses_200.csv`：200份可复现的模拟用户画像答卷，不属于真实调研数据
- `data/processed/simulated_survey_*_summary.csv`：模拟答卷的年龄、分群、品类、渠道、阻力和价格汇总
- `data/processed/selection_case_evidence.csv`：选品案例的六层证据门禁
- `data/processed/pilot_candidate_shortlist.csv`：由公开聚合数据与真实匿名问卷形成的角色×品类候选池
- `data/processed/pilot_readiness.csv`：内容、意向、供应、订单、履约与复盘阶段门禁
- `data/processed/pilot_supplier_public_leads.csv`：公开零售商品形成的寻源线索，不等同于供应商报价
- `data/processed/pilot_supplier_sourcing_gap.csv`：每个已批方案距3家授权供应商报价门槛的缺口
- `data/manual/commercial_pilot/`：八张真实商业试点空白录入模板，不含虚构经营结果
- `data/processed/operator_heat.csv`：兼容旧分析链路的角色热度表
- `data/processed/erp_mock.csv`：明确标注的模拟 ERP 明细
- `data/processed/erp_sku_master.csv`：210个模拟SKU主数据与补货参数
- `data/processed/erp_order_headers.csv` / `erp_order_lines.csv`：6,000张订单与7,652条订单明细
- `data/processed/erp_inventory_daily.csv`：90天、18,900条库存日快照
- `data/processed/erp_purchase_orders.csv`：采购、到货、缺交与在途状态
- `data/processed/erp_after_sales.csv`：退款、退货、换货及处理时长
- `data/processed/erp_financial_summary.csv`：SKU收入、成本、毛利、退货率、售罄率和库存周转
- `data/processed/erp_sku_diagnostics.csv`：SKU级ABC-XYZ、GMROI、缺货损失代理和经营动作
- `data/processed/erp_replenishment_plan.csv`：基于28日需求、交期和安全库存的补货建议
- `data/processed/erp_after_sales_pareto.csv`：品类×售后原因Pareto与退款金额
- `data/processed/erp_channel_profitability.csv`：渠道支付率、客单价、退款率和毛利代理
- `data/processed/erp_category_diagnostics.csv`：七品类收入、毛利、周转、缺货和退货联合诊断
- `data/processed/erp_daily_kpis.csv`：完整订单周期的订单、收入、满足率和7日滚动趋势
- `data/processed/sku_recommendations.csv`：SKU 选品评分
- `reports/generated/analysis_report.md`：自动生成的分析报告
- `reports/generated/bilibili_archive_report.md`：B站官号历史内容和角色Campaign分析
- `reports/generated/taobao_commerce_report.md`：淘宝商业化运营分析报告
- `reports/generated/sku_timeseries_report.md`：固定 SKU 周期复采状态与证据等级
- `reports/generated/user_research_report.md`：真实匿名用户调研质量与结果
- `reports/generated/erp_operations_report.md`：模拟ERP经营指标、渠道、补货、滞销和售后报告
- `reports/generated/operational_analytics_report.md`：角色需求、价格架构与ERP经营诊断总报告
- `reports/generated/operational_analytics.xlsx`：上述三条主线的可筛选工作簿
- `reports/generated/simulated_user_research_report.md`：明确标注为非真实调研的模拟画像分析报告
- `reports/generated/selection_case_study.md`：新约能天使可验证选品案例
- `reports/generated/commercial_pilot_report.md`：真实商业试点候选与准备度报告
- `reports/generated/supplier_sourcing_gap_report.md`：公开寻源证据与真实供应商报价缺口
- `docs/pilot_new_exusiai_validation_plan.md`：新约能天使双商品方案、30人专项意向与三家供应商询价计划
- `docs/supplier_rfq_template.md`：三家供应商授权核验、询价字段与联系话术
- `docs/commercial_pilot_runbook.md`：真实投放、备份、询价、门禁和运营复盘执行手册
- `web/pilot/`：匿名专项问卷、商品关注埋点和本机运营控制台
- `reports/generated/sql_analysis_report.md`：由 SQLite 视图与分析 SQL 自动生成的运营报告
- `reports/generated/operations_dashboard.xlsx`：运营结果工作簿
- `reports/generated/operations.db`：可直接执行分析 SQL 的 SQLite 数据库
- `reports/figures/`：核心可视化

新增 `sql/operational_analytics_views.sql` 与 `sql/operational_analysis_queries.sql`，覆盖多源角色需求、价格梯度、ABC-XYZ、补货预算、售后Pareto、品类健康度和7日滚动经营指标；字段定义见 `docs/data_dictionary.md`。

面试准备、岗位能力地图、项目拷打题和专业化迭代路线见
`docs/commercial_operations_interview_guide.md`。

固定 SKU、真实用户调研和选品案例的执行规范分别见
`docs/fixed_sku_tracking_protocol.md`、`docs/user_research_protocol.md` 和
`docs/selection_case_protocol.md`。

真实内容预热、供应商比价、订单履约与复盘的执行规范见
`docs/commercial_pilot_protocol.md`。

## 数据合规

采集器仅访问公开聚合数据，默认限速并缓存结果。请遵守数据源的服务条款、robots 约束和访问频率限制。若接口返回风控或验证码，程序会停止，不尝试绕过。小红书开放平台当前不提供读取任意账号笔记的公开能力，因此仓库提供 `data/manual/xiaohongshu_operator_posts_template.csv`。淘宝不提供免授权的大规模商品抓取通道，本项目仅保存人工核验或当前浏览器中可见的低频公开快照，并提供 `data/manual/taobao_snapshot_template.csv` 和 `scripts/import_taobao_snapshot.py` 进行可追溯导入。

## License

MIT

# Arknights IP Character Heat-Driven Merchandising Analytics

《明日方舟》IP 角色热度驱动的周边选品分析：使用 B站、微博、小红书与淘宝公开数据构建“内容热度—商业信号—商品策略”矩阵，再结合人工商品目录、用户调研模板与明确标注的模拟 ERP 数据，输出角色榜单、价格带、供需缺口、备货和直播排品建议。

## 项目边界

- **真实数据**：B站与微博官号公开内容的聚合互动指标，不采集评论正文或用户个人信息。
- **生态数据**：小红书公开品牌榜快照用于衡量 IP 在平台中的整体种草生态，不冒充角色级官号数据。
- **商业快照**：淘宝登录后公开展示的自然搜索结果，仅记录商品 ID、标题、价格、公开收货人数下界、排名和服务标签，不采集买家信息。
- **人工数据**：商品品类、生产难度和直播适配度等运营规则，由项目维护者记录并保留来源。
- **模拟数据**：订单、库存、销售和退货数据仅用于展示分析方法，字段中始终保留 `is_simulated=true`。
- 互动量是角色关注度的代理变量，不等同于真实销量或购买意愿。

仓库内置 30 条 B站官号角色内容、100 条微博近期官号公开内容、4 期小红书品牌生态快照和首批 84 条淘宝公开商品快照。角色级总榜覆盖 30 名干员；微博仅对近期明确命中的角色形成交叉验证，小红书角色级字段保留为缺失，淘宝首批横截面只作为商业验证样本，禁止把公开收货人数下界写成精确销量。

## 分析链路

```text
B站官号角色内容 ----> Reach / Momentum / Engagement / Intent
微博官号近期内容 ----> 角色实体识别 / 跨平台一致性 / Confidence
小红书品牌生态 ------> 平台校准，不直接参与角色排序
淘宝销量页快照 ------> 商品相关性 / 价格带 / 供给 / 销量代理
                               |
                               v
                    内容×商业矩阵 -> 模拟 ERP -> SKU 选品建议
```

## 技术栈

`Python / Pandas / NumPy / Requests / BeautifulSoup / Matplotlib / SQLite / pytest / Excel`

## 快速开始

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\run_pipeline.py
.\.venv\Scripts\python.exe -m pytest
```

`--use-fixture` 仅用于测试完整链路。更新公开数据时请控制请求频率；若平台返回风控，采集器停止并保留旧快照：

```powershell
.\.venv\Scripts\python.exe scripts\collect_multiplatform.py
.\.venv\Scripts\python.exe scripts\run_pipeline.py
```

后续复采同一批淘宝 SKU 时，可填写模板并导入新的日期快照：

```powershell
.\.venv\Scripts\python.exe scripts\import_taobao_snapshot.py data\manual\taobao_snapshot_template.csv `
  --query "明日方舟 新约能天使 周边" --target-operator "新约能天使"
.\.venv\Scripts\python.exe scripts\run_pipeline.py
```

只需要基于现有 SQLite 数据库刷新 SQL 运营分析时，可运行：

```powershell
.\.venv\Scripts\python.exe scripts\run_sql_analysis.py
```

## 主要输出

- `data/processed/character_heat_matrix.csv`：角色跨平台热度及多维特征
- `data/processed/official_content_scores.csv`：官号内容级评分与角色归因
- `data/processed/platform_ecosystem.csv`：小红书品牌生态快照
- `data/processed/taobao_public_snapshots.csv`：淘宝公开商品字段及质量标签
- `data/processed/taobao_role_signals.csv`：全 IP 自然销量页的角色商业信号
- `data/processed/content_commerce_matrix.csv`：内容热度 × 商业热度及验证优先级
- `data/processed/taobao_target_query_qa.csv`：定向搜索相关率、价格带和集中度
- `data/processed/operator_heat.csv`：兼容旧分析链路的角色热度表
- `data/processed/erp_mock.csv`：明确标注的模拟 ERP 明细
- `data/processed/sku_recommendations.csv`：SKU 选品评分
- `reports/generated/analysis_report.md`：自动生成的分析报告
- `reports/generated/taobao_commerce_report.md`：淘宝商业化运营分析报告
- `reports/generated/sql_analysis_report.md`：由 SQLite 视图与分析 SQL 自动生成的运营报告
- `reports/generated/operations_dashboard.xlsx`：运营结果工作簿
- `reports/generated/operations.db`：可直接执行分析 SQL 的 SQLite 数据库
- `reports/figures/`：核心可视化

SQL 资产包括 `sql/business_views.sql` 中的 5 个可复用业务视图，以及
`sql/analysis_queries.sql` 中覆盖角色决策、价格带、品类漏斗、市场集中度、库存风险和数据质量审计的 20 组查询；字段定义见 `docs/data_dictionary.md`。

面试准备、岗位能力地图、项目拷打题和专业化迭代路线见
`docs/commercial_operations_interview_guide.md`。

## 数据合规

采集器仅访问公开聚合数据，默认限速并缓存结果。请遵守数据源的服务条款、robots 约束和访问频率限制。若接口返回风控或验证码，程序会停止，不尝试绕过。小红书开放平台当前不提供读取任意账号笔记的公开能力，因此仓库提供 `data/manual/xiaohongshu_operator_posts_template.csv`。淘宝不提供免授权的大规模商品抓取通道，本项目仅保存人工核验或当前浏览器中可见的低频公开快照，并提供 `data/manual/taobao_snapshot_template.csv` 和 `scripts/import_taobao_snapshot.py` 进行可追溯导入。

## License

MIT

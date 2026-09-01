# Arknights IP Character Heat-Driven Merchandising Analytics

《明日方舟》IP 角色热度驱动的周边选品分析：使用 B站、微博与小红书公开数据构建多层热度矩阵，再结合人工商品目录、用户调研模板与明确标注的模拟 ERP 数据，输出角色榜单、选品、价格带、备货和直播排品建议。

## 项目边界

- **真实数据**：B站与微博官号公开内容的聚合互动指标，不采集评论正文或用户个人信息。
- **生态数据**：小红书公开品牌榜快照用于衡量 IP 在平台中的整体种草生态，不冒充角色级官号数据。
- **人工数据**：商品品类、生产难度和直播适配度等运营规则，由项目维护者记录并保留来源。
- **模拟数据**：订单、库存、销售和退货数据仅用于展示分析方法，字段中始终保留 `is_simulated=true`。
- 互动量是角色关注度的代理变量，不等同于真实销量或购买意愿。

仓库内置 30 条 B站官号角色内容、100 条微博近期官号公开内容和 4 期小红书品牌生态快照。角色级总榜覆盖 30 名干员；微博仅对近期明确命中的角色形成交叉验证，小红书角色级字段保留为缺失，禁止用品牌总量伪造角色排序。

## 分析链路

```text
B站官号角色内容 ----> Reach / Momentum / Engagement / Intent
微博官号近期内容 ----> 角色实体识别 / 跨平台一致性 / Confidence
小红书品牌生态 ------> 平台校准，不直接参与角色排序
                               |
                               v
                    角色热度矩阵 -> 模拟 ERP -> SKU 选品建议
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

## 主要输出

- `data/processed/character_heat_matrix.csv`：角色跨平台热度及多维特征
- `data/processed/official_content_scores.csv`：官号内容级评分与角色归因
- `data/processed/platform_ecosystem.csv`：小红书品牌生态快照
- `data/processed/operator_heat.csv`：兼容旧分析链路的角色热度表
- `data/processed/erp_mock.csv`：明确标注的模拟 ERP 明细
- `data/processed/sku_recommendations.csv`：SKU 选品评分
- `reports/generated/analysis_report.md`：自动生成的分析报告
- `reports/generated/operations_dashboard.xlsx`：运营结果工作簿
- `reports/generated/operations.db`：可直接执行分析 SQL 的 SQLite 数据库
- `reports/figures/`：核心可视化

SQL 示例位于 `sql/analysis_queries.sql`，字段定义见 `docs/data_dictionary.md`。

## 数据合规

采集器仅访问公开聚合数据，默认限速并缓存结果。请遵守数据源的服务条款、robots 约束和访问频率限制。若接口返回风控或验证码，程序会停止，不尝试绕过。小红书开放平台当前不提供读取任意账号笔记的公开能力，因此仓库提供 `data/manual/xiaohongshu_operator_posts_template.csv`，只接受人工核验的公开官号快照。

## License

MIT

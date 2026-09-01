# Arknights IP Character Heat-Driven Merchandising Analytics

《明日方舟》IP 角色热度驱动的周边选品分析：使用公开内容互动数据构建角色热度指标，再结合人工商品目录、用户调研模板与明确标注的模拟 ERP 数据，输出选品、价格带、备货和直播排品建议。

## 项目边界

- **真实数据**：公开发布内容及其聚合互动指标，不采集评论正文或用户个人信息。
- **人工数据**：商品品类、生产难度和直播适配度等运营规则，由项目维护者记录并保留来源。
- **模拟数据**：订单、库存、销售和退货数据仅用于展示分析方法，字段中始终保留 `is_simulated=true`。
- 互动量是角色关注度的代理变量，不等同于真实销量或购买意愿。

仓库内置 `data/public/bilibili_official_pv_snapshot.json`，包含10条官方限定干员PV公开展示值快照。平台以“万”为单位展示的指标已转换为整数，因此其精度标记为 `display_rounded`。

## 分析链路

```text
官方内容数据 -> 角色识别 -> 热度与互动质量 -> 商品品类组合
             -> 模拟 ERP -> SKU 经营指标 -> 选品与直播排品
```

## 技术栈

`Python / Pandas / NumPy / Requests / Matplotlib / SQLite / pytest / Excel`

## 快速开始

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\run_pipeline.py
.\.venv\Scripts\python.exe -m pytest
```

`--use-fixture` 仅用于测试完整链路。更新公开数据时请控制请求频率：

```powershell
.\.venv\Scripts\python.exe scripts\collect_bilibili.py
.\.venv\Scripts\python.exe scripts\run_pipeline.py
```

## 主要输出

- `data/processed/operator_heat.csv`：角色热度和互动质量指标
- `data/processed/erp_mock.csv`：明确标注的模拟 ERP 明细
- `data/processed/sku_recommendations.csv`：SKU 选品评分
- `reports/generated/analysis_report.md`：自动生成的分析报告
- `reports/generated/operations_dashboard.xlsx`：运营结果工作簿
- `reports/generated/operations.db`：可直接执行分析 SQL 的 SQLite 数据库
- `reports/figures/`：核心可视化

SQL 示例位于 `sql/analysis_queries.sql`，字段定义见 `docs/data_dictionary.md`。

## 数据合规

采集器仅访问公开聚合数据，默认限速并缓存结果。请遵守数据源的服务条款、robots 约束和访问频率限制。若接口返回风控或验证码，程序会停止，不尝试绕过。

## License

MIT

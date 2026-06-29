# NL2SQL 评测模块

本目录用于独立评测当前 NL2SQL 项目的数据查询正确性，不修改生产链路代码。

## 评测目标

- 验证自然语言问题能否生成可执行 SQL。
- 对比生成 SQL 与标准 SQL 的执行结果是否一致。
- 检查生成 SQL 是否命中预期表、字段、过滤条件、聚合与分组排序意图。
- 输出可复盘的 JSON 与 Markdown 报告，便于定位失败样本。

## 目录结构

- `eval_cases.json`：默认评测集。
- `evaluate_nl2sql.py`：命令行入口。
- `evaluator/`：评测实现模块。

## 运行方式

在 `data-agent-pro-backend` 目录下运行：

```bash
python -m test.evaluate_nl2sql --cases test/eval_cases.json --report-dir test/reports
```

如需只跑前 N 条：

```bash
python -m test.evaluate_nl2sql --limit 3
```

## 前置条件

运行前请确保：

1. MySQL、Qdrant、Elasticsearch、Embedding 服务已启动。
2. 已执行元数据构建脚本，确保字段、指标、字段值索引已写入 Qdrant/ES。
3. `conf/app_config.yaml` 中的服务地址可访问。

## 核心指标

- `syntax_valid_rate`：生成 SQL 可被 `EXPLAIN` 校验通过的比例。
- `execution_success_rate`：生成 SQL 可成功执行的比例。
- `execution_accuracy`：生成 SQL 与标准 SQL 执行结果一致的比例。
- `table_match_rate`：生成 SQL 是否包含评测集要求的表。
- `column_match_rate`：生成 SQL 是否包含评测集要求的字段。
- `condition_match_rate`：生成 SQL 是否包含关键过滤条件。
- `avg_latency_ms` / `p95_latency_ms`：端到端生成耗时。

## 评测集设计

默认评测集覆盖：

- 单表聚合：订单数、销售额。
- 维度过滤：大区、省份、品类、品牌、会员等级、性别。
- 多表关联：事实表与地区、商品、客户、日期维表关联。
- 分组排序：按地区、品类、品牌、月份统计与 Top-N。
- 时间条件：1 月、2 月、Q1、日期范围。

每条样本以标准 SQL 的执行结果作为答案，避免手工维护结果值。
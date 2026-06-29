# DataSearch

DataSearch 是一个面向数据分析场景的 NL2SQL 项目，支持自然语言查询数据库，并通过“召回 - 筛选 - 生成 - 校验 - 执行 - 追踪 - 评测”的链路完成一次完整的数据问答。

## 项目结构

- `data-agent-pro-backend/`：后端服务，基于 FastAPI、LangGraph、MySQL、Elasticsearch、Qdrant 和 SQLGlot。
- `data-agent-pro-frontend/`：前端界面，基于 Vue 3 + Vite，用于输入问题、查看执行步骤和查询结果。
- `docs/`：项目说明文档和面试整理内容。

## 核心能力

- 自然语言转 SQL：根据用户问题召回字段、指标和字段值，再生成可执行 SQL。
- SQL 安全校验：在执行前做 AST 级安全检查，拦截危险语句和越权访问。
- 纠错闭环：SQL 生成失败后进入有限次数的自动纠错流程。
- 链路追踪：记录每次请求的召回、校验、执行和耗时信息，便于排查问题。
- 数据飞轮：把失败样例沉淀为可回灌的评测资产，持续优化系统。
- 评测体系：提供多层评测，验证召回、筛选、SQL 和结果质量。

## 本地运行

### 后端

1. 进入后端目录：`cd data-agent-pro-backend`
2. 安装依赖：使用项目对应的 Python 环境安装 `pyproject.toml` 中的依赖
3. 启动服务：`python -m fastapi dev`

### 前端

1. 进入前端目录：`cd data-agent-pro-frontend`
2. 安装依赖：`npm install`
3. 启动开发服务：`npm run dev`

## 使用说明

1. 启动后端和前端服务。
2. 在前端输入自然语言问题，例如“查询上个月的销售额”。
3. 系统会返回查询步骤、SQL 执行结果或友好的提示信息。

# 知枢 · 企业智能知识库

> **zhishu-kb-platform** ｜ 知枢企业智能知识库（简称「知枢」）
> 以**知识治理中枢**为核心差异化的企业级 AI 智能知识库平台

## 为什么叫「知枢」

「枢」即中枢。知枢的差异化不在「又一个 RAG 问答」，而在把知识库做成企业知识的**治理中枢**：

- **知识有效期**——过期知识自动退休，AI 不会拿旧制度回答新问题
- **旧稿识别归并**——新稿入库自动识别并归并旧版，回答默认只用现行稿
- **密级过滤**——L1~L4 四级密级在**检索层**过滤，无权用户对密级文档「不存在」
- **审计与动态水印**——管理操作全量审计，涉密页面动态水印

## 技术栈（全部开源/公共组件，清洁室自研）

| 层 | 选型 |
|----|------|
| 前端 | Vue 3 + TypeScript + Vite + Ant Design Vue 4 + Pinia + ECharts |
| 后端 | FastAPI（模块化单体）+ Pydantic v2 + SQLAlchemy 2.0 + Celery |
| 数据 | PostgreSQL 16（业务 + pgvector 向量 + zhparser 中文全文同库）+ Valkey |
| AI 服务 | llama.cpp server（Qwen3-4B / 30B-A3B）+ TEI（Qwen3-Embedding/Reranker）+ Langfuse |
| 解析 | Docling（默认）/ MinerU（复杂版面）/ PaddleOCR（扫描件），按类型路由 |
| 评测 | RAGAS 四指标夜间回归 + 全链路 trace |

许可证纪律：**AGPL 组件零引入**；全部组件为 MIT/Apache/BSD/PostgreSQL 宽松许可；不使用任何第三方闭源产品的源码与 SDK（清洁室独立开发，法律依据见技术方案 §10）。

## 文档

- [docs/开发进度.md](./docs/开发进度.md)——**当前进度与下一步**（随迭代更新）
- [docs/开发快速开始.md](./docs/开发快速开始.md)——一键启动 / 账号 / 冒烟
- [docs/前端约定.md](./docs/前端约定.md)——Vue SFC 顺序（template→script→style/less）与模块拆分
- [docs/知枢企业智能知识库PRD.md](./docs/知枢企业智能知识库PRD.md)——产品需求文档
- [docs/知枢企业智能知识库技术方案.md](./docs/知枢企业智能知识库技术方案.md)——主技术方案
- [docs/知枢企业智能知识库开发计划.md](./docs/知枢企业智能知识库开发计划.md)——标段与任务 WBS
- [docs/知枢企业智能知识库开发排期.md](./docs/知枢企业智能知识库开发排期.md)——日历与签收日
- [docs/知枢技术方案markmap.html](./docs/知枢技术方案markmap.html)——技术方案交互式目录导图

## 当前进度（2026-11-05）

| 里程碑 | 状态 |
|--------|------|
| M0 ~ M2 | **主体完成**（上传→混合检索→SSE 问答引用；JWT / 工作区 / 密级） |
| M3-1 | **~85%**（有效期 + 审计 + 归并 + Hit Test 台；**下一步表格全表注入**） |

详情与缺口见 [docs/开发进度.md](./docs/开发进度.md)。

## 路线图

| 阶段 | 标段 | 内容 | 工期 |
|------|------|------|------|
| Phase 0 | A | POC：Compose 全栈，上传→解析→检索→流式回答→引用闭环（M1） | 1 周 |
| Phase 1 | B | 核心：解析路由、混合检索+RRF+Rerank、SSE 引用、RBAC+密级过滤（M2） | 3~4 周 |
| Phase 2 | C | 治理与评测：有效期/归并/审计水印、RAGAS、Hit Test（M3 正式启用） | 3~4 周 |
| Phase 3 | D | 开放与增强：Open API+限流；图谱/工作流/协同按需（M4） | 按需 |

## 部署形态

面向企业内网（5~50 人），完全离线运行：A 档 6GB 显存单机（≤5 人 POC）→ B 档无 GPU 32GB 服务器（10~30 人主力档）→ C 档 24GB 单卡（30~50 人）。详见技术方案 §7。

## 快速开始（开发 / stub）

详见 [docs/开发快速开始.md](./docs/开发快速开始.md)。

**一键启动（Windows）**：双击根目录 `start.bat`，或执行 `.\scripts\start.ps1`。停止用 `stop.bat`。

- 前端 http://127.0.0.1:5173 · API http://127.0.0.1:8000  
- 登录 `admin` / `admin123`（L4）或 `member` / `member123`（L2）

默认 `ZHISHU_DEV_STUB=1` + `USE_SQLITE=true`：无 Docker/GPU 即可跑通闭环。冒烟：`python scripts/smoke.py`。

## 许可证

本项目以 **MIT License** 发布（见 [LICENSE](./LICENSE)）；第三方组件依各自许可证合规使用。


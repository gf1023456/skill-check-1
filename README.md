# Skill Checker - FastAPI-based LLM-driven Skill Validation Service

一个基于 FastAPI 的 **Skill 验证服务**，通过 LLM 驱动的流水线对上传的 Skill 包进行静态检查、确定性测试、LLM 测试计划执行和 TRACE 评分，最终生成完整的验证报告。

---

## 架构概览

```
┌──────────────────────────────────────────────────────────────┐
│                    FastAPI Application                        │
│                                                              │
│  POST /upload       → 上传 Skill ZIP 包                      │
│  POST /start/{id}   → 异步启动验证流程 (BackgroundTasks)     │
│  GET  /status/{id}  → 查询验证状态                           │
│  GET  /report/{id}  → 获取验证报告                           │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  SkillManager                         │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────┐  │   │
│  │  │Validator  │  │ Executor │  │ LlmAgent │  │Core  │  │   │
│  │  │(静态检查)  │  │(进程/HTTP)│  │(LLM 客户端)│  │Skill │  │   │
│  │  └──────────┘  └──────────┘  └──────────┘  │Checker│  │   │
│  │                                             └──────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Storage: /tmp/skill_checker_storage/                        │
│    ├── {skill_id}/skill.zip        ← 上传的 ZIP              │
│    ├── work/{skill_id}/            ← 工作目录                │
│    ├── reports/{skill_id}.json     ← 验证报告                │
│    └── status/{skill_id}.json      ← 状态文件                │
└──────────────────────────────────────────────────────────────┘
```

---

## 验证流程

1. **上传** — 接收 Skill ZIP 包，分配唯一 `skill_id`
2. **解压 & 安全检查** — 防止 ZIP 路径穿越攻击
3. **Frontmatter 验证** — 使用 bundled `skill-checker` 脚本验证 `SKILL.md` 的 YAML frontmatter
4. **Manifest 加载** — 自动探测多种 manifest 文件格式（yaml/json/md）
5. **静态检查** — 检查 `name`, `version`, `entrypoint` 等必填字段
6. **进程启动** — 如果 manifest 配置了 `run.command`，启动子进程并等待健康检查
7. **确定性测试** — 执行 manifest 中定义的 HTTP 测试用例
8. **LLM 测试计划** — 调用 LLM 根据 manifest 和 triggers 生成测试计划 JSON
9. **LLM 计划执行** — 执行 LLM 生成的 HTTP action 测试（含安全校验）
10. **Trigger 评估** — LLM 生成 20 个查询（10 正例 + 10 负例），评估 skill 触发准确性
11. **TRACE 评分** — 合并所有结果，生成规范化的 TRACE 报告
12. **结果持久化** — 保存状态和报告 JSON 文件

---

## 快速开始

### 环境要求

- Python 3.11+
- 选择一个 LLM 提供商并配置 API Key

### 安装

```bash
# 克隆仓库
git clone <repo-url>
cd skill-check-1-feature-fastapi-skill-checker

# 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# 安装依赖
pip install -r requirements.txt
```

### 配置

通过环境变量配置。复制以下内容创建 `.env` 文件：

```bash
# LLM 提供商: openai / deepseek / azure / anthropic / local
LLM_PROVIDER=openai
# 模型名称 (默认: gpt-4o-mini)
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-xxxxxxxx

# 可选: DeepSeek
# DEEPSEEK_URL=https://api.deepseek.com/v1/completions
# DEEPSEEK_API_KEY=sk-xxxxxxxx

# 可选: Azure OpenAI
# AZURE_API_BASE=https://xxx.openai.azure.com
# AZURE_API_KEY=xxxxxxxx
# AZURE_DEPLOYMENT=gpt-4o-mini

# 可选: Anthropic
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxx
# ANTHROPIC_URL=https://api.anthropic.com/v1/complete

# 可选: 本地 LLM
# LOCAL_LLM_URL=http://localhost:8080/generate

# 存储目录 (默认: /tmp/skill_checker_storage)
STORAGE_DIR=/tmp/skill_checker_storage

# 安全配置
ALLOW_PRIVATE_NETWORK=false
ALLOWED_HOSTS=api.example.com,api.anthropic.com
```

### 启动

```bash
# 开发模式
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 或直接运行
python main.py
```

服务默认启动在 `http://localhost:8000`，API 文档地址 `http://localhost:8000/docs`。

---

## API 接口

### 1. 上传 Skill

```
POST /skill-checker/upload
Content-Type: multipart/form-data

Body: file=<skill.zip>
```

**响应示例：**
```json
{
  "skill_id": "a1b2c3d4-...",
  "message": "uploaded"
}
```

### 2. 启动验证

```
POST /skill-checker/start/{skill_id}
```

**可选参数：** `?baseline_id=xxx` — 传入基线 skill_id 用于对比

**响应示例：**
```json
{
  "skill_id": "a1b2c3d4-...",
  "status": "started",
  "baseline": null
}
```

### 3. 查询状态

```
GET /skill-checker/status/{skill_id}
```

**响应示例：**
```json
{
  "status": "running"
}
```
状态值：`running` / `done` / `error`

### 4. 获取报告

```
GET /skill-checker/report/{skill_id}
```

**响应包含：**
| 字段 | 说明 |
|------|------|
| `skill` | Skill 名称 |
| `skill_checker` | 完整验证结果（frontmatter、environment、trigger、trace_report） |
| `static` | 静态检查结果 |
| `deterministic_tests` | 确定性测试结果 |
| `llm_plan_raw` | LLM 原始响应 |
| `plan_results` | LLM 测试计划执行结果 |
| `legacy_trace` | 兼容性 TRACE 评分（T/R/A/C/E） |
| `trace` | 规范 TRACE 报告 |

---

## 项目结构

```
├── app/
│   ├── main.py                  # FastAPI 应用入口
│   ├── api/
│   │   └── router.py            # REST API 路由定义
│   ├── core/
│   │   └── config.py            # 配置管理（多 LLM 提供商）
│   ├── schemas/
│   │   └── report.py            # Pydantic 数据模型
│   ├── services/
│   │   ├── skill_manager.py     # 验证流程编排（核心）
│   │   └── core_skill.py        # bundled skill-checker 适配器
│   ├── agent/
│   │   ├── executor.py          # 进程管理 & HTTP 测试执行
│   │   ├── validator.py         # Manifest 静态检查 & TRACE 计算
│   │   └── llm_agent.py         # LLM 客户端（多提供商支持）
│   └── utils/
│       ├── manifest_utils.py    # Manifest 文件加载
│       └── security.py          # 私有网络检测
│
├── skill/
│   └── skill-checker/           # 核心验证技能（bundled）
│       ├── SKILL.md
│       ├── scripts/
│       │   ├── validate.py      # Frontmatter 验证
│       │   └── scoring.py       # TRACE 评分
│       └── references/
│           ├── schemas.md
│           └── prompts/
│               ├── trigger_eval_prompt.md
│               └── improve_desc_prompt.md
│
├── tests/
│   └── test_core_skill.py       # CoreSkillChecker 单元测试
├── main.py                      # 命令行入口
├── requirements.txt             # Python 依赖
├── Dockerfile                   # Docker 构建文件
└── README.md
```

---

## LLM 提供商支持

| 提供商 | 配置方式 | 聊天 API |
|--------|---------|---------|
| OpenAI | `LLM_PROVIDER=openai` + `OPENAI_API_KEY` | 支持 |
| DeepSeek | `LLM_PROVIDER=deepseek` + `DEEPSEEK_URL` + `DEEPSEEK_API_KEY` | 仅 Prompt |
| Azure OpenAI | `LLM_PROVIDER=azure` + `AZURE_API_BASE/KEY/DEPLOYMENT` | 支持 |
| Anthropic | `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` + `ANTHROPIC_URL` | 仅 Prompt |
| Local LLM | `LLM_PROVIDER=local` + `LOCAL_LLM_URL` | 仅 Prompt |

---

## 安全

- **ZIP 路径穿越防护** — 解压时验证所有文件路径，防止 `../` 逃逸
- **私有网络防护** — 默认禁止访问私有 IP 地址（10/172.16/192.168/127/169.254）
- **Host 白名单** — 通过 `ALLOWED_HOSTS` 限制可访问的域名
- **子进程超时** — 所有子进程执行均有超时控制

---

## Docker 部署

```bash
# 构建镜像
docker build -t skill-checker .

# 运行
docker run -d \
  -p 8000:8000 \
  -e LLM_PROVIDER=openai \
  -e OPENAI_API_KEY=sk-xxx \
  -v /path/to/storage:/tmp/skill_checker_storage \
  skill-checker
```

---

## 作为模块嵌入

```python
from fastapi import FastAPI
from app.api.router import router as skill_checker_router

app = FastAPI()
app.include_router(skill_checker_router, prefix="/skill-checker", tags=["skill-checker"])
```

---

## 开发

```bash
# 运行测试
python -m pytest tests/

# 或
python -m unittest tests/test_core_skill.py
```
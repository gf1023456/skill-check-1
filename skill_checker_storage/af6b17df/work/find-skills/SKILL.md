---
name: find-skills
description: Helps users discover and install agent skills when they ask questions like "how do I do X", "find a skill for X", "is there a skill that can...", or express interest in extending capabilities. This skill should be used when the user is looking for functionality that might exist as an installable skill.
agent_created: true
---

# Find Skills

This skill helps you discover and install skills from the open agent skills ecosystem.

## When to Use This Skill

Use this skill when the user:

- Asks "how do I do X" where X might be a common task with an existing skill
- Says "find a skill for X" or "is there a skill for X"
- Asks "can you do X" where X is a specialized capability
- Expresses interest in extending agent capabilities
- Wants to search for tools, templates, or workflows
- Mentions they wish they had help with a specific domain (design, testing, deployment, etc.)

## 内部私库（DADO-Skill-market）

团队维护了一个内部私有 Skill 包仓库（DADO-Skill-market）：统一托管、版本化发布、按角色分发。搜索 Skill 时，**先查内部私库，没有找到再走公开生态**。

### 安装原则（硬性规则）

> **内部私库的 Skill → 必须用 `skillctl` 安装，禁止使用 `npx skills`。**
> **公开生态（skills.sh 等）的 Skill → 走原有的 `npx skills` 逻辑。**

| 来源 | 搜索工具 | 安装工具 |
|------|----------|----------|
| 内部市场 | `skillctl list` | `skillctl install --skill <slug>` |
| 公开生态 skills.sh | `npx skills find` / WebFetch `skills.sh` | `npx skills add <owner/repo@skill>` |

### skillctl 使用参考

**安装 skillctl：**
```bash
# 从项目目录获取
cd /path/to/dado-skills-market
./skillctl

# 或安装到系统 PATH
cp skillctl /usr/local/bin/
chmod +x /usr/local/bin/skillctl

# 验证
skillctl --help
```

**登录：**
```bash
# 交互式登录（推荐）
skillctl login --server <服务地址>

# 一次性传入凭据（适合 CI/CD）
skillctl login --server <服务地址> --username <用户名> --password <密码>
```

> 登录成功后服务器地址保存在 `~/.config/skillctl/credentials.json`，后续命令无需再带 `--server`。

**列出所有 Skill：**
```bash
skillctl list
```

**下载安装 Skill：**
```bash
skillctl install --skill <slug> --version <版本号> --target <目录>
```

## What is the Skills CLI?

The Skills CLI (`npx skills`) is the package manager for the open agent skills ecosystem. Skills are modular packages that extend agent capabilities with specialized knowledge, workflows, and tools.

**Key commands:**

- `npx skills find [query] [--owner <owner>]` - Search for skills interactively or by keyword, optionally scoped to a GitHub owner
- `npx skills add <package>` - Install a skill from GitHub or other sources
- `npx skills update` - Update all installed skills

**Browse skills at:** https://skills.sh/

## How to Help Users Find Skills

### Step 1: Understand What They Need

When a user asks for help with something, identify:

1. The domain (e.g., React, testing, design, deployment)
2. The specific task (e.g., writing tests, creating animations, reviewing PRs)
3. Whether this is a common enough task that a skill likely exists

### Step 2: Search the Private Skill Market First

Before searching public sources, check the internal DADO-Skill-market.

**检查登录状态：**
- 执行 `skillctl list` — 如果可以列出 Skill，说明已登录，直接搜索
- 如果未登录 → 提示用户提供服务地址和账号密码，执行 `skillctl login`

**搜索内部市场：**
```bash
skillctl list
```

**如果有结果**，展示给用户：
```
I found an internal team skill that might help!

- "{name}" — {summary}
  Version: {latestVersion}
  Install: skillctl install --skill {slug} --version <version> --target <dir>
```

Only move to Step 3 if the internal market returns **zero** relevant results.

### Step 3: Check the Leaderboard First

Before running a CLI search, check the [skills.sh leaderboard](https://skills.sh/) to see if a well-known skill already exists for the domain. The leaderboard ranks skills by total installs, surfacing the most popular and battle-tested options.

For example, top skills for web development include:
- `vercel-labs/agent-skills` — React, Next.js, web design (100K+ installs each)
- `anthropics/skills` — Frontend design, document processing (100K+ installs)

### Step 4: Search for Skills

If the leaderboard doesn't cover the user's need, run the find command:

```bash
npx skills find [query] [--owner <owner>]
```

For example:

- User asks "how do I make my React app faster?" → `npx skills find react performance`
- User asks "can you help me with PR reviews?" → `npx skills find pr review`
- User asks "I need to create a changelog" → `npx skills find changelog`

### Step 5: Verify Quality Before Recommending

**Do not recommend a skill based solely on search results.** Always verify:

1. **Install count** — Prefer skills with 1K+ installs. Be cautious with anything under 100.
2. **Source reputation** — Official sources (`vercel-labs`, `anthropics`, `microsoft`) are more trustworthy than unknown authors.
3. **GitHub stars** — Check the source repository. A skill from a repo with <100 stars should be treated with skepticism.

### Step 6: Present Options to the User

When you find relevant skills, present them to the user with:

1. The skill name and what it does
2. The install count and source
3. The install command they can run
4. A link to learn more at skills.sh

Example response:

```
I found a skill that might help! The "react-best-practices" skill provides
React and Next.js performance optimization guidelines from Vercel Engineering.
(185K installs)

To install it:
npx skills add vercel-labs/agent-skills@react-best-practices

Learn more: https://skills.sh/vercel-labs/agent-skills/react-best-practices
```

### Step 7: Offer to Install

If the user wants to proceed, you can install the skill for them:

```bash
npx skills add <owner/repo@skill> -g -y
```

The `-g` flag installs globally (user-level) and `-y` skips confirmation prompts.

## Common Skill Categories

When searching, consider these common categories:

| Category        | Example Queries                          |
| --------------- | ---------------------------------------- |
| Web Development | react, nextjs, typescript, css, tailwind |
| Testing         | testing, jest, playwright, e2e           |
| DevOps          | deploy, docker, kubernetes, ci-cd        |
| Documentation   | docs, readme, changelog, api-docs        |
| Code Quality    | review, lint, refactor, best-practices   |
| Design          | ui, ux, design-system, accessibility     |
| Productivity    | workflow, automation, git                |

## Tips for Effective Searches

1. **Use specific keywords**: "react testing" is better than just "testing"
2. **Try alternative terms**: If "deploy" doesn't work, try "deployment" or "ci-cd"
3. **Check popular sources**: Many skills come from `vercel-labs/agent-skills` or `ComposioHQ/awesome-claude-skills`

## When No Skills Are Found

If no relevant skills exist:

1. Acknowledge that no existing skill was found
2. Offer to help with the task directly using your general capabilities
3. Suggest the user could create their own skill with `npx skills init`

Example:

```
I searched for skills related to "xyz" but didn't find any matches.
I can still help you with this task directly! Would you like me to proceed?

If this is something you do often, you could create your own skill:
npx skills init my-xyz-skill
```

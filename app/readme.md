# FastAPI Skill-Checker App

This module exposes a FastAPI application and a router you can mount into your existing app.

Examples

Mount router into your existing FastAPI app:

```python
from fastapi import FastAPI
from app.api.router import router as skill_checker_router

app = FastAPI()
app.include_router(skill_checker_router, prefix="/skill-checker", tags=["skill-checker"])


1. 上传 ZIP
2. 调用 /start/{skill_id}
3. 后台执行 SkillManager.run_check_for_skill
4. 解压 ZIP 并读取目标 skill
5. 执行 bundled skill-checker 的 frontmatter 校验
6. 执行原有的功能测试 / LLM 测试计划
7. 让 LLM agent 生成 20 条触发测试 query
8. 让 LLM agent 对 20 条 query 分别判断是否触发目标 skill
9. 用 skill-checker 的 scoring.py 计算触发评测结果
10. 扫描已声明 dependencies 并计算环境汇总
11. 用 skill-checker 的 scoring.py merge 生成 TRACE 五维报告
12. 写入最终 report
# Skill Checker - FastAPI-based LLM-driven Skill Validation Service

This repository provides a modular FastAPI service that implements an LLM-driven "Skill-Checker" agent (TRACE scoring).

Quick overview
- Async FastAPI app exposing REST endpoints to upload a skill zip, start validation, check status, and fetch report.
- Modular components that you can import into an existing FastAPI project.
- LLM support is configurable: OpenAI (OPENAI_API_KEY) and a generic Deepseek-like HTTP provider (DEEPSEEK_URL + DEEPSEEK_API_KEY) are supported.
- Optional Docker-based sandboxing for skills (disabled by default). The service will still run validation without Docker.
- The bundled `skill/skill-checker` skill is the mandatory validation core. Every uploaded archive is checked for `SKILL.md` frontmatter, then the configured LLM agent generates and evaluates 20 trigger queries before the skill's canonical TRACE report is produced. A check fails rather than emitting a partial TRACE report if trigger evaluation cannot run.

See `app/README.md` for usage and embedding examples.

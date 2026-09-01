# Skill Checker - FastAPI-based LLM-driven Skill Validation Service

This repository provides a modular FastAPI service that implements an LLM-driven "Skill-Checker" agent (TRACE scoring).

Quick overview
- Async FastAPI app exposing REST endpoints to upload a skill zip, start validation, check status, and fetch report.
- Modular components that you can import into an existing FastAPI project.
- LLM support is configurable: OpenAI (OPENAI_API_KEY) and a generic Deepseek-like HTTP provider (DEEPSEEK_URL + DEEPSEEK_API_KEY) are supported.
- Optional Docker-based sandboxing for skills (disabled by default). The service will still run validation without Docker.

See `app/README.md` for usage and embedding examples.
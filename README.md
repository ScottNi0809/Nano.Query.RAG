### Introduction
This is a Query repo of WTG internal content, used with RAG framework.

## Project Plan

Full project plan with architecture, phased implementation steps, tech stack, and team collaboration guide:

- **English**: [Plan.md](Plan.md)
- **中文版**: [Plan_Chinese.md](Plan_Chinese.md)

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your OpenAI API key
cp .env.example .env
# Edit .env and add your key

# 3. Add documents to the docs/ folder (PDF, MD, or TXT)

# 4. Run
python rag.py
```

Type questions at the `Q:` prompt. Type `quit` to exit.
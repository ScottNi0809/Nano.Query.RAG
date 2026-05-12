"""
Legacy CLI entry point for WTG.Query.RAG.

The production API lives under backend/app.
Run the backend with:

    cd backend
    uvicorn app.main:app --reload --port 8000
"""

import subprocess
import sys


def main():
    print("Starting WTG.Query.RAG FastAPI backend...")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--port",
            "8000",
        ],
        cwd="backend",
        check=False,
    )


if __name__ == "__main__":
    main()
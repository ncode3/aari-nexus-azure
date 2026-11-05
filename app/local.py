"""Run with python -m app.local. Uses .env.local, never the Azure profile."""
import os
from pathlib import Path
from dotenv import load_dotenv


def configure_local_environment():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env.local", override=True)
    # Empty values also prevent config.py's .env loader restoring cloud settings.
    for key in ("AZURE_KEY_VAULT_URI", "AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY",
                "AZURE_OPENAI_DEPLOYMENT", "AZURE_STORAGE_CONNECTION_STRING",
                "AZURE_STORAGE_ACCOUNT_URL", "APPLICATIONINSIGHTS_CONNECTION_STRING"):
        os.environ[key] = ""
    os.environ["NEXUS_MODEL_PROVIDER"] = "ollama"
    os.environ["COHORT_GRAPH_ENABLED"] = "false"
    os.environ["APP_ENV"] = "local"
    os.environ.setdefault("NEXUS_MEMORY_PATH", str(root / "data" / "nexus_memory.sqlite3"))
    os.environ.setdefault("NEXUS_LOCAL_ARTIFACT_PATH", str(root / "data" / "artifacts"))
    os.environ.setdefault("MODEL_TIMEOUT_SECONDS", "120")


def main():
    configure_local_environment()
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()

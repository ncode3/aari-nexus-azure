"""Explicit provider selection. Errors never trigger paid fallback."""
from app.config import Settings
from app.azure_openai_client import AzureOpenAIClient
from app.ollama_local_client import OllamaLocalClient


def create_model_client(settings: Settings):
    if settings.model_provider == "ollama":
        return OllamaLocalClient(settings.ollama_model, settings.ollama_base_url,
                                 settings.model_timeout_seconds)
    if settings.model_provider == "azure":
        return AzureOpenAIClient(settings)
    raise ValueError("Unknown model provider")

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_openai import (
    AzureChatOpenAI,
    AzureOpenAIEmbeddings,
    ChatOpenAI,
    OpenAIEmbeddings,
)

from app.config import Settings, get_settings


GITHUB_MODELS_BASE_URL = "https://models.inference.ai.azure.com"


class LLMService:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    def get_chat_model(self) -> BaseChatModel:
        provider = self.settings.llm_provider

        if provider == "github":
            if not self.settings.github_token:
                raise ValueError("GITHUB_TOKEN is required when LLM_PROVIDER=github")
            return ChatOpenAI(
                model=self.settings.model_name,
                temperature=0,
                api_key=self.settings.github_token,
                base_url=GITHUB_MODELS_BASE_URL,
            )

        if provider == "openai":
            if not self.settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
            return ChatOpenAI(
                model=self.settings.model_name,
                temperature=0,
                api_key=self.settings.openai_api_key,
            )

        if provider == "azure":
            if not self.settings.azure_openai_endpoint or not self.settings.azure_openai_api_key:
                raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY are required when LLM_PROVIDER=azure")
            return AzureChatOpenAI(
                azure_endpoint=self.settings.azure_openai_endpoint,
                api_key=self.settings.azure_openai_api_key,
                azure_deployment=self.settings.azure_openai_deployment or self.settings.model_name,
                api_version="2024-02-15-preview",
                temperature=0,
            )

        if provider == "ollama":
            return ChatOllama(
                model=self.settings.model_name,
                base_url=self.settings.ollama_base_url,
                temperature=0,
            )

        if provider == "vllm":
            return ChatOpenAI(
                model=self.settings.vllm_model_name or self.settings.model_name,
                temperature=0,
                api_key="not-needed",
                base_url=self.settings.vllm_base_url,
            )

        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

    def get_embeddings(self) -> Embeddings:
        provider = self.settings.llm_provider

        if provider == "github":
            if not self.settings.github_token:
                raise ValueError("GITHUB_TOKEN is required when LLM_PROVIDER=github")
            return OpenAIEmbeddings(
                model=self.settings.embedding_model,
                api_key=self.settings.github_token,
                base_url=GITHUB_MODELS_BASE_URL,
            )

        if provider == "openai":
            if not self.settings.openai_api_key:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
            return OpenAIEmbeddings(
                model=self.settings.embedding_model,
                api_key=self.settings.openai_api_key,
            )

        if provider == "azure":
            if not self.settings.azure_openai_endpoint or not self.settings.azure_openai_api_key:
                raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY are required when LLM_PROVIDER=azure")
            return AzureOpenAIEmbeddings(
                azure_endpoint=self.settings.azure_openai_endpoint,
                api_key=self.settings.azure_openai_api_key,
                azure_deployment=self.settings.azure_openai_embedding_deployment or self.settings.embedding_model,
                api_version="2024-02-15-preview",
            )

        if provider == "ollama":
            return OllamaEmbeddings(
                model=self.settings.embedding_model,
                base_url=self.settings.ollama_base_url,
            )

        if provider == "vllm":
            return OpenAIEmbeddings(
                model=self.settings.embedding_model,
                api_key="not-needed",
                base_url=self.settings.vllm_base_url,
            )

        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")


def get_llm_service() -> LLMService:
    return LLMService()
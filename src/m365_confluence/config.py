"""Configuration loaded from environment variables (optionally a .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


def _require_any(*names: str) -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    raise ConfigError(f"Missing required environment variable (one of): {', '.join(names)}")


def _split_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _as_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _clean_token(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1].strip()
    return value


def _load_org_context() -> str:
    path = os.getenv("ORG_CONTEXT_FILE")
    if path:
        file_path = Path(path)
        if file_path.exists():
            return file_path.read_text(encoding="utf-8").strip()
    return os.getenv("ORG_CONTEXT", "").strip()


@dataclass
class GraphConfig:
    tenant_id: str
    client_id: str
    client_secret: str
    base_url: str = "https://graph.microsoft.com/v1.0"
    authority: str = "https://login.microsoftonline.com"

    @classmethod
    def from_env(cls) -> GraphConfig:
        return cls(
            tenant_id=_require("M365_TENANT_ID"),
            client_id=_require("M365_CLIENT_ID"),
            client_secret=_require("M365_CLIENT_SECRET"),
            base_url=os.getenv("M365_GRAPH_BASE_URL", "https://graph.microsoft.com/v1.0"),
            authority=os.getenv("M365_AUTHORITY", "https://login.microsoftonline.com"),
        )


@dataclass
class RoadmapConfig:
    api_url: str = "https://www.microsoft.com/releasecommunications/api/v2/m365"

    @classmethod
    def from_env(cls) -> RoadmapConfig:
        return cls(
            api_url=os.getenv(
                "M365_ROADMAP_API_URL",
                "https://www.microsoft.com/releasecommunications/api/v2/m365",
            ),
        )


@dataclass
class AIConfig:
    provider: str  # "anthropic" | "azure_openai" | "local"
    output_language: str = "de"
    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    # Azure OpenAI
    azure_endpoint: str = ""
    azure_api_key: str = ""
    azure_deployment: str = ""
    azure_api_version: str = "2024-10-21"
    # Local / OpenAI-compatible endpoint (Ollama, LM Studio, vLLM, ...)
    local_base_url: str = "http://localhost:11434/v1"
    local_model: str = ""
    local_api_key: str = "not-needed"
    # Optional organisation profile injected into the (cached) system prompt so
    # decision recommendations reflect your environment.
    org_context: str = ""

    @classmethod
    def from_env(cls) -> AIConfig:
        provider = os.getenv("AI_PROVIDER", "anthropic").strip().lower()
        if provider not in {"anthropic", "azure_openai", "local"}:
            raise ConfigError(
                f"Unknown AI_PROVIDER '{provider}' (expected: anthropic | azure_openai | local)"
            )
        return cls(
            provider=provider,
            output_language=os.getenv("OUTPUT_LANGUAGE", "de"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
            azure_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            local_base_url=os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1"),
            local_model=os.getenv("LOCAL_LLM_MODEL", ""),
            local_api_key=os.getenv("LOCAL_LLM_API_KEY", "not-needed"),
            org_context=_load_org_context(),
        )


@dataclass
class ConfluenceConfig:
    base_url: str  # e.g. https://confluence.example.com
    token: str  # Personal Access Token (Bearer)
    space_key: str
    parent_page_id: str = ""
    backend: str = "requests"  # "requests" (built-in) or "atlassian" (atlassian-python-api)

    @classmethod
    def from_env(cls) -> ConfluenceConfig:
        return cls(
            base_url=_require("CONFLUENCE_BASE_URL").strip().rstrip("/"),
            token=_clean_token(_require_any("CONFLUENCE_TOKEN", "ConfluencePAT")),
            space_key=_require("CONFLUENCE_SPACE").strip(),
            parent_page_id=os.getenv("CONFLUENCE_PARENT_PAGE_ID", ""),
            backend=os.getenv("CONFLUENCE_BACKEND", "requests").strip().lower(),
        )


@dataclass
class FilterConfig:
    """Default relevance filters; overridable per run via CLI flags."""

    products: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    major_only: bool = False
    action_required: bool = False
    worldwide_only: bool = True
    new_rollouts_only: bool = True
    quarter: str = ""

    @classmethod
    def from_env(cls) -> FilterConfig:
        return cls(
            products=_split_list(os.getenv("FILTER_PRODUCTS", "")),
            categories=_split_list(os.getenv("FILTER_CATEGORIES", "")),
            major_only=_as_bool(os.getenv("FILTER_MAJOR_ONLY")),
            action_required=_as_bool(os.getenv("FILTER_ACTION_REQUIRED")),
            worldwide_only=_as_bool(os.getenv("FILTER_WORLDWIDE_ONLY", "true")),
            new_rollouts_only=_as_bool(os.getenv("FILTER_NEW_ROLLOUTS_ONLY", "true")),
            quarter=os.getenv("FILTER_QUARTER", "").strip(),
        )


@dataclass
class Config:
    graph: GraphConfig | None
    roadmap: RoadmapConfig | None
    ai: AIConfig
    confluence: ConfluenceConfig | None
    filters: FilterConfig

    @classmethod
    def load(
        cls,
        *,
        use_message_center: bool,
        use_roadmap: bool,
        require_confluence: bool = True,
    ) -> Config:
        load_dotenv()
        return cls(
            graph=GraphConfig.from_env() if use_message_center else None,
            roadmap=RoadmapConfig.from_env() if use_roadmap else None,
            ai=AIConfig.from_env(),
            confluence=ConfluenceConfig.from_env() if require_confluence else None,
            filters=FilterConfig.from_env(),
        )

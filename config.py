"""
Enpro Filtration Mastermind Portal — Configuration
Pydantic Settings with env var loading for Modular AI Architecture
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):
    # ═══════════════════════════════════════════════════════════════════════════
    # Azure OpenAI - Multiple Model Deployments
    # ═══════════════════════════════════════════════════════════════════════════
    AZURE_OPENAI_ENDPOINT: str = Field(
        default="https://enpro-filtration-ai.services.ai.azure.com/api/projects/enpro-filtration-ai-project/openai/v1",
        description="Azure OpenAI / AI Foundry endpoint URL"
    )
    AZURE_OPENAI_KEY: str = Field(default="", description="Azure OpenAI API key")
    AZURE_OPENAI_API_VERSION: str = Field(default="2026-01-01", description="Azure OpenAI API version")
    
    # Model Deployments - Sales-First Architecture
    # Fast/Cheap: GPT-5.4 Nano/Mini for lookups and extraction
    AZURE_DEPLOYMENT_FAST: str = Field(
        default="gpt-5.4-mini",
        description="Fast model for lookups and entity extraction"
    )
    
    # Standard: GPT-5.4 for general reasoning
    AZURE_DEPLOYMENT_STANDARD: str = Field(
        default="gpt-5.4",
        description="Standard model for general responses"
    )
    
    # Reasoning: o3-mini for compare and structured reasoning
    AZURE_DEPLOYMENT_REASONING: str = Field(
        default="o3-mini",
        description="Reasoning model for compare and analysis"
    )
    
    # High Reasoning: o3-mini-high for pregame strategy
    AZURE_DEPLOYMENT_STRATEGIC: str = Field(
        default="o3-mini-high",
        description="Strategic reasoning for pregame and complex quotes"
    )
    
    # Safety Critical: o3-pro for hydrogen, H2S, >400F, etc.
    AZURE_DEPLOYMENT_SAFETY: str = Field(
        default="o3-pro",
        description="Safety-critical reasoning model"
    )
    
    # Classification: Phi-4 via Azure AI Foundry (ultra-low cost)
    AZURE_DEPLOYMENT_CLASSIFIER: str = Field(
        default="phi-4",
        description="Intent classifier via Azure AI Foundry"
    )
    
    # Legacy fallback (for compatibility during migration)
    AZURE_DEPLOYMENT_ROUTER: str = Field(default="gpt-4.1-mini", description="Legacy router model")
    AZURE_DEPLOYMENT_REASONING_LEGACY: str = Field(default="gpt-4o", description="Legacy reasoning model")

    # ═══════════════════════════════════════════════════════════════════════════
    # Azure Speech Services (for Voice)
    # ═══════════════════════════════════════════════════════════════════════════
    AZURE_SPEECH_ENDPOINT: str = Field(
        default="",
        description="Azure Speech Services endpoint"
    )
    AZURE_SPEECH_KEY: str = Field(
        default="",
        description="Azure Speech Services key"
    )
    AZURE_SPEECH_REGION: str = Field(
        default="eastus",
        description="Azure Speech Services region"
    )
    # Phonetic-optimized model for industrial part numbers
    AZURE_SPEECH_MODEL_ID: str = Field(
        default="en-US-phonetic-industrial",
        description="Custom speech model ID for part numbers"
    )
    
    # Legacy Whisper (will be deprecated)
    AZURE_WHISPER_ENDPOINT: str = Field(default="", description="Azure Whisper endpoint (legacy)")
    AZURE_WHISPER_KEY: str = Field(default="", description="Azure Whisper key (legacy)")
    AZURE_WHISPER_DEPLOYMENT: str = Field(default="whisper", description="Azure Whisper deployment (legacy)")

    # ═══════════════════════════════════════════════════════════════════════════
    # Azure Blob Storage
    # ═══════════════════════════════════════════════════════════════════════════
    AZURE_BLOB_SAS: str = Field(default="", description="SAS token for Azure Blob access")
    AZURE_STORAGE_ACCOUNT: str = Field(default="", description="Azure Storage account name")
    AZURE_STORAGE_CONTAINER: str = Field(default="data", description="Azure Storage container name")

    # ═══════════════════════════════════════════════════════════════════════════
    # Database (PostgreSQL)
    # ═══════════════════════════════════════════════════════════════════════════
    DATABASE_URL: str = Field(
        default="",
        description="PostgreSQL connection string"
    )
    
    # ═══════════════════════════════════════════════════════════════════════════
    # Local paths
    # ═══════════════════════════════════════════════════════════════════════════
    SESSION_DIR: str = Field(default="data/sessions", description="Session storage directory")
    AUDIT_LOG: str = Field(default="data/audit.jsonl", description="Audit log file path")
    KB_DIR: str = Field(default="kb", description="Knowledge base directory")

    # ═══════════════════════════════════════════════════════════════════════════
    # Server
    # ═══════════════════════════════════════════════════════════════════════════
    HOST: str = Field(default="0.0.0.0", description="Server bind host")
    PORT: int = Field(default=8000, description="Server bind port")
    DEBUG: bool = Field(default=False, description="Debug mode")

    # ═══════════════════════════════════════════════════════════════════════════
    # Security
    # ═══════════════════════════════════════════════════════════════════════════
    ADMIN_TOKEN: str = Field(default="", description="Admin API token for sensitive endpoints")
    JWT_SECRET: str = Field(default="", description="JWT signing secret")
    SESSION_SECRET: str = Field(default="", description="Session encryption secret")

    # ═══════════════════════════════════════════════════════════════════════════
    # Feature Flags
    # ═══════════════════════════════════════════════════════════════════════════
    ENABLE_VOICE: bool = Field(default=True, description="Enable voice search")
    ENABLE_REASONING_TRACE: bool = Field(default=True, description="Show reasoning traces in UI")
    USE_MODULAR_MODELS: bool = Field(default=True, description="Use new modular AI architecture")
    USE_UNIFIED_HANDLER: bool = Field(default=False, description="Use v3.0 unified backend handler")
    USE_PHI4_ROUTING: bool = Field(default=False, description="Use Phi-4 for intelligent query routing")
    USE_HARDCODED_CHEMICAL: bool = Field(default=True, description="Use hardcoded chemical lookups")
    ENABLE_SAFETY_CHECK: bool = Field(default=True, description="Enable safety escalation checks")

    # ═══════════════════════════════════════════════════════════════════════════
    # SMTP / Email
    # ═══════════════════════════════════════════════════════════════════════════
    smtp_host: str = Field(default="", alias="SMTP_HOST", description="SMTP server host")
    smtp_port: int = Field(default=587, alias="SMTP_PORT", description="SMTP server port")
    smtp_user: str = Field(default="", alias="SMTP_USER", description="SMTP username")
    smtp_pass: str = Field(default="", alias="SMTP_PASS", description="SMTP password")
    report_email: str = Field(default="pwnetsuite@outlook.com", alias="REPORT_EMAIL", description="Report recipient email")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Module-level instance for direct import
settings = get_settings()


# ═══════════════════════════════════════════════════════════════════════════
# Model Cost Reference (for tracking)
# ═══════════════════════════════════════════════════════════════════════════
MODEL_COSTS = {
    # Model: {input_cost_per_1M, output_cost_per_1M}
    "gpt-5.4": {"input": 2.50, "output": 10.00},
    "gpt-5.4-mini": {"input": 0.75, "output": 3.00},
    "gpt-5.4-nano": {"input": 0.20, "output": 1.25},
    "o3-mini": {"input": 1.10, "output": 4.40},
    "o3-mini-high": {"input": 1.10, "output": 4.40},
    "o3-pro": {"input": 5.00, "output": 20.00},
    "phi-4": {"input": 0.10, "output": 0.40},
    # Legacy
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.50, "output": 2.00},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in dollars for a request."""
    costs = MODEL_COSTS.get(model, MODEL_COSTS["gpt-5.4"])
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    return round(input_cost + output_cost, 6)

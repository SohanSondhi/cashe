from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    tavily_api_key: str = ""
    prism_api_key: str = ""
    prism_base_url: str = "https://api.ssimplifi.com/v1"
    prism_model: str = "any"
    prism_mode: str = "sport"
    prism_trace_url: str = "https://prismtrace.blockconvey.com/api/traces"
    prism_project_id: str = ""
    fireworks_api_key: str = ""
    fireworks_base_url: str = "https://api.fireworks.ai/inference/v1"
    fireworks_model: str = "accounts/fireworks/models/kimi-k2p6"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5.6-terra"
    openai_realtime_model: str = "gpt-realtime-2.1"
    openai_voice: str = "marin"
    public_base_url: str = ""
    public_host: str = ""
    voice_to_number: str = ""
    harborline_phone: str = ""
    restaurant_phone: str = ""
    telnyx_api_key: str = ""
    telnyx_connection_id: str = ""
    telnyx_from_number: str = ""
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_api_key: str = ""
    twilio_api_secret: str = ""
    vapi_api_key: str = ""
    vapi_phone_number_id: str = ""
    vapi_area_code: str = "415"
    vapi_voice_id: str = "alloy"
    bland_api_key: str = ""
    bland_voice: str = "josh"
    bland_model: str = "base"
    local_server: str = "http://127.0.0.1:8080"
    local_server_twilio: str = "http://127.0.0.1:8081"
    customer_name: str = "Alex"
    customer_phone: str = ""
    cashe_db: str = "data/cashe.db"
    cashe_host: str = "127.0.0.1"
    cashe_port: int = 8000
    artifact_dir: Path = ROOT / "data" / "artifacts"
    tavily_cache_dir: Path = Path(__file__).parent / "fixtures" / "tavily_cache"


settings = Settings()
settings.artifact_dir.mkdir(parents=True, exist_ok=True)

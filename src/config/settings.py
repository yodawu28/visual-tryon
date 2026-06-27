"""
Application settings sử dụng Pydantic Settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import List, Optional, Any, Union
from pathlib import Path


class Settings(BaseSettings):
    """
    Application configuration từ environment variables.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")
    host: str = Field(default="127.0.0.1", env="HOST")
    port: int = Field(default=8000, env="PORT")
    api_profile: str = Field(default="kiosk", env="API_PROFILE")

    # CORS
    cors_origins: Union[str, List[str]] = Field(
        default=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5174",
            "http://127.0.0.1:5174",
        ],
        env="CORS_ORIGINS",
    )

    # Semantic Parser
    semantic_parser_provider: str = Field(
        default="ollama", env="SEMANTIC_PARSER_PROVIDER"
    )  # "ollama" primary; "openai" for explicit fallback/eval

    # OpenAI
    openai_api_key: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o", env="OPENAI_MODEL")
    openai_timeout: int = Field(default=30, env="OPENAI_TIMEOUT")
    openai_max_retries: int = Field(default=3, env="OPENAI_MAX_RETRIES")

    # Ollama semantic parser
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434", env="OLLAMA_BASE_URL"
    )
    ollama_model: str = Field(default="vto-brain", env="OLLAMA_MODEL")
    ollama_timeout: int = Field(default=300, env="OLLAMA_TIMEOUT")
    tryon_analyzer_ollama_model: str = Field(
        default="qwen2.5vl:7b",
        env="TRYON_ANALYZER_OLLAMA_MODEL",
    )
    tryon_analyzer_timeout: int = Field(
        default=300,
        env="TRYON_ANALYZER_TIMEOUT",
    )
    kiosk_visual_preview_provider: str = Field(
        default="disabled",
        env="KIOSK_VISUAL_PREVIEW_PROVIDER",
    )  # "disabled", "local_leffa" for self-hosted GPU tops preview, or "replicate_qwen" for benchmark/debug

    # Local Leffa visual try-on provider
    local_leffa_root: Path = Field(
        default=Path(__file__).parent.parent.parent / "models" / "external" / "Leffa",
        env="LOCAL_LEFFA_ROOT",
    )
    local_leffa_repo_url: str = Field(
        default="https://github.com/franciszzj/Leffa.git",
        env="LOCAL_LEFFA_REPO_URL",
    )
    local_leffa_model_repo_id: str = Field(
        default="franciszzj/Leffa",
        env="LOCAL_LEFFA_MODEL_REPO_ID",
    )
    local_leffa_checkpoint_dir: Path = Field(
        default=Path(__file__).parent.parent.parent
        / "models"
        / "external"
        / "Leffa"
        / "ckpts",
        env="LOCAL_LEFFA_CHECKPOINT_DIR",
    )
    local_leffa_hf_home: Optional[Path] = Field(
        default=None,
        env="LOCAL_LEFFA_HF_HOME",
    )
    local_leffa_torch_home: Optional[Path] = Field(
        default=None,
        env="LOCAL_LEFFA_TORCH_HOME",
    )
    local_leffa_xdg_cache_home: Optional[Path] = Field(
        default=None,
        env="LOCAL_LEFFA_XDG_CACHE_HOME",
    )
    local_leffa_python: Optional[Path] = Field(
        default=None,
        env="LOCAL_LEFFA_PYTHON",
    )
    local_leffa_no_clone: bool = Field(default=True, env="LOCAL_LEFFA_NO_CLONE")
    local_leffa_size: str = Field(default="768x1024", env="LOCAL_LEFFA_SIZE")
    local_leffa_device: str = Field(default="cuda", env="LOCAL_LEFFA_DEVICE")
    local_leffa_dtype: str = Field(default="float16", env="LOCAL_LEFFA_DTYPE")
    local_leffa_vt_model_type: str = Field(
        default="viton_hd",
        env="LOCAL_LEFFA_VT_MODEL_TYPE",
    )
    local_leffa_steps: int = Field(default=30, env="LOCAL_LEFFA_STEPS")
    local_leffa_guidance_scale: float = Field(
        default=2.5,
        env="LOCAL_LEFFA_GUIDANCE_SCALE",
    )
    local_leffa_seed: int = Field(default=42, env="LOCAL_LEFFA_SEED")
    local_leffa_timeout: int = Field(default=1800, env="LOCAL_LEFFA_TIMEOUT")

    # Replicate
    replicate_api_token: Optional[str] = Field(default=None, env="REPLICATE_API_TOKEN")
    replicate_timeout: int = Field(default=120, env="REPLICATE_TIMEOUT")
    replicate_preview_model: str = Field(
        default="qwen/qwen-image-edit-2511", env="REPLICATE_PREVIEW_MODEL"
    )
    replicate_preview_model_version: Optional[str] = Field(
        default=None, env="REPLICATE_PREVIEW_MODEL_VERSION"
    )
    replicate_preview_input_mapping: str = Field(
        default="multi_image_edit", env="REPLICATE_PREVIEW_INPUT_MAPPING"
    )  # "multi_image_edit" for Qwen; "google_nano_banana" for Google preview
    replicate_preview_go_fast: bool = Field(
        default=True, env="REPLICATE_PREVIEW_GO_FAST"
    )
    replicate_preview_model_warning: Optional[str] = Field(
        default=None, env="REPLICATE_PREVIEW_MODEL_WARNING"
    )

    # Avatar generation
    avatar_generator_mode: str = Field(
        default="replicate",
        env="AVATAR_GENERATOR_MODE",
    )  # "replicate" or "local_command"
    local_avatar_command: str = Field(default="", env="LOCAL_AVATAR_COMMAND")
    local_avatar_model_id: str = Field(
        default="local-command-avatar",
        env="LOCAL_AVATAR_MODEL_ID",
    )
    local_avatar_timeout: int = Field(default=1200, env="LOCAL_AVATAR_TIMEOUT")
    local_avatar_output_dir: Path = Field(
        default=Path(__file__).parent.parent.parent
        / "data"
        / "avatar_cache"
        / "local_outputs",
        env="LOCAL_AVATAR_OUTPUT_DIR",
    )

    # Image Generation Mode
    image_gen_mode: str = Field(
        default="remote", env="IMAGE_GEN_MODE"
    )  # "local", "remote", "qwen-fast", or "replicate-preview"

    # Local Diffusion (for MacBook M-series)
    # NOTE: CatVTON requires custom implementation
    # Using SD 2.1 inpainting as fallback (lighter, better MPS support)
    catvton_model_id: str = Field(
        default="sd2-community/stable-diffusion-2-inpainting",
        env="CATVTON_MODEL_ID",
    )
    catvton_device: str = Field(default="mps", env="CATVTON_DEVICE")  # "mps", "cpu"
    catvton_enable_attention_slicing: bool = Field(
        default=True, env="CATVTON_ENABLE_ATTENTION_SLICING"
    )
    catvton_enable_vae_slicing: bool = Field(
        default=True, env="CATVTON_ENABLE_VAE_SLICING"
    )
    catvton_enable_cpu_offload: bool = Field(
        default=True, env="CATVTON_ENABLE_CPU_OFFLOAD"
    )

    # InsightFace
    insightface_model_dir: Path = Field(
        default=Path.home() / ".insightface" / "models", env="INSIGHTFACE_MODEL_DIR"
    )
    face_detection_threshold: float = Field(default=0.5, env="FACE_DETECTION_THRESHOLD")

    # Storage
    temp_storage_dir: Path = Field(
        default=Path(__file__).parent.parent.parent / "data", env="TEMP_STORAGE_DIR"
    )
    max_upload_size_mb: int = Field(default=10, env="MAX_UPLOAD_SIZE_MB")
    playwright_profile_dir: Path = Field(
        default=Path(__file__).parent.parent.parent / "data" / "playwright" / "profile",
        env="PLAYWRIGHT_PROFILE_DIR",
    )
    eval_report_dir: Path = Field(
        default=Path(__file__).parent.parent.parent / "data" / "eval" / "reports",
        env="EVAL_REPORT_DIR",
    )
    job_queue_backend: str = Field(default="local", env="JOB_QUEUE_BACKEND")
    job_queue_dir: Path = Field(
        default=Path(__file__).parent.parent.parent / "data" / "jobs",
        env="JOB_QUEUE_DIR",
    )
    seed_default_size_charts_on_startup: bool = Field(
        default=True,
        env="SEED_DEFAULT_SIZE_CHARTS_ON_STARTUP",
    )

    # Memory Management
    enable_memory_cleanup: bool = Field(default=True, env="ENABLE_MEMORY_CLEANUP")
    cleanup_interval_seconds: int = Field(default=300, env="CLEANUP_INTERVAL_SECONDS")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> List[str]:
        """Parse CORS_ORIGINS from .env comma-separated string"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return v
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator(
        "local_leffa_hf_home",
        "local_leffa_torch_home",
        "local_leffa_xdg_cache_home",
        "local_leffa_python",
        mode="before",
    )
    @classmethod
    def empty_path_to_none(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator(
        "temp_storage_dir",
        "playwright_profile_dir",
        "eval_report_dir",
        "local_avatar_output_dir",
        "job_queue_dir",
    )
    @classmethod
    def create_temp_dir(cls, v):
        v = Path(v)
        v.mkdir(parents=True, exist_ok=True)
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


# Singleton pattern
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

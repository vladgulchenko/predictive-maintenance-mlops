from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    model_path: str = "artifacts/predictive_maintenance_pipeline.joblib"
    metadata_path : str = "artifacts/metadata.json"
    database_url: str | None = None
    log_level: str = "INFO"

    model_config = {"env_file": ".env"}

settings = Settings()
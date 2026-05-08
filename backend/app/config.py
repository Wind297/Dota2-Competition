from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./dota2_competition.db"
    secret_key: str = "change-me-in-production"
    admin_password: str = "666"
    timezone: str = "Asia/Shanghai"


settings = Settings()

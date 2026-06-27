"""アプリ設定 (環境変数 / .env から読み込む)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """環境変数で上書き可能な設定値."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ZRESP_", extra="ignore")

    # アプリの表示名 (インスペクタ UI のヘッダ等に使用)
    app_name: str = "zresp"

    # /cache/bytes/{size} が許可する最大バイト数 (DoS 防止のための上限)
    max_bytes: int = 100 * 1024 * 1024  # 100 MiB


settings = Settings()

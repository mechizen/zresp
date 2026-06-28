"""アプリ設定 (環境変数 / .env から読み込む)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """環境変数で上書き可能な設定値."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ZRESP_", extra="ignore")

    # アプリの表示名 (インスペクタ UI のヘッダ等に使用)
    app_name: str = "zresp"

    # /cache/bytes/{size} が許可する最大バイト数 (DoS 防止のための上限)
    max_bytes: int = 100 * 1024 * 1024  # 100 MiB

    # CORS: ブラウザクライアント (req-sender 等) からの検証を許可する。
    # 既定は全オリジン許可。Cookie 等の credentialed リクエストを使う場合は、
    # cors_allow_origins を具体的なオリジンに絞り、cors_allow_credentials=true にする
    # (CORS 仕様上、"*" と credentials は併用できないため)。
    # 環境変数例: ZRESP_CORS_ALLOW_ORIGINS='["https://app.example.com"]'
    cors_allow_origins: list[str] = ["*"]
    cors_allow_credentials: bool = False


settings = Settings()

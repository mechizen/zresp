# zresp

[ktmrmshk/Dresp](https://github.com/ktmrmshk/Dresp) をモダン化した、**Cloudflare 検証用オリジンサーバ**です。
Cloudflare CDN / WAF / Bot Management / Turnstile / API Shield の挙動を検証するための
「Cloudflare の背後に立つオリジン」として動作します。

あなたはコーディング支援エージェントとして、ユーザーの指示に従いコードの実装・修正を行います。

---

## 重要な設計前提

- **これは Cloudflare Worker ではなく、実オリジンサーバ(コンテナ)である。**
  Worker はキャッシュより前で動くため、オリジンが実際に受け取るヘッダ
  (`X-Forwarded-For` の最終付与、Bot スコア、`Client-Cert` 等の転送ヘッダ)を観測できない。
  検証地点として正しいのは「Cloudflare の背後の実オリジン」なので、コンテナとして実装する。
- 公開は **Cloudflare Tunnel(cloudflared)** 経由を基本とする。前段に CDN/WAF/Bot/Turnstile/API Shield が効く。
- レスポンスのキャッシュ可否は、本文に載せた `generated_at` / `uuid` がリロードで変わらないかで判定する
  (オリジンは `CF-Cache-Status` を受信できないため)。

---

## システムアーキテクチャ

- [**Python**](https://www.python.org/) 3.12+ — 実装言語
- [**FastAPI**](https://fastapi.tiangolo.com/) — Web フレームワーク(OpenAPI 自動生成 → API Shield 検証に活用)
- [**uvicorn**](https://www.uvicorn.org/) — ASGI サーバ。`--proxy-headers` でプロキシ配下のヘッダを信頼
- [**Jinja2**](https://jinja.palletsprojects.com/) — HTML インスペクタのテンプレート
- [**Pydantic**](https://docs.pydantic.dev/) v2 — リクエスト/レスポンスの型と検証
- [**uv**](https://docs.astral.sh/uv/) — パッケージ/環境管理
- [**Docker**](https://www.docker.com/) + Cloudflare Tunnel — 配信

---

## ディレクトリ構成

```
zresp/
├── pyproject.toml          # 依存・ruff・pytest・mypy 設定
├── uv.lock
├── Dockerfile              # uv ビルド → python:3.13-slim, 非root, healthcheck
├── docker-compose.yml      # app + cloudflared(profile: tunnel)
├── app/
│   ├── main.py             # FastAPI 本体・ルーター登録・ランディング・/healthz
│   ├── config.py           # pydantic-settings (ZRESP_ プレフィックス)
│   ├── routers/
│   │   ├── echo.py         # リクエスト・インスペクタ (JSON / 多形式)
│   │   ├── cache.py        # CDN/キャッシュ検証
│   │   ├── response.py     # 汎用レスポンス整形 (status/redirect/delay/cookie/header)
│   │   └── content.py      # コンテンツ配信・動的画像生成
│   ├── services/
│   │   ├── request_info.py # リクエスト/CF ヘッダの抽出・分類
│   │   ├── payload.py      # キャッシュ可視化用ペイロード
│   │   └── content.py      # サンプル/画像/PDF 生成
│   ├── templates/          # base / index / inspect (Jinja2)
│   └── static/             # style.css / samples/ (動画・フォントの実ファイル)
├── tests/                  # pytest (FastAPI TestClient)
└── agent-docs/init/        # 開発ガイドライン(セッション開始時に読む)
```

---

## セッション開始時の必須確認

最初に必ず `agent-docs/init/` フォルダ内のすべての .md ファイルを No1 から順番に読むこと。
内容を理解してからタスクに取り組むこと。

---

## ユーザーとのコミュニケーション

- 正しい技術用語を使う。ただし初出時や操作が必要な場合は1文でフォローを添える。
- 「何が起きたか」より「何ができるようになったか／次に何をするか」を先に伝える。
- エラー時は「〜できない問題が起きました。原因は〜です。直します」と先に結論を言う。
- サーバ起動後は「ブラウザで `http://localhost:8000/` を開いてください」と具体的な URL を伝える
  (FastAPI の対話ドキュメントは `http://localhost:8000/docs`)。

---

## コードスタイル規約

スタックは **Python + FastAPI**。

- **型ヒント必須**: 関数の引数・戻り値に型注釈を付ける。`Any` は避け、信頼できない入力は Pydantic で検証する。
- **外部入力は検証する**: クエリ・ボディ・ヘッダ・環境変数は使用前に型と妥当性を確認する。
- **フォーマッタ/リンタは ruff**: `line-length = 100`、ダブルクォート、インポート整列(isort 互換)。
- **命名**: 関数・変数は `snake_case`、クラスは `PascalCase`、定数は `SCREAMING_SNAKE_CASE`、
  モジュール内部限定のヘルパーは `_` プレフィックス。
- **インポート順**: 標準ライブラリ → サードパーティ → 内部モジュール(`app....`)。
- **ルーターは `app/routers/` に分割**し、`app/main.py` で `include_router` する。
- **Cloudflare 由来のヘッダ名・挙動はドキュメント準拠**で扱う(推測で書かない)。
  参照: https://developers.cloudflare.com/

---

## 完了前に必ず通すコマンド

```bash
uv run ruff check .          # Lint
uv run ruff format --check . # フォーマット確認
uv run pytest                # テスト
```

いずれかでもエラーが出たら完了としない。型チェックを行う場合は `uv run mypy app`。

---

## コアプリンシプル

- **手抜きなし**: 根本原因を探す。一時的な修正をしない。シニアエンジニアの基準で。
- **最小インパクト**: 必要な箇所だけ変更する。
- **検証してから完了**: サーバを起動し、対象エンドポイントの挙動を確認してから完了とする。

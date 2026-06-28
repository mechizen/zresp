# zresp

**指示どおりの HTTP レスポンスを返す、従順で柔軟な Web サーバ**

ステータスコード・ヘッダ・本文・Cookie・遅延・リダイレクト・各種コンテンツタイプ(画像/PDF/JS/CSS など)を
**自在にコントロール**して応答できます。あわせて、受信したリクエストの中身を可視化する **Echo(インスペクタ)** も備えます。

### 主な用途
- **CDNの検証用オリジン**
- CDN / リバースプロキシ / ロードバランサ の挙動確認(キャッシュ・圧縮・ヘッダ書き換え・タイムアウト等)
- クライアント / SDK / 監視ツールのテスト用バックエンド(任意のステータス・遅延・リダイレクトを再現)

要するに「こういう応答を返して」と頼めば、そのとおりに返す検証用の Web サーバです。

---

## 必要なもの

- [uv](https://docs.astral.sh/uv/)(Python 環境管理) — ローカル実行する場合
- [Docker](https://www.docker.com/) — コンテナ実行する場合
- (任意) Cloudflare アカウント + ゾーン — Cloudflare 経由で検証する場合

---

## クイックスタート(ローカル)

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8000
```

ブラウザで http://localhost:8000/ を開くと、検証ツール一覧と現在のリクエスト要約が表示されます。
API の対話ドキュメント(OpenAPI)は http://localhost:8000/docs です。

## クイックスタート(Docker)

```bash
docker compose up --build
# → http://localhost:8000/
```

---

## エンドポイント一覧

### リクエスト・インスペクタ(Echo)
Cloudflare が付与したヘッダを意味別に分類して表示します。

| パス | 説明 |
| --- | --- |
| `GET /` | ランディング。検証ツール一覧 + 現在のリクエスト要約 |
| `GET /inspect` | HTML 版インスペクタ(CF 付与ヘッダを強調表示) |
| `ANY /api/echo` | 全リクエスト情報を JSON で返す(全メソッド対応) |
| `ANY /api/echo.{ext}` | 形式を指定して返す(`json` / `txt` / `xml` / `html`) |
| `ANY /api/inspect` | `/api/echo` のエイリアス |
| `GET /healthz` | ヘルスチェック |

分類されるヘッダの例: `cf-connecting-ip` / `cf-ray` / `cf-ipcountry`(Geo)/ `cf-bot-score`(Bot)/
`client-cert`(mTLS)/ `cf-access-jwt-assertion`(Access)など。

### CDN / キャッシュ検証
キャッシュ可否は、本文の `generated_at` / `uuid` がリロードで**変わらなければキャッシュ提供**と判定します。

| パス | 説明 |
| --- | --- |
| `GET /cache/timestamp` | キャッシュ確認プローブ(既定 `Cache-Control: public, max-age=60`) |
| `GET /cache/control` | 任意の Cache-Control / Expires / Vary を設定(クエリ指定) |
| `GET /cache/etag` | `ETag` / `Last-Modified` を返し、条件付きリクエストに `304` |
| `GET /cache/bytes/{size}` | 指定サイズの本文(`1kb`/`5mb` 等)。`Range` で `206 Partial Content` |
| `GET /cache/vary` | 指定ヘッダで `Vary` を設定(キャッシュキー検証) |

例:
```bash
# キャッシュ確認(2回叩いて uuid が変わるか確認。Cloudflare 経由なら 2回目が同一になり得る)
curl -s http://localhost:8000/cache/timestamp

# 条件付きリクエストで 304
curl -s -D - -H 'If-None-Match: "zresp-etag-v1"' http://localhost:8000/cache/etag -o /dev/null

# Range リクエスト(206)
curl -s -D - -H 'Range: bytes=0-99' http://localhost:8000/cache/bytes/1mb -o /dev/null
```

### 汎用レスポンス整形(/response)
ステータスコードやリダイレクトなど、キャッシュに依存しない応答の作り込み。

| パス | 説明 |
| --- | --- |
| `GET /response/status/{code}` | 任意のステータスコードを返す。3xx は `?location=<URL>` で `Location` ヘッダを付与 |
| `GET /response/redirect/{n}` | n 回リダイレクトを繰り返し、終点で `200`(`?status=301` で各ホップのコードを指定) |
| `GET /response/delay/{seconds}` | 指定秒だけ待ってから応答(上限 30 秒)。タイムアウト検証 |
| `GET /response/cookies/set` | クエリの各 `key=value` を Set-Cookie で返す(複数可) |
| `GET /response/cookie` | 属性付きで 1 つの Cookie を設定(`name` `value` `max_age` `path` `domain` `secure` `httponly` `samesite`) |
| `GET /response/headers` | クエリの各 `key=value` をレスポンスヘッダとして返す |

例:
```bash
# リダイレクト(301 + Location)
curl -s -D - -o /dev/null 'http://localhost:8000/response/status/301?location=/api/echo'

# リダイレクトチェーン(3 ホップ追従)
curl -sL http://localhost:8000/response/redirect/3

# 属性付き Cookie
curl -s -D - -o /dev/null 'http://localhost:8000/response/cookie?name=sid&value=abc&samesite=Lax&httponly=true&secure=true'

# 任意レスポンスヘッダ
curl -s -D - -o /dev/null 'http://localhost:8000/response/headers?X-Test=hello&Cache-Control=no-store'
```

### コンテンツ配信(/content)
各種コンテンツタイプの配信と動的画像生成。CDN キャッシュ / 圧縮 / 画像最適化(Polish) / WAF のファイル検査の検証に。

| パス | 説明 |
| --- | --- |
| `GET /content/sample.{ext}` | サンプルを配信。`html`/`txt`/`css`/`js`/`json`/`xml`/`svg`/`pdf`/`png`/`jpg`/`gif`/`webp` は動的生成 |
| `GET /content/image/{W}x{H}.{fmt}` | 指定サイズの画像を生成(`png`/`jpg`/`gif`/`webp`、例 `640x480.png`) |

例:
```bash
# 動的画像(任意サイズ)
curl -s http://localhost:8000/content/image/640x480.png -o sample.png

# サンプル PDF / JPEG
curl -s http://localhost:8000/content/sample.pdf -o sample.pdf
```

> `mp4` / `webm` / `ttf` / `woff` / `woff2` は生成が難しいため、`app/static/samples/sample.{ext}` を
> 置くとその実ファイルを配信します(未配置時は 404)。

---

## CORS(ブラウザクライアントからの検証)

[req-sender](https://github.com/mechizen/req-sender) のような**ブラウザから `fetch` で叩く検証クライアント**でも
レスポンスを読めるよう、zresp は **CORS ヘッダをオリジン自身で返します**(既定で全オリジン許可)。

- プリフライト(`OPTIONS`)に応答し、`Access-Control-Allow-Origin` / `-Methods` / `-Headers` を付与
- `Access-Control-Expose-Headers: *` で、JS から**全レスポンスヘッダを読める**(ヘッダ検証向け)

> **重要**: Cloudflare の Transform ルールで CORS を付与している場合は、**そのルールを外してください**。
> 両方で付けると `Access-Control-Allow-Origin` が重複し、ブラウザが CORS エラーになります。

Cookie 等の credentialed リクエストを使う場合は、`"*"` と credentials は併用できないため、
`ZRESP_CORS_ALLOW_ORIGINS` を具体的なオリジンに絞り、`ZRESP_CORS_ALLOW_CREDENTIALS=true` にします
(`.env.example` 参照)。

---

## Cloudflare の前段に配置する(Tunnel)

グローバル IP やポート開放なしに、コンテナを Cloudflare のプロキシ配下に出せます。

1. Cloudflare ダッシュボードで **named tunnel** を作成し、トークンを取得
2. `.env.example` を `.env` にコピーし、`TUNNEL_TOKEN` を設定
3. トンネルの公開ホスト名(例 `origin-test.example.com`)を `http://app:8000` にルーティング
4. 起動:
   ```bash
   docker compose --profile tunnel up --build
   ```
5. 公開ホスト名にアクセスし、`/inspect` で `CF-Ray` / `CF-Connecting-IP` 等が付与されていることを確認

簡易確認だけなら quick tunnel も使えます:
```bash
cloudflared tunnel --url http://localhost:8000
```

配置後は、Cloudflare 側で Cache Rules / WAF / Bot Management / Turnstile / API Shield を設定し、
このオリジンへの到達結果を `/inspect` や各キャッシュエンドポイントで観測します。

---

## 公開オリジン + HTTPS(Cloudflare Origin CA / Full strict)

グローバル IP を持つオリジンを Cloudflare の背後に置き、**CF↔オリジン間も TLS で暗号化**する構成です。
TLS は前段の nginx が終端し、zresp 本体は HTTP のままにします(`docker-compose.yml` の `proxy` サービス)。

```
ブラウザ ──HTTPS(CFエッジ証明書)──▶ Cloudflare ──HTTPS(Origin CA)──▶ nginx(443) ──HTTP──▶ app:8000
```

1. CF ダッシュボード **SSL/TLS → Origin Server → Create Certificate** で Origin CA 証明書(最長15年)を発行し、
   `certs/origin.pem`(証明書)/ `certs/origin.key`(秘密鍵)に保存(詳細は [certs/README.md](certs/README.md))。
2. DNS を **プロキシ有効(オレンジ)**、SSL/TLS 暗号化モードを **Full (strict)** に設定。
3. 起動:
   ```bash
   docker compose --profile tls-origin up --build
   ```
4. (推奨) **Authenticated Origin Pulls** で「CF 以外の接続」を遮断したい場合は、
   `certs/authenticated_origin_pull_ca.pem` を配置し、[deploy/nginx.conf](deploy/nginx.conf) の該当2行のコメントを外し、
   CF 側でも AOP を有効化。あわせてオリジンの 443 を [Cloudflare の IP レンジ ↗](https://www.cloudflare.com/ips/) のみに制限すると堅牢です。

検証ポイント: `/inspect` で `X-Forwarded-Proto` / `CF-Visitor` が `https` になっているか、
証明書を外す/期限切れにして CF が **526 (Invalid SSL certificate)** を返すか、など。

> **使い分け**: 証明書管理なしで手軽に出すなら **Tunnel**(上記)、CF を正面に置きつつ CF↔オリジンを
> 暗号化するなら **Origin CA(本節)**、CF を介さず直接 HTTPS で公開するなら **Caddy + Let's Encrypt** が向きます。

---

## ロードマップ

**実装済み:** Echo(多形式)/ CDN・キャッシュ / 汎用レスポンス整形(ステータス・リダイレクト・遅延・Cookie・ヘッダ)/ コンテンツ配信・動的画像生成。

**今後追加予定:**

- **WAF**: 攻撃パターンを安全に受けるエンドポイント、オリジン到達カウンタ、レート制限ターゲット
- **Bot Management**: 転送された bot スコア / JA3・JA4 の表示、JS 検知用ページ
- **Turnstile**: デモフォーム + サーバ側 `siteverify` エンドポイント
- **API Shield**: OpenAPI 公開、JWT 検証(JWKS)、mTLS、Sequence、GraphQL
- **その他**: 動画 / フォントのサンプル同梱、SSE / WebSocket

> 一部機能は Cloudflare のプラン依存です(Bot Management スコアや一部 API Shield・mTLS は Enterprise 級、
> WAF Managed Rules は Pro 以上、Turnstile は無料、Schema Validation は全プラン)。

---

## 開発

```bash
uv run ruff check .            # Lint
uv run ruff format --check .   # フォーマット確認
uv run pytest                  # テスト
uv run mypy app                # 型チェック(任意)
```

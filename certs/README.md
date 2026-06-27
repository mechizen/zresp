# certs

② 公開オリジン + Cloudflare Origin CA (Full strict) 構成で、前段プロキシ(nginx)が読み込む証明書を置く場所です。
**実ファイル(秘密鍵を含む)はコミットされません**(`.gitignore` 参照)。

## 配置するファイル

| ファイル名 | 内容 | 取得元 |
| --- | --- | --- |
| `origin.pem` | Origin CA 証明書(サーバ証明書) | CF ダッシュボード → SSL/TLS → Origin Server → Create Certificate |
| `origin.key` | 上記の秘密鍵 | 同上(発行時に1度だけ表示) |
| `authenticated_origin_pull_ca.pem` | AOP 用の Cloudflare CA 証明書(任意) | [Authenticated Origin Pulls のドキュメント](https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/) |

## 手順(概要)

1. CF ダッシュボードで **Origin CA 証明書を発行**し、`origin.pem` / `origin.key` をここに保存。
2. DNS を **プロキシ有効(オレンジ)**、SSL/TLS モードを **Full (strict)** に設定。
3. 起動: `docker compose --profile tls-origin up --build`(443 で待ち受け)。
4. (任意) **Authenticated Origin Pulls** を使うなら `authenticated_origin_pull_ca.pem` を置き、
   `deploy/nginx.conf` の該当2行のコメントを外して CF 側でも AOP を有効化。

> Origin CA 証明書は **Cloudflare 経由(プロキシ有効)前提**です。プロキシをオフにして直アクセスすると
> ブラウザは証明書を信頼しません(CF↔オリジン間だけを暗号化する用途のため)。

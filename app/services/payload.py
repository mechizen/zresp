"""レスポンス本文に載せる共通ペイロード.

オリジンは `CF-Cache-Status` を受信できないため、本文に毎回変わる
`generated_at` / `uuid` を載せておく。リロードで値が変わらなければ
Cloudflare がキャッシュから提供した、と目視で判定できる。
"""

import uuid
from datetime import UTC, datetime
from typing import Any


def origin_payload(note: str) -> dict[str, Any]:
    """オリジンが生成したことを示す可視化用ペイロード."""
    return {
        "server": "zresp",
        "generated_at": datetime.now(UTC).isoformat(),
        "uuid": str(uuid.uuid4()),
        "note": note,
    }

"""【關卡 17】登入頻率限制（slowapi）

為什麼：/api/auth/login 沒有限制的話，攻擊者可以無限次猜密碼（暴力破解、撞庫）。
bcrypt 很慢（關卡 13）讓猜的成本高一點，但「每個 IP 每分鐘最多幾次」才是真正的門。

slowapi 是 flask-limiter 的 FastAPI 版：
- key_func：決定「誰」算同一個人。這裡用客戶端 IP
- 限制寫在端點上：@limiter.limit("10/minute")
- 超過回 429，帶 Retry-After 標頭
- 計數存在記憶體：單一實例夠用（免費方案就是一台）；多台要改 storage_uri 指向 Redis（例如 Upstash 的免費方案）

最難的一題是「客戶端 IP 是哪個」，見 get_client_ip。
"""

from fastapi import Request
from slowapi import Limiter

from config import settings


def get_client_ip(request: Request) -> str:
    """從 X-Forwarded-For 取出真正的客戶端 IP

    正式環境的請求經過兩層代理：瀏覽器 → Vercel（rewrite）→ Render（負載平衡）→ 我們的程式。
    每一層代理都會把「它看到的來源 IP」**接在** X-Forwarded-For 的最後面，所以會長這樣：
        X-Forwarded-For: <瀏覽器>, <Vercel 的出口 IP>
    直接用 request.client.host 拿到的是最後一層代理的 IP，所有使用者看起來都是同一個人，
    限制會變成「全站每分鐘 10 次」。

    為什麼不能直接拿最左邊那個？因為最左邊是任何人都能自己填的（curl -H "X-Forwarded-For: 1.2.3.4"），
    攻擊者每次換一個假 IP 就繞過限制。只有「代理接上去的那幾段」才可信。
    所以規則是：**從右邊數，跳過 TRUSTED_PROXY_HOPS 層可信的代理，取下一個**。
    本機沒有代理：hops=0，用 request.client.host；Render 一層：1；Vercel + Render：2（render.yaml）。
    hops 設太大（比實際代理層數多）會拿到攻擊者可控的值，設太小會拿到代理的 IP，兩種都要避免，
    開 ENABLE_DEBUG_ENDPOINTS 打 /api/_ip 可以看到實際的標頭內容來決定。

    ⚠️ uvicorn 自己也會讀 X-Forwarded-For：它預設相信「連線來源是 127.0.0.1 / ::1」的請求帶的這個標頭，
    在我們拿到 request 之前就把 request.client.host 改成標頭裡的值。所以本機用 localhost 打、hops=0，
    request.client.host 其實已經是客戶端自己填的，換假 IP 就繞過（2026-10-30 帶關卡 17 時發現）。
    Dockerfile 與 k8s 的啟動參數加了 --no-proxy-headers，讓 IP 只由這個函式決定；
    本機要做頻率限制的實驗，啟動時也加 --no-proxy-headers。
    """
    hops = settings.trusted_proxy_hops
    forwarded = request.headers.get("X-Forwarded-For", "")
    ips = [ip.strip() for ip in forwarded.split(",") if ip.strip()]
    if hops > 0 and len(ips) >= hops:
        return ips[-hops]
    # 沒有代理、或標頭段數不夠（例如有人直接打 Render 網址）：用連線本身的來源
    return request.client.host if request.client else "unknown"


limiter = Limiter(
    key_func=get_client_ip,
    headers_enabled=True,  # 回應帶 X-RateLimit-Limit / Remaining / Reset 與 Retry-After
    enabled=settings.rate_limit_enabled,  # 測試時關掉（conftest.py），不然 pytest 會自己被擋
)

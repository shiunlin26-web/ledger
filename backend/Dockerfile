# 【關卡 9】後端的 Dockerfile：把後端打包成一個 image
#
# image 是什麼？「一個打包好的、包含作業系統 + Python + 套件 + 程式碼的壓縮檔」。
# container 是什麼？「把 image 跑起來的那個程序」。同一個 image 可以跑很多個 container。
# 比喻：image 是遊戲光碟，container 是正在跑的遊戲。
#
# Dockerfile 的每一行指令會變成 image 的一「層」（layer），而且有快取：
# 只要某一行以及它之前的行沒變，這一層就直接用上次的結果。
# 所以「先複製套件清單、裝套件，最後才複製程式碼」：改程式碼不會重裝套件，build 從幾分鐘變幾秒。
#
# 這是「multi-stage build」：第一階段（builder）裝套件，第二階段只拿裝好的結果。
# 第二階段不含 uv、編譯工具、快取，image 比較小，也比較安全。

# ---------- 第一階段：安裝套件 ----------
# 基底 image：官方 Python 3.13 的精簡版（slim = 沒有多餘的系統工具）。
# 版本寫死，不寫 "python:3"，否則哪天升級了行為會悄悄改變。
FROM python:3.13-slim AS builder

# 從 uv 的官方 image 把 uv 執行檔複製過來（比 pip install uv 快且版本固定）
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /bin/uv

# 容器裡的工作目錄，之後的相對路徑都以這裡為準
WORKDIR /app

# uv 的兩個設定：
# UV_COMPILE_BYTECODE=1 預先把 .py 編譯成 .pyc，啟動快一點
# UV_LINK_MODE=copy     把套件「複製」進 .venv 而不是用連結，跨階段複製才不會壞掉
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# 【快取關鍵】先只複製套件清單，裝套件。程式碼還沒複製進來，所以改程式碼不會讓這一層失效。
# --frozen：嚴格照 uv.lock 裝，lock 檔和 pyproject 對不上就直接失敗（不會偷偷升級）
# --no-dev：不裝 pytest、ruff 這些開發用套件，正式環境用不到
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---------- 第二階段：真正拿來跑的 image ----------
FROM python:3.13-slim

WORKDIR /app

# 不要用 root 跑程式：就算程式被攻破，攻擊者也拿不到容器的最高權限
RUN useradd --create-home --uid 1000 app

# 從第一階段把裝好的 .venv 複製過來（這就是 multi-stage 的重點：只拿結果，不拿過程）
COPY --from=builder --chown=app:app /app/.venv /app/.venv

# 現在才複製程式碼。.dockerignore 會排除 .env、tests、.venv 等不該進 image 的東西
COPY --chown=app:app . .

# 把 .venv 的 bin 加進 PATH，之後直接打 uvicorn、alembic 就會用到 .venv 裡的版本
ENV PATH="/app/.venv/bin:$PATH" \
    # Python 的輸出不要先存在緩衝區，log 才會即時出現在 docker logs / Render log
    PYTHONUNBUFFERED=1

USER app

# 文件用途：告訴看的人這個服務聽哪個 port。實際對外的 port 由 docker run -p 或平台決定
EXPOSE 8000

# 啟動指令。用 sh -c 是因為要用到環境變數 $PORT 和 && 串兩個指令：
# 1. alembic upgrade head：先把資料表升到最新版（部署時自動跑遷移，不用手動）
#    遷移失敗會讓容器直接退出，平台會標記部署失敗，不會跑一個資料表版本不對的後端
# 2. uvicorn：啟動後端
#    --host 0.0.0.0：聽所有網路介面。寫 127.0.0.1 的話容器外面連不進來（部署常見錯誤）
#    --port ${PORT:-8000}：平台（Render 等）會用環境變數 PORT 告訴你要聽哪個 port，沒給就用 8000
#    --no-access-log：【關卡 11】uvicorn 內建的每請求一行 log 關掉，改由 main.py 的 middleware 記（有 request id、耗時）
#    --no-proxy-headers：【關卡 17】uvicorn 預設會相信「從 127.0.0.1 連進來」的 X-Forwarded-For，先把 client IP 改掉；
#      客戶端 IP 只交給 rate_limit.py 的 TRUSTED_PROXY_HOPS 決定，兩層都讀會互相打架（k8s 的 sidecar 就是從 127.0.0.1 連進來）
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log --no-proxy-headers"]

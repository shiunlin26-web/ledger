# 除錯手冊：症狀 → 原因 → 修法

照**症狀**找，不用先知道原因。踩到新的坑就加一列。

**任何症狀先做這三件事**：

1. **看 log**。本機看跑 uvicorn 的終端機；Render 看 Logs；CI 看 Actions 打叉的那一步。錯誤訊息的**最後幾行**通常就是答案。
2. **看 Network**。瀏覽器 DevTools → Network，點失敗的請求，看 Status、Response、Cookies。
3. **分段確認**。後端活著（`/api/ping`）→ 前端打得到後端（Network 裡 `/api/health` 是 200）→ 最後才看登入。

## 安裝與啟動

| 症狀 | 原因 | 修法 |
| --- | --- | --- |
| `uv`、`git`、`node` 出現 `is not recognized` | 終端機程式（Windows Terminal、VS Code）是在工具裝好之前開的，拿的是舊的 PATH。`setup.ps1` 在這種視窗跑，找不到 git 會自己另外下載一份 | 終端機程式**整個**關掉重開（只開新分頁不夠）；VS Code 用「開啟資料夾」開 repo 根目錄並信任。跑 `setup.ps1` 前先確認 `(Get-Command git).Source` 有東西 |
| `npm ci` 報 `EPERM: operation not permitted, unlink ...` | `npm ci` 要先刪 `node_modules`，但 `npm run dev` 或 `npm test` 還開著、檔案被佔用 | 把跑前端的終端機 `Ctrl+C` 關掉，再重跑 |
| `setup.ps1` 問連線字串時打錯 | 已經寫進 `backend\.env` | 刪掉 `backend\.env` 重跑腳本，或 `notepad backend\.env` 直接改 |
| `.ps1` 說「指令碼執行被停用」 | Windows 預設擋 `.ps1` | `powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -SkipTests` |
| `setup.ps1` 一跑就一堆 `Unexpected token`、中文亂碼 | 檔案沒有 UTF-8 BOM，PowerShell 5.1 用系統編碼讀 | `.ps1` 要存成 UTF-8 **with BOM**（`.editorconfig` 已設定）；用程式改檔時也要保留 BOM |
| `uv run pytest` 要跑好幾分鐘 | 測試資料庫在 Neon（新加坡），每個測試都要網路來回 | 正常。改程式時只跑相關的檔案：`uv run pytest -q tests/test_auth.py` |
| `ModuleNotFoundError: No module named 'xxx'` | 指令沒用 `uv run` 開頭，用到了系統的 Python | 指令前加 `uv run`；在 `backend` 跑 `uv sync` |
| `npm run dev` 報 `styleText` 或 `Cannot find native binding` | Node 太舊（要 22.22 以上），或 `node_modules` 是在舊 Node 下裝的 | `node -v` 確認版本；在 `frontend` 刪掉 `node_modules` 再 `npm ci`。**不要**刪 `package-lock.json` |
| 啟動時 `ValidationError ... Field required` | `backend\.env` 缺 `DATABASE_URL` 或 `JWT_SECRET`；正式環境則是平台沒設 | 本機補 `.env`；Render 到 Environment 補 |
| 啟動時 `jwt_secret ... at least 32 characters` | `JWT_SECRET` 太短 | `uv run python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `relation "user" does not exist` | 資料表沒建或不是最新 | `uv run alembic upgrade head` |
| `connect() got an unexpected keyword argument 'sslmode'` | Neon 的連線字串沒轉成 asyncpg 格式 | 開頭 `postgresql+asyncpg://`、`sslmode=require` 改 `ssl=require`、刪掉 `channel_binding` |
| 前端打 `/api/...` 回 500 或 `ECONNREFUSED` | 後端沒在 8000 跑，Vite 轉不過去 | 先起後端 |
| `npm ci` 說 `10 moderate severity vulnerabilities` | 都在 eslint 等開發工具裡，`npm audit --omit=dev` 是 0 | 不用處理，**不要**跑 `npm audit fix --force`（會換大版本、改 lock 檔）；交給 Dependabot |

## CI

| 症狀 | 原因 | 修法 |
| --- | --- | --- |
| `The lockfile at uv.lock needs to be updated` | 改了 `pyproject.toml` 沒更新 `uv.lock` | 在 `backend` 跑 `uv sync`，`uv.lock` 一起 commit |
| `package.json and package-lock.json are not in sync` | 同上，前端版 | 在 `frontend` 跑 `npm install`，`package-lock.json` 一起 commit |
| `alembic check` 紅 | 改了 `models.py` 沒產生遷移檔 | `uv run alembic revision --autogenerate --rev-id 000X -m "說明"`，檢查產生的檔案再 commit |
| `Smoke test` 紅，log 裡 alembic 報錯 | 容器啟動時遷移失敗，uvicorn 沒起來 | 看 alembic 的錯誤，通常是遷移檔有問題 |
| Dependabot 的 PR CI 紅 | 套件升級（通常是大版本）造成不相容 | 不要合併；看 changelog 決定要改程式還是先關掉 PR |
| CI 綠但正式環境壞 | CI 的環境變數、資料庫和正式環境不同 | 比對 `ci.yml` 的 `env:` 和 Render 的 Environment；看 Render log |

## 部署：後端（Render）

| 症狀 | 原因 | 修法 |
| --- | --- | --- |
| `Deploy failed`，log 最後是 `ValidationError ... Field required` | 環境變數沒設 | Environment 補上，Manual Deploy |
| 顯示 live 但一直 502 | 後端沒聽 `$PORT` 或聽 `127.0.0.1` | `Dockerfile` 的 CMD 要 `--host 0.0.0.0 --port ${PORT:-8000}` |
| 第一個請求等 30～60 秒，或 Vercel 回 504 | 免費方案冷啟動：Render 閒置 15 分鐘、Neon 閒置 5 分鐘會休眠 | 不是 bug，等它醒來 |
| 閒置後第一個請求 500：`connection is closed` | Neon 休眠後連線池裡的舊連線斷了 | `database.py` 已有 `pool_pre_ping=True`；還發生就看 Neon 狀態 |
| `prepared statement "__asyncpg_stmt_1__" already exists` | 用 Neon 的 pooled 連線但 statement cache 沒關 | `database.py` 已處理；或改用非 pooled 的連線字串 |
| alembic 說 `Can't locate revision identified by 'xxxx'` | 資料庫的遷移版本和程式裡的遷移檔對不上 | 看 `alembic_version` 表和 `migrations/versions/`，先搞清楚哪邊對，不要手改 |

## 部署：前端（Vercel）與前後端串接

| 症狀 | 原因 | 修法 |
| --- | --- | --- |
| 註冊、登入都失敗，Console 有 `Unexpected token '<'` | `/api/...` 拿到的是 HTML，不是 JSON：`vercel.json` 的轉發沒生效 | `frontend/vercel.json` 的 `destination` 要是你的 Render 網址加 `/api/:path*`；Vercel 的 Root Directory 要設 `frontend` |
| `/api/...` 回 404，Response 是 Render 的 `Not Found` | 轉發的路徑少了 `/api` | `destination` 要是 `https://<服務名>.onrender.com/api/:path*` |
| 登入成功，**重新整理就掉登入**，Cookies 裡沒有 `refresh_token` | 前端直接打 Render 網址（設了 `VITE_API_URL`）造成跨站；或本機 `COOKIE_SECURE=true` 但網址是 http | 拿掉 `VITE_API_URL`，走 `/api` 代理；本機 `COOKIE_SECURE=false` |
| Console 出現 CORS 錯誤 | 前端沒走代理、直接打後端網域 | 確認 `VITE_API_URL` 沒設、`vercel.json` 正確 |
| 直接開 `/settings` 是 404，從首頁點過去才正常 | 這種路由由前端處理，Vercel 上沒有這個檔案 | `vercel.json` 第二條 rewrite 把非 `/api/` 的路徑都回 `index.html` |
| `/api/...` 全部 404、標頭有 `x-render-routing: no-server` | Vercel 轉到 Render 不認識的網址（`vercel.json` 的網址和實際服務名對不上） | 改 `vercel.json` 推上去讓 Vercel 重新部署 |
| 改了 Vercel 的環境變數沒反應 | `VITE_*` 是 build 時打包進去的 | Deployments → 最新那筆 → Redeploy |
| 推了程式碼，Render 沒有部署 | Render 只看 `main`，或 Auto-Deploy 被關掉 | 確認推的是 main；Render → Settings → Build & Deploy |

## 維護

| 症狀 | 原因 | 修法 |
| --- | --- | --- |
| `/api/health` 的 `version` 不是最新 commit | Render 還沒部署完、CI 紅了沒部署、或 Auto-Deploy 關了 | Render Events 看最近一次部署；Actions 看 CI |
| `/api/health` 的 `db` 是 `error` | 連不上資料庫：`DATABASE_URL` 錯、剛換密碼、Neon 專案暫停 | Render Logs 搜 `database unreachable` |
| `/api/health` 的 `migration` 不是最新 | 啟動時 `alembic upgrade head` 失敗 | Render Logs 找 alembic 那段；見 `RUNBOOK.md` 第 3 節 |
| Sentry 沒收到東西 | `SENTRY_DSN` 沒設；或例外被程式接住了 | Render Logs 啟動時有沒有 `Sentry 已啟用`；用 `/api/_boom` 測 |
| 直接 push main 被拒：`protected branch` | branch protection 生效 | 開分支、開 PR、CI 綠了再合併 |

## 頻率限制

| 症狀 | 原因 | 修法 |
| --- | --- | --- |
| 登入回 429，但只試了一兩次 | 所有人被算成同一個 IP：`TRUSTED_PROXY_HOPS` 設錯（正式環境要 2） | 開 `ENABLE_DEBUG_ENDPOINTS` 看 `/api/_ip` 的 `x_forwarded_for` 有幾段 |
| 端點 500：`parameter \`response\` must be an instance of starlette.responses.Response` | 加了 `@limiter.limit` 的端點少了 `response: Response` 參數 | 補上參數 |

## 登入

| 症狀 | 原因 | 修法 |
| --- | --- | --- |
| 同時發好幾個請求，使用者突然被登出 | 每個都去 refresh，後面幾個拿已經換掉的舊 token，被當成重複使用 | 前端要 single-flight（`client.ts` 的 `refreshPromise` 已處理） |
| 登出所有裝置後，另一台還能用幾分鐘 | access token 不查資料庫，過期前都有效 | 預期行為；`JWT_EXPIRE_MINUTES` 越短影響越小 |
| commit 之後讀物件屬性出現 `MissingGreenlet` | async SQLAlchemy 在 commit 後把屬性標成過期，再讀會偷偷查資料庫 | commit **之前**先把要用的值存到變數 |
| 加了新資料表，測試單獨跑會過、一起跑就失敗 | `tests/conftest.py` 的 `TRUNCATE` 沒清到新表，上一個測試的資料留著 | 把新表加進 `TRUNCATE`，或改成從 `SQLModel.metadata.tables` 自動抓表名 |
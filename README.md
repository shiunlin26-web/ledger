# 記帳本（Ledger）

家庭記帳本。後端 FastAPI + PostgreSQL（Neon），前端 React + Vite，登入用 JWT（access token 放記憶體，refresh token 放 HttpOnly cookie）。

## 需要準備

- Neon 專案一個，裡面兩個資料庫：主資料庫，和測試用的 `ledger_test`（第一次在 Neon 的 SQL Editor 執行 `CREATE DATABASE ledger_test;`）
- Windows 機器要有 git；其他工具（uv、Node）腳本會自己裝

## 跑起來（Windows）

在 PowerShell 執行：

```powershell
git clone https://github.com/shiunlin26-web/ledger.git
cd ledger
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 -SkipTests
```

clone 到哪個資料夾都可以，腳本會從自己所在的位置找到專案。

腳本會問：

- **git 的名字和 email**（沒設過才問）
- **DATABASE_URL**：Neon 後台 → Connect → Pooled connection，原始格式直接貼
- **TEST_DATABASE_URL**：同一條，把資料庫名稱換成 `ledger_test`（兩條不能相同，測試會清空資料表）

最後印出綠字 `==> 完成。` 就是成功。任何一步失敗會停在那一步、印紅字。

跑完後**把終端機程式整個關掉再打開**（新安裝的工具要重開才找得到），開兩個終端機：

```powershell
cd backend;  uv run uvicorn main:app --reload --port 8000
cd frontend; npm run dev
```

瀏覽器開 <http://localhost:5173>。開 <http://localhost:5173/api/health> 應該看到 `"db":"ok"`。

repo 已經在的話只要跑最後一行，腳本會自己 `git pull`。

**Mac / Linux**：`bash scripts/setup.sh --skip-tests`

## 測試

```powershell
cd backend;  uv run pytest -q    # 連 ledger_test，約 5 分鐘
cd frontend; npm test            # 不連網路，約 10 秒
```

## 結構

```
backend/    FastAPI。main.py 入口、routes/ API、models.py 資料表、migrations/ 遷移、tests/ 測試
frontend/   React + Vite。src/ 程式、src/test/ 測試設定與假後端（MSW）
scripts/    setup.ps1（Windows 一鍵建置）、setup.sh（Mac / Linux）、doctor.*（檢查這台有哪些工具）
```

所有 API 都在 `/api` 底下。前端只打自己網域的 `/api`，本機由 Vite 轉給後端（`vite.config.ts`），正式環境由 Vercel 轉（`vercel.json`）。

開發規則與常用指令見 `AGENTS.md`。

## 常見問題

| 症狀 | 處理 |
| --- | --- |
| `uv`、`git`、`node` 找不到（`is not recognized`） | 終端機程式整個關掉重開（只開新分頁不夠）；用 VS Code 的話「開啟資料夾」開 repo 根目錄並信任它 |
| `npm ci` 報 `EPERM` | 先把正在跑的 `npm run dev` / `npm test` 用 `Ctrl+C` 關掉，再重跑腳本 |
| 連線字串打錯 | 刪掉 `backend\.env`，重跑腳本 |
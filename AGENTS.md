# AGENTS.md

這是一個由學習者指揮 AI 拼出來的練習專案：家庭記帳本。
技術棧與結構照 jwt-auth-demo（FastAPI + React + Neon，Render + Vercel），登入模板是從那裡搬來的。

## 結構
（環 2 搬完模板之後照實際情況填）

## 常用指令

```bash
# 後端（在 backend/，不用啟用 venv）
uv sync                        # 安裝套件
uv run uvicorn main:app --reload --port 8000
uv run pytest -q               # 測試（會清空 TEST_DATABASE_URL 的資料表）
uv run ruff check --fix .      # lint
uv run ruff format .           # 格式化（CI 會檢查）
uv run pyright                 # 型別檢查（CI 會檢查）
uv run alembic upgrade head    # 套用遷移
uv run alembic revision --autogenerate --rev-id 000X -m "說明"   # 改完 models.py 後產生遷移
uv run alembic check           # models.py 和遷移檔是否一致

# 前端（在 frontend/）
npm ci && npm run dev
npm run format && npm run lint && npm run typecheck && npm test && npm run build
```

## 規則

### 慣例

- **一環或一個功能一個 commit**，commit 訊息用中文、開頭標環或功能（例：環 1：最小打通。...、功能 1：帳戶與交易。...）。文件類用 docs：、修正用 修正：。
- 程式裡的註解用中文，說「為什麼」不說「做什麼」；新加的東西標 `【環 N】` 或 `【功能 N】`。
- 改了 `models.py` **一定**要產生遷移檔；不手改既有的遷移檔；不用 `create_all`。
- 改了 `pyproject.toml` 要跑 `uv sync` 並把 `uv.lock` 一起 commit；改了 `package.json` 要把 `package-lock.json` 一起 commit。
- 推之前本機跑：`uv run ruff format .`、`uv run ruff check .`、`uv run pyright`、`uv run pytest -q`、`npm run format`、`npm run lint`、`npm run typecheck`、`npm test`、`npm run build`。
- `.env` 永遠不進 git；密鑰只放平台的環境變數。
- **架構與程式碼以現代開發的專業水準為準**。這是練習專案，不是降低標準的理由：型別檢查、格式化、lint、測試、CI 全綠才合併；安全與效能細節照正式專案做。
- **會碰到付費門檻的事，動手前先說**。部署平台的設定、第三方服務的方案，只要可能跳出付費頁，先告訴學習者「這步可能要錢，免費替代是＿＿」，由他決定。

### AI 在練習專案裡的規則

1. **只做被要求的事**。做完列出「我注意到但你沒要求、所以我沒做」的清單，只列不做。
2. 不要為了讓測試過而改測試或跳過測試；不要用 `--no-verify`、空 commit 之類的手段繞過檢查。
3. 不確定就先問，不要猜一個做法做下去。
4. 修 bug 時先說明根本原因，再改。
5. 每個需要登入的端點都要檢查資料屬於目前使用者（不是你的回 404），並有對應的測試。見 jwt-auth-demo 的 `docs/API.md` 第 2 條。
6. 修 bug 先補一個會紅的測試，再修；測試沒紅過就不算抓到。

### 不要碰

- `backend/migrations/versions/` 裡已存在的檔案
- `.env`、任何含密鑰的東西
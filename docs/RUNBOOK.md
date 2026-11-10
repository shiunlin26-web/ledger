# 維運手冊：上線之後會遇到的事，照著做

`DEBUGGING.md` 是「症狀 → 原因」，這份是「**情境 → 步驟**」。壞掉、換密鑰、退版，照這裡做。

**網址**（上線後填）：

- 後端：`https://<Render 服務名>.onrender.com`（`render.yaml` 的 `name` 是 `ledger-backend`）
- 前端：`https://<Vercel 專案>.vercel.app`

## 0. 每次部署後的檢查（30 秒）

1. 開 `<後端網址>/api/health`，看：
   - `db` 是 `ok`
   - `migration` 是 `backend/migrations/versions/` 裡最新的編號
   - `version` 是剛推的 commit（GitHub 上 main 最新 commit 的前 7 碼）
2. 開前端網址，登入，重新整理後還在登入狀態。

`version` 對不上：Render 還沒部署完，或沒有觸發部署（見 `DEBUGGING.md`「維護」）。

## 1. 網站掛了，先做什麼

1. **分段確認**：後端 `/api/ping` → 後端 `/api/health` → 前端網址的 `/api/health` → 登入。哪一段先壞就查哪一段。
2. **看 Render Events**：最近有沒有部署？剛部署完就壞，直接做第 2 節退版。
3. **看 Render Logs**：log 是 JSON，一行一筆。搜 `"level": "ERROR"`，或用使用者回報的 `request_id`（回應的 `X-Request-ID` header）。
4. **看 Sentry**：有沒有新的 issue、發生幾次、哪個路徑。
5. 都正常但第一次很慢或逾時：免費方案冷啟動，等一分鐘再試。

## 2. 退版（剛推的壞了，上一版是好的）

1. Render → 服務 → **Events**
2. 找到上一個 **Deploy live** → 右邊「…」→ **Rollback to this deploy**
3. 等它變 Live，做第 0 節的檢查：`version` 變成上一版的 commit 就是退成功
4. 修好 main 之後：**Manual Deploy → Deploy latest commit**，或推新 commit

退版只是把線上換回舊的 image，**main 上壞的程式碼還在**，下一次 push 又會部署壞的版本，所以一定要修 main。

> ⚠️ 退版不會退資料庫。壞的那版如果跑了「加欄位」的遷移，舊版通常照樣能跑；如果是「刪欄位、改型別」，舊版可能會壞。所以這種遷移要分兩步，見第 3 節。

## 3. 遷移壞了

**正式環境不要手動 `alembic downgrade`。** 原則是 **roll forward**：推一個新的遷移把它改回來。

**情境 A：遷移在啟動時失敗**（Render log 的 alembic 段報錯，部署失敗）

- 舊版還在跑，線上沒壞，不用急
- 這個遷移沒成功跑過，可以直接改它；本機重現、修好，推新 commit

**情境 B：遷移成功了，但內容錯了**（例如欄位名打錯）

- **不要改那個遷移檔**，它已經跑過了，`alembic_version` 記得它
- 改 `models.py` → `uv run alembic revision --autogenerate --rev-id 000X -m "修正 ..."` → 檢查產生的檔案 → 推

**本機練習 downgrade**（只在本機或測試資料庫）：

```bash
uv run alembic current        # 現在在哪一版
uv run alembic history        # 所有版本
uv run alembic downgrade -1   # 退一版
uv run alembic upgrade head   # 再升回去
```

**安全的改表習慣**：刪欄位、改型別分兩次部署。第一次讓程式不再用它（需要的話先加新欄位），第二次才刪。這樣隨時退版都安全。

## 4. 換 JWT_SECRET

時機：懷疑外洩、定期（例如一年一次）。

使用者幾乎感覺不到：access token 是 JWT，換了密鑰會全部失效，但它本來就只有 30 分鐘；refresh token 是隨機字串、資料庫存雜湊，和密鑰無關。所以下一個請求 401 → 前端自動 refresh → 拿到新的 access token，**不用重新登入**。

1. 本機產生：`uv run python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Render → Environment → 改 `JWT_SECRET` → Save（會自動重新部署）
3. 做第 0 節；已登入的那台重新整理，應該還在登入狀態

## 5. 換資料庫密碼或連線字串

1. Neon → 專案 → Roles → Reset password
2. Render → Environment → 改 `DATABASE_URL`（asyncpg 格式：`postgresql+asyncpg://`、`ssl=require`）→ Save
3. 部署完成前有幾十秒連不上，`/api/health` 的 `db` 會是 `error`，部署完就恢復

本機的 `backend\.env` 也要跟著改（刪掉重跑 `setup.ps1`，或直接編輯）。

## 6. 備份與還原

原則只有一條：**刪資料、改表之前先備份**。

**名詞**

- **還原窗**：Neon 保留每一筆改動的歷史，這段時間內的任何一刻都能回去。免費方案是 6 小時（以 <https://neon.com/docs/introduction/plans> 為準）。超過就救不回來，所以「發現得早」最重要。
- **分支（branch）**：整個資料庫的複本，像 git 的分支。「從歷史還原」就是在指定的時間點開一個新分支、換成主分支，**連線字串不變，Render 不用改**。
- **快照（snapshot）**：手動拍一份備份，免費方案 1 張。做危險操作前先拍。

### 6.1 從歷史還原（Neon 後台，不用裝東西）

1. 先記下「出事前」的時間（UTC）
2. 正式的 Neon 專案 → **Branches** → `main` → **Backup & Restore** → **Restore from history** → 選那個時間 → 確認
3. 幾秒後完成，Branches 會多一個帶 old 和時間戳的分支，那是還原前的狀態，確認沒問題再刪
4. 開 `/api/health`：`db` 是 `ok`，`migration` 也會回到那一刻的版本

⚠️ 還原是**整個資料庫**回到那一刻，那之後別人的註冊、資料也會一起消失。真的要還原前，先用同一頁的 **Time Travel**（在還原窗內任一時刻跑唯讀查詢）確認回到哪一刻損失最小。

### 6.2 手動備份（有 `pg_dump` 的機器）

```bash
pg_dump "postgresql://<user>:<pass>@<host>/<db>?sslmode=require" > backup-$(date +%F).sql
ls -la backup-*.sql        # 0 位元組就是失敗
```

連線字串用 Neon 後台 Connect 給的原始格式，**不是** `.env` 裡的 asyncpg 格式。檔案含密碼雜湊，**不要進 git**（`.gitignore` 已擋 `backup-*.sql`）。

**沒有還原過的備份不算備份**：至少試一次把它倒進一個空的資料庫，`SELECT count(*) FROM "user";` 和線上一樣才算數。

## 7. 清理

- 過期的 refresh token：每次登入時順便清，量大了再改成排程。
- 免費額度：Render 每月 750 小時、Sentry 每月 5000 個錯誤、Neon 的計算時數。
- 用 `/api/_boom` 測完 Sentry，記得把 `ENABLE_DEBUG_ENDPOINTS` 關回 `false`。
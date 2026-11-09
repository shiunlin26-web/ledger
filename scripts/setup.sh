#!/usr/bin/env bash
# 【工具】Mac 一鍵建置（對應 Windows 的 setup.ps1）
#
# 學習者晚上與週末用 Mac，Mac 不會每次開機清空，所以第一次跑完之後再跑只是 git pull + 同步套件。
# 做的事和 setup.ps1 一樣，順序也一樣，兩邊對照著看：
#   1. 沒有 Homebrew、git、Node（照 frontend/.nvmrc 的大版號）、uv 就裝；Node 比 .nvmrc 舊也重裝（舊版 Node 裝出來的 node_modules 少東西，見 DEBUGGING.md）
#   2. git pull 最新 main
#   3. 設定 git 的 user.name / user.email（沒有的話會問你）
#   4. backend：uv sync、建立 .env（沒有的話問你 Neon 的兩個連線字串，貼原始格式即可；JWT_SECRET 自動產生）、alembic upgrade head
#   5. frontend：npm ci
#   6. 跑一次 pytest 和 vitest 當基準線（--skip-tests 跳過；沒填 TEST_DATABASE_URL 也會跳過 pytest）
#   7. 檢查 Docker 有沒有（關卡 21 起要用），沒有只提示怎麼裝，不自動裝
#   任何一步失敗腳本就停在那一步（set -e），不會印「完成」。
#
# 用法（在 repo 根目錄或任何地方都可以）：
#   bash scripts/setup.sh --skip-tests
#   bash scripts/setup.sh --env-file ~/jwt.env     # 不手打連線字串，從檔案複製成 backend/.env
set -euo pipefail

ENV_FILE=""
SKIP_TESTS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --env-file) ENV_FILE="${2:-}"; shift 2 ;;
    --skip-tests) SKIP_TESTS=1; shift ;;
    -h|--help) sed -n '2,/^set -euo pipefail/{/^#/p;}' "$0"; exit 0 ;;   # 印檔頭註解到 set 之前為止，檔頭加減行不用改這裡
    *) echo "不認識的參數：$1（可用：--env-file <路徑>、--skip-tests）" >&2; exit 2 ;;
  esac
done

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

step() { printf '\n\033[36m==> %s\033[0m\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

# 【工具】Node 只檢查「有沒有」不夠，還要檢查版本。舊版 Node（例如 18）下 npm ci 會安靜地跳過 Rolldown 的原生套件
# （engines 不符的選用套件 npm 直接略過、不報錯），之後 npm run dev 才炸 Cannot find native binding（DEBUGGING.md 有這條）。
# 大版號 >= .nvmrc 就算過，更新的版本（24）也可以
NODE_MAJOR="$(tr -d '[:space:]' < frontend/.nvmrc | sed -E 's/^v?([0-9]+).*/\1/')"
node_ok() {
  have node || return 1
  [ "$(node --version | sed -E 's/^v?([0-9]+).*/\1/')" -ge "$NODE_MAJOR" ]
}

# Neon 後台複製出來的是 psycopg 格式，asyncpg 要改三個地方（README 第 1 節）。貼原始格式也會被轉對。
convert_neon_url() {
  local url="$1"
  url="$(printf '%s' "$url" | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')"
  [ -z "$url" ] && { printf ''; return; }
  url="$(printf '%s' "$url" | sed -E 's#^postgresql://#postgresql+asyncpg://#; s#^postgres://#postgresql+asyncpg://#; s#sslmode=require#ssl=require#; s#[&?]channel_binding=require##; s#^([^?]*)&#\1?#')"
  printf '%s' "$url"
}

# ---------- 1. 工具（只在 macOS 自動裝，用 Homebrew；Linux 請自己先裝好） ----------
step "檢查工具"
if [ "$(uname -s)" = "Darwin" ]; then
  if ! have brew; then
    step "安裝 Homebrew（會要求 Mac 的登入密碼，這是 Homebrew 官方安裝腳本）"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi
  # Apple Silicon 的 brew 裝在 /opt/homebrew，新終端機才看得到；這裡先讓這次執行看得到
  if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"; fi
  if [ -x /usr/local/bin/brew ]; then eval "$(/usr/local/bin/brew shellenv)"; fi

  have git || { step "安裝 git"; brew install git; }
  if ! node_ok; then
    step "安裝 Node.js $NODE_MAJOR（照 frontend/.nvmrc 的大版號；太舊也重裝）"
    brew install "node@$NODE_MAJOR"
    # node@22 這種固定版本的套件 brew 不會自動連進 PATH，照它的提示加進 zsh 的設定
    node_bin="$(brew --prefix "node@$NODE_MAJOR")/bin"
    export PATH="$node_bin:$PATH"
    grep -q "node@$NODE_MAJOR/bin" "$HOME/.zprofile" 2>/dev/null || echo "export PATH=\"$node_bin:\$PATH\"" >> "$HOME/.zprofile"
    if ! node_ok; then
      now="$(node --version 2>/dev/null || echo '找不到 node')"
      echo "Node $NODE_MAJOR 裝了，但這個終端機跑到的還是舊的（$now，在 $(command -v node || echo '?')）。PATH 上有另一個 Node 排在前面（nvm、brew 的舊版 node……）：移除它或把它從 PATH 拿掉，重開終端機再跑一次" >&2
      exit 1
    fi
  fi
  have uv || { step "安裝 uv"; brew install uv; }
else
  for t in git uv; do
    have "$t" || { echo "缺 $t：這支腳本只在 macOS 自動裝工具，請先自己裝好再跑" >&2; exit 1; }
  done
  node_ok || { echo "Node 要 $NODE_MAJOR 以上（現在：$(node --version 2>/dev/null || echo '沒裝')）：這支腳本只在 macOS 自動裝工具，請先自己裝好再跑" >&2; exit 1; }
fi
echo "git  $(git --version)"
echo "node $(node --version)"
echo "uv   $(uv --version)"

# ---------- 2. 最新程式 ----------
step "git pull"
git pull --ff-only origin main

# ---------- 3. git 身分 ----------
if [ -z "$(git config user.name || true)" ]; then
  read -r -p "git 的 user.name（commit 上顯示的名字）: " name
  git config --global user.name "$name"
fi
if [ -z "$(git config user.email || true)" ]; then
  read -r -p "git 的 user.email（和 GitHub 帳號一樣）: " mail
  git config --global user.email "$mail"
fi

# ---------- 4. 後端 ----------
step "backend：uv sync"
cd "$REPO_ROOT/backend"
uv sync

if [ ! -f .env ]; then
  if [ -n "$ENV_FILE" ] && [ -f "$ENV_FILE" ]; then
    step "backend：從 $ENV_FILE 複製 .env"
    cp "$ENV_FILE" .env
  else
    step "backend：建立 .env（兩個連線字串到 Neon 後台複製，原始格式貼上即可；JWT_SECRET 自動產生）"
    read -r -p "DATABASE_URL（Neon 的連線字串，直接貼）: " db_raw
    read -r -p "TEST_DATABASE_URL（測試資料庫，不能和上面相同；留空就不設）: " test_raw
    db="$(convert_neon_url "$db_raw")"
    test_db="$(convert_neon_url "$test_raw")"
    if [ "$db" = "$test_db" ]; then
      echo "TEST_DATABASE_URL 不能和 DATABASE_URL 相同（測試會清空資料表）。重跑一次。" >&2
      exit 1
    fi
    secret="$(uv run python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    {
      echo "DATABASE_URL=$db"
      echo "JWT_SECRET=$secret"
      echo "COOKIE_SECURE=false"
      [ -n "$test_db" ] && echo "TEST_DATABASE_URL=$test_db"
    } > .env
    echo "已寫入 backend/.env（JWT_SECRET 每次重建都不一樣，只影響本機的 token，沒關係）"
  fi
else
  echo "backend/.env 已存在，不動它"
fi

step "backend：alembic upgrade head"
uv run alembic upgrade head

# ---------- 5. 前端 ----------
step "frontend：npm ci"
cd "$REPO_ROOT/frontend"
npm ci

# ---------- 6. 基準線 ----------
if [ "$SKIP_TESTS" = 0 ]; then
  cd "$REPO_ROOT/backend"
  if grep -qE '^TEST_DATABASE_URL=.' .env; then
    step "基準線：pytest（測試資料庫在 Neon 時約 4 分鐘）"
    uv run pytest -q
  else
    printf '\033[33mbackend/.env 沒有 TEST_DATABASE_URL，跳過 pytest\033[0m\n'
  fi
  step "基準線：vitest"
  cd "$REPO_ROOT/frontend"
  npm test
fi

# ---------- 7. Docker（關卡 21 起才需要；不自動裝，因為 Docker Desktop 是要你點同意的桌面程式） ----------
step "Docker（關卡 21 起需要）"
cd "$REPO_ROOT"
if have docker && docker info >/dev/null 2>&1; then
  echo "docker 有在跑：$(docker --version)"
else
  printf '\033[33m這台還沒有 Docker（或沒開）。關卡 0～20 不需要；關卡 21 起要用時，三選一都免費：\n  Docker Desktop（docker.com，個人使用免費）、OrbStack（orbstack.dev，個人免費）、brew install colima docker && colima start\n裝好之後跑 bash scripts/doctor.sh 確認。\033[0m\n'
fi

printf '\n\033[32m==> 完成。接下來兩個終端機各開一個：\n    cd backend  && uv run uvicorn main:app --reload --port 8000\n    cd frontend && npm run dev\n    瀏覽器開 http://localhost:5173\033[0m\n'

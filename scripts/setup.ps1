<#
【工具】乾淨的 Windows 機器一鍵建置

用途：學習者的電腦每次開機都是乾淨的系統，每次都要從頭裝工具、拉專案、裝套件、填 .env。
這個腳本把整個流程壓成一個指令，三到五分鐘跑完。

每次開機（連 repo 都會消失的乾淨機器）在 PowerShell 貼兩行：
    git clone https://github.com/shiunlin26-web/ledger.git $HOME\ledger
    powershell -ExecutionPolicy Bypass -File $HOME\ledger\scripts\setup.ps1 -SkipTests
（連 git 都沒有時先到 git-scm.com 裝；repo 是公開的，clone 不用登入，push 才要）
repo 還在的話只要第二行，腳本自己會 git pull。

做的事：
  1. 沒有 Node.js、uv 就裝；Node 比 .nvmrc 的大版號舊也重裝（舊版 Node 裝出來的 node_modules 少東西，見 DEBUGGING.md）。有 winget 用 winget，沒有就直接從官網下載 zip，不需要管理員權限
  2. git pull 最新 main
  3. 設定 git 的 user.name / user.email（沒有的話會問你）
  4. backend：uv sync、建立 .env（沒有的話問你 Neon 的兩個連線字串，貼原始格式即可；JWT_SECRET 自動產生）、alembic upgrade head
  5. frontend：npm ci
  6. 跑一次 pytest 和 vitest 當基準線（-SkipTests 跳過；沒填 TEST_DATABASE_URL 也會跳過 pytest）
  任何一步失敗腳本就停在那一步並印出紅字，不會印「完成」。

參數：
  -EnvFile <路徑>   不用手打連線字串，從一個檔案（例如 USB 上的 jwt.env）複製成 backend/.env
  -SkipTests        跳過最後的測試
#>
param(
    [string]$EnvFile = "",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# Windows 內建的 PowerShell 5.1 不會因為外部程式（git、uv、npm）失敗而停下來，$ErrorActionPreference 管不到它們。
# 所以每個外部指令都包在這裡面，exit code 不是 0 就停，不然 alembic 連不上資料庫還會繼續印「完成」
function Must($label, [scriptblock]$block) {
    & $block
    if ($LASTEXITCODE -ne 0) { throw "「$label」失敗（exit code $LASTEXITCODE），停在這裡。看上面的錯誤訊息，修好再重跑。" }
}

# Neon 後台複製出來的是 psycopg 格式，asyncpg 要改三個地方（README 第 1 節）。貼原始格式也會被轉對
function Convert-NeonUrl($url) {
    $url = $url.Trim()
    if ($url -eq "") { return $url }
    $url = $url -replace "^postgresql://", "postgresql+asyncpg://"
    $url = $url -replace "^postgres://", "postgresql+asyncpg://"
    $url = $url -replace "sslmode=require", "ssl=require"
    $url = $url -replace "[&?]channel_binding=require", ""
    return $url
}
function Has($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

# 【工具】Node 只檢查「有沒有」不夠，還要檢查版本。機器預裝的舊 Node（例如 18）會讓 npm ci 安靜地跳過
# Rolldown 的原生套件（engines 不符的選用套件 npm 直接略過、不報錯），之後 npm run dev 才炸
# Cannot find native binding（DEBUGGING.md 有這條）。大版號 >= .nvmrc 就算過，更新的版本（24）也可以
function Node-Ok {
    if (-not (Has node)) { return $false }
    $required = [int]((Get-Content "$RepoRoot\frontend\.nvmrc").Trim() -replace "^v?(\d+).*$", '$1')
    $actual = [int]((node --version) -replace "^v?(\d+).*$", '$1')
    return $actual -ge $required
}

# 讓這個 PowerShell 視窗立刻看得到剛裝好的工具（不用重開終端機，DEBUGGING.md 第一條的坑）
function Refresh-Path {
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("Path", "User") + ";" +
                "$HOME\.local\bin"
}

# ---------- 1. 工具 ----------
# 有 winget 就用 winget；沒有（精簡的 VM 常常沒有）就直接從官網下載 zip 解到 $HOME\.local，不需要管理員權限
$LocalBin = "$HOME\.local"
New-Item -ItemType Directory -Force -Path $LocalBin | Out-Null

function Add-SessionPath($dir) {
    if (-not ($env:Path -split ";" | Where-Object { $_ -eq $dir })) { $env:Path = "$dir;$env:Path" }
    $userPath = [System.Environment]::GetEnvironmentVariable("Path", "User")
    if (-not ($userPath -split ";" | Where-Object { $_ -eq $dir })) {
        [System.Environment]::SetEnvironmentVariable("Path", "$dir;$userPath", "User")
    }
}

function Install-Git {
    if (Has winget) {
        winget install --id Git.Git -e --accept-source-agreements --accept-package-agreements
        Refresh-Path
        return
    }
    # MinGit：Git for Windows 的精簡 zip 版，不用安裝程式
    $rel = Invoke-RestMethod "https://api.github.com/repos/git-for-windows/git/releases/latest"
    $asset = $rel.assets | Where-Object { $_.name -like "MinGit-*-64-bit.zip" -and $_.name -notlike "*busybox*" } | Select-Object -First 1
    $zip = "$env:TEMP\mingit.zip"
    Invoke-WebRequest $asset.browser_download_url -OutFile $zip
    Expand-Archive $zip "$LocalBin\git" -Force
    Add-SessionPath "$LocalBin\git\cmd"
}

function Install-Node {
    # 版本照 frontend/.nvmrc 的大版號（22）抓最新的 22.x
    $major = (Get-Content "$RepoRoot\frontend\.nvmrc").Trim()
    if (Has winget) {
        winget install --id "OpenJS.NodeJS.$major" -e --accept-source-agreements --accept-package-agreements
        Refresh-Path
        if (Node-Ok) { return }
    }
    $index = Invoke-RestMethod "https://nodejs.org/dist/index.json"
    $ver = ($index | Where-Object { $_.version -like "v$major.*" } | Select-Object -First 1).version
    $zip = "$env:TEMP\node.zip"
    Invoke-WebRequest "https://nodejs.org/dist/$ver/node-$ver-win-x64.zip" -OutFile $zip
    if (Test-Path "$LocalBin\node") { Remove-Item "$LocalBin\node" -Recurse -Force }
    Expand-Archive $zip $LocalBin -Force
    Rename-Item "$LocalBin\node-$ver-win-x64" "node"
    Add-SessionPath "$LocalBin\node"
}

function Install-Uv {
    # uv 的官方安裝腳本本來就不用 winget，裝到 $HOME\.local\bin
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    Add-SessionPath "$LocalBin\bin"
    Refresh-Path
}

Step "檢查工具"
if (-not (Has git))  { Step "安裝 git";  Install-Git }
if (-not (Node-Ok)) {
    Step "安裝 Node.js（照 .nvmrc 的大版號；太舊也重裝）"
    Install-Node
    if (-not (Node-Ok)) {
        $now = if (Has node) { (node --version) + "，在 " + (Get-Command node).Source } else { "找不到 node" }
        throw "Node 裝了，但這個視窗跑到的還是舊的（$now）。PATH 上有另一個 Node 排在前面：移除它（設定 → 應用程式 → Node.js）或把它從 PATH 拿掉，重開終端機再跑一次。"
    }
}
if (-not (Has uv))   { Step "安裝 uv";   Install-Uv }
Write-Host ("git  " + (git --version))
Write-Host ("node " + (node --version))
Write-Host ("uv   " + (uv --version))

# ---------- 2. 最新程式 ----------
Step "git pull"
Must "git pull" { git pull --ff-only origin main }

# ---------- 3. git 身分（乾淨機器每次都沒有，沒設 commit 會失敗） ----------
if (-not (git config user.name)) {
    $name = Read-Host "git 的 user.name（commit 上顯示的名字）"
    git config --global user.name $name
}
if (-not (git config user.email)) {
    $mail = Read-Host "git 的 user.email（和 GitHub 帳號一樣）"
    git config --global user.email $mail
}

# ---------- 4. 後端 ----------
Step "backend：uv sync"
Set-Location "$RepoRoot\backend"
Must "uv sync" { uv sync }

if (-not (Test-Path ".env")) {
    if ($EnvFile -ne "" -and (Test-Path $EnvFile)) {
        Step "backend：從 $EnvFile 複製 .env"
        Copy-Item $EnvFile ".env"
    } else {
        Step "backend：建立 .env（兩個連線字串到 Neon 後台複製，原始格式貼上即可；JWT_SECRET 自動產生）"
        $db = Convert-NeonUrl (Read-Host "DATABASE_URL（Neon 的連線字串，直接貼）")
        $testDb = Convert-NeonUrl (Read-Host "TEST_DATABASE_URL（測試資料庫，不能和上面相同；留空就不設）")
        if ($db -eq $testDb) { throw "TEST_DATABASE_URL 不能和 DATABASE_URL 相同（測試會清空資料表）。重跑一次。" }
        $secret = (uv run python -c "import secrets; print(secrets.token_urlsafe(32))")
        $lines = @(
            "DATABASE_URL=$db",
            "JWT_SECRET=$secret",
            "COOKIE_SECURE=false"
        )
        if ($testDb -ne "") { $lines += "TEST_DATABASE_URL=$testDb" }
        Set-Content -Path ".env" -Value $lines -Encoding ascii
        Write-Host "已寫入 backend\.env（JWT_SECRET 每次重建都不一樣，只影響本機的 token，沒關係）"
    }
} else {
    Write-Host "backend\.env 已存在，不動它"
}

Step "backend：alembic upgrade head"
Must "alembic upgrade head" { uv run alembic upgrade head }

# ---------- 5. 前端 ----------
Step "frontend：npm ci"
Set-Location "$RepoRoot\frontend"
Must "npm ci" { npm ci }

# ---------- 6. 基準線 ----------
if (-not $SkipTests) {
    Set-Location "$RepoRoot\backend"
    if (Select-String -Path ".env" -Pattern "^TEST_DATABASE_URL=." -Quiet) {
        Step "基準線：pytest（測試資料庫在 Neon 時約 4 分鐘）"
        Must "pytest" { uv run pytest -q }
    } else {
        Write-Host "backend\.env 沒有 TEST_DATABASE_URL，跳過 pytest" -ForegroundColor Yellow
    }
    Step "基準線：vitest"
    Set-Location "$RepoRoot\frontend"
    Must "vitest" { npm test }
}

Set-Location $RepoRoot
Write-Host @"

==> 完成。接下來兩個終端機各開一個：
    cd backend;  uv run uvicorn main:app --reload --port 8000
    cd frontend; npm run dev
    瀏覽器開 http://localhost:5173

    找不到 uv / node？這個腳本是另開一個 PowerShell 跑的，剛裝的工具只有「之後開的」程式看得到：
    - VS Code：用「開啟資料夾」開 repo 根目錄並信任它，新開的終端機就有（.vscode/settings.json 處理了）
    - 其他 PowerShell / Windows Terminal：整個關掉重開（只開新分頁不夠），
      或在那個視窗跑一次 `$env:Path = "`$env:USERPROFILE\.local\bin;`$env:Path"
"@ -ForegroundColor Green

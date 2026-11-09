<#
【工具】這台機器能做哪幾關？（Windows 版；Mac / Linux 用 doctor.sh）

學習者有兩台機器：平日的 Windows VM 沒有 Docker，晚上與週末的 Mac 有。
關卡 0～20 只要 git、Node、uv；關卡 21 起要 Docker；關卡 23 另外要 kind 與 kubectl。
開任何一關之前先跑這支，把輸出貼給 AI，它就知道該走「Mac 路線」還是「VM 路線」（docs/PLAN-INFRA.md 第 2 節第 4 條）。

    powershell -ExecutionPolicy Bypass -File scripts\doctor.ps1
#>
$ErrorActionPreference = "SilentlyContinue"

function Has($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function Ok($name, $msg)   { Write-Host ("  OK   {0,-10} {1}" -f $name, $msg) -ForegroundColor Green }
function Miss($name, $msg) { Write-Host ("  缺   {0,-10} {1}" -f $name, $msg) -ForegroundColor Red }
function Ver($cmd, $args) { try { $out = & $cmd @args 2>$null; if ($out) { return ($out | Select-Object -First 1) } } catch {} ; return "" }

Write-Host "==> 系統：Windows $([System.Environment]::OSVersion.Version)"

Write-Host "==> 關卡 0～20 需要的工具"
$baseOk = $true
foreach ($t in @("git", "node", "uv")) {
    if (Has $t) { Ok $t (Ver $t @("--version")) } else { Miss $t "沒裝"; $baseOk = $false }
}

Write-Host "==> 關卡 21 起需要的工具（Docker）"
$dockerOk = $false
if (Has docker) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        Ok "docker" ((Ver docker @("--version")) + "（daemon 有在跑）")
        $dockerOk = $true
    } else {
        Miss "docker" "有裝但 daemon 沒在跑（這台 VM 裝不了 Docker，已確認；要動手請到 Mac）"
    }
} else {
    Miss "docker" "沒裝（這台 VM 裝不了 Docker，已確認；要動手請到 Mac）"
}

Write-Host "==> 關卡 23 需要的工具（Kubernetes）"
$k8sOk = $true
foreach ($t in @("kind", "kubectl")) {
    if (Has $t) { Ok $t (Ver $t @("version")) } else { Miss $t "沒裝"; $k8sOk = $false }
}

Write-Host ""
Write-Host "==> 結論：這台可以做"
if ($baseOk) { Write-Host "  關卡 0～20：可以" } else { Write-Host "  關卡 0～20：還不行，先跑 scripts\setup.ps1 -SkipTests" }
if ($dockerOk) { Write-Host "  關卡 21、22、24（compose、E2E、指標、訊息）：可以，走 Mac 路線" } else { Write-Host "  關卡 21、22、24：不行，走 VM 路線（看 CI 的 job log）" }
if ($dockerOk -and $k8sOk) { Write-Host "  關卡 23（Kubernetes）：可以，走 Mac 路線" } else { Write-Host "  關卡 23：不行，走 VM 路線（看 CI 的 k8s job log）" }

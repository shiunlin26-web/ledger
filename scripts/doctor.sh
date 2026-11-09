#!/usr/bin/env bash
# 【工具】這台機器能做哪幾關？（Mac / Linux 版；Windows 用 doctor.ps1）
#
# 學習者有兩台機器：平日的 Windows VM 沒有 Docker，晚上與週末的 Mac 有。
# 關卡 0～20 只要 git、Node、uv；關卡 21 起要 Docker；關卡 23 另外要 kind 與 kubectl。
# 開任何一關之前先跑這支，把輸出貼給 AI，它就知道該走「Mac 路線」還是「VM 路線」（docs/PLAN-INFRA.md 第 2 節第 4 條）。
#
#   bash scripts/doctor.sh
set -u

ok()   { printf '  \033[32m✔\033[0m %-10s %s\n' "$1" "$2"; }
miss() { printf '  \033[31m✘\033[0m %-10s %s\n' "$1" "$2"; }

have() { command -v "$1" >/dev/null 2>&1; }
ver()  { "$@" 2>/dev/null | head -n 1; }

echo "==> 系統：$(uname -s) $(uname -m)"

echo "==> 關卡 0～20 需要的工具"
base_ok=1
for t in git node uv; do
  if have "$t"; then ok "$t" "$(ver "$t" --version)"; else miss "$t" "沒裝"; base_ok=0; fi
done

echo "==> 關卡 21 起需要的工具（Docker）"
docker_ok=0
if have docker; then
  if docker info >/dev/null 2>&1; then
    ok "docker" "$(ver docker --version)（daemon 有在跑）"
    docker_ok=1
    if docker compose version >/dev/null 2>&1; then ok "compose" "$(ver docker compose version)"; else miss "compose" "docker compose 子指令不存在，Docker Desktop / OrbStack 都內建，請更新"; docker_ok=0; fi
  else
    miss "docker" "有裝但 daemon 沒在跑：先開 Docker Desktop（或 OrbStack / colima start）"
  fi
else
  miss "docker" "沒裝。Mac：Docker Desktop（個人免費）、OrbStack（個人免費）或 brew install colima docker"
fi

echo "==> 關卡 23 需要的工具（Kubernetes）"
k8s_ok=1
for t in kind kubectl; do
  if have "$t"; then ok "$t" "$(ver "$t" version --client 2>/dev/null || ver "$t" version)"; else miss "$t" "沒裝：brew install $t"; k8s_ok=0; fi
done

echo
echo "==> 結論：這台可以做"
if [ "$base_ok" = 1 ]; then echo "  關卡 0～20：可以"; else echo "  關卡 0～20：還不行，先跑 scripts/setup.sh"; fi
if [ "$docker_ok" = 1 ]; then echo "  關卡 21、22、24（compose、E2E、指標、訊息）：可以，走 Mac 路線"; else echo "  關卡 21、22、24：不行，走 VM 路線（看 CI 的 job log）"; fi
if [ "$docker_ok" = 1 ] && [ "$k8s_ok" = 1 ]; then echo "  關卡 23（Kubernetes）：可以，走 Mac 路線"; else echo "  關卡 23：不行，走 VM 路線（看 CI 的 k8s job log）"; fi

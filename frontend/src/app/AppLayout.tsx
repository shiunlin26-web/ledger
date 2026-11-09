/**
 * 【關卡 7】所有頁面共用的外框：上方導覽列 + 提示訊息 + 頁面內容
 *
 * 在 router.tsx 裡，所有頁面都是它的子頁面，所以每一頁都會有這個導覽列。
 * <Outlet /> 的位置就是各頁面顯示的地方。
 *
 * 【關卡 15】inline style 全部改成 Tailwind class。NavLink 的 className 可以是函式，拿到 isActive 決定樣式
 */
import { useState } from "react";
import { NavLink, Outlet } from "react-router";
import { getErrorMessage } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { useMe } from "../auth/useMe";
import { Alert, Button } from "../components/ui";

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `text-sm hover:text-indigo-600 ${isActive ? "font-semibold text-indigo-600 underline underline-offset-4" : "text-zinc-600 dark:text-zinc-400"}`;

export function AppLayout() {
  const { status, notice, logout } = useAuth();
  // 【關卡 12】使用者資料改從 TanStack Query 拿（沒登入時 useMe 不會發請求，data 是 undefined）
  const { data: me } = useMe();
  const [error, setError] = useState("");

  const handleLogout = async () => {
    setError("");
    try {
      await logout(); // 登出後 status 變成 unauthenticated，RequireAuth 會自動導到 /login
    } catch (e) {
      setError(getErrorMessage(e));
    }
  };

  return (
    <div className="mx-auto max-w-md px-4 py-8 sm:py-12">
      <header className="mb-6">
        <h1 className="mb-3 text-2xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
          Ledger
        </h1>
        <nav className="flex flex-wrap items-center gap-4">
          {status === "authenticated" && (
            <>
              <NavLink to="/" end className={navLinkClass}>
                首頁
              </NavLink>
              <NavLink to="/settings" className={navLinkClass}>
                帳號設定
              </NavLink>
              <span className="ml-auto max-w-48 truncate text-sm text-zinc-500">{me?.email}</span>
              <Button variant="secondary" onClick={handleLogout}>
                登出
              </Button>
            </>
          )}
          {status === "unauthenticated" && (
            <>
              <NavLink to="/login" className={navLinkClass}>
                登入
              </NavLink>
              <NavLink to="/register" className={navLinkClass}>
                註冊
              </NavLink>
            </>
          )}
        </nav>
      </header>

      {notice && <Alert tone="info">{notice}</Alert>}
      {error && <Alert>{error}</Alert>}

      <main>
        <Outlet />
      </main>
    </div>
  );
}

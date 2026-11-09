/**
 * 【關卡 7】「只給未登入的人看」的頁面守門員（登入頁、註冊頁）
 *
 * 已經登入的人進到 /login，直接送回首頁（或原本想去的頁面）。
 * 登入成功時也是靠這個：登入後 status 變成 authenticated，這裡就自動把人導走，
 * 所以 LoginForm 裡不需要自己寫「登入後跳轉」。
 */
import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "./useAuth";

export function GuestOnly() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <p className="text-sm text-zinc-500">載入中...</p>;
  }

  if (status === "authenticated") {
    // RequireAuth 導過來時有記住原本想去的頁面，有的話就回去那裡
    const from = (location.state as { from?: string } | null)?.from ?? "/";
    return <Navigate to={from} replace />;
  }

  return <Outlet />;
}

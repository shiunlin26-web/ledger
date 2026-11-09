/**
 * 【關卡 7】「需要登入」的頁面守門員
 *
 * 在 router.tsx 裡，把需要登入的頁面放在它底下：
 *   { element: <RequireAuth />, children: [ 首頁, 設定頁 ] }
 *
 * - 還在確認登入狀態 → 顯示「載入中」
 * - 沒登入 → 導到 /login，並記住「原本想去哪一頁」，登入後再帶回來
 * - 已登入 → <Outlet /> 顯示裡面的頁面
 */
import { Navigate, Outlet, useLocation } from "react-router";
import { useAuth } from "./useAuth";

export function RequireAuth() {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return <p className="text-sm text-zinc-500">載入中...</p>;
  }

  if (status === "unauthenticated") {
    // replace：取代目前這一筆瀏覽紀錄，按「上一頁」不會又回到這個進不去的頁面
    // state：附帶資料給下一頁，這裡記住原本想去的路徑
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  // <Outlet /> 是「子頁面要顯示在這裡」的佔位符
  return <Outlet />;
}

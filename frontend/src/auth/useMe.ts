/**
 * 【關卡 12】目前登入的使用者資料，改由 TanStack Query 管
 *
 * 第 8 關：user 放在 Zustand store，login / initializeAuth / reloadUser 各自呼叫 getMe() 再 setUser()。
 * 第 12 關：只宣告「這份資料叫 ["me"]，用 getMe() 抓」，什麼時候抓、抓到存哪、載入中、錯誤、重抓，套件處理。
 *
 * 元件裡這樣用：
 *   const { data: me, isPending, error, refetch } = useMe();
 *
 * 跟 useAuth() 的分工：useAuth 給「登入狀態與動作」（status、login、logout），useMe 給「使用者資料」。
 */
import { useQuery } from "@tanstack/react-query";
import { getMe } from "../api/auth";
import { selectStatus, useAuthStore } from "./authStore";

// query key：快取裡的「名字」。同一個 key 的資料在所有元件之間共用，只會抓一次。
// 之後要手動讓它過期（例如改了資料後）：queryClient.invalidateQueries({ queryKey: meQueryKey })
export const meQueryKey = ["me"] as const;

export function useMe() {
  const status = useAuthStore(selectStatus);

  return useQuery({
    queryKey: meQueryKey,
    queryFn: getMe, // 走 api（axios 攔截器）：token 過期會自動 refresh 再重送
    // 沒登入就不要抓：否則一打開網頁就送出一個註定 401 的 /me。
    // 登入成功後 status 變成 authenticated，這個 query 自動開始抓，不用在 login() 裡手動呼叫 getMe()
    enabled: status === "authenticated",
  });
}

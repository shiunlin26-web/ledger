/**
 * 【關卡 12】TanStack Query 的「快取」本體
 *
 * 第 8 關把 user 存在 Zustand store，每次要更新都得自己呼叫 getMe() 再 setUser()。
 * 但 user 不是前端的狀態，它是「後端資料的一份副本」。副本會過期、要重抓、抓的時候要顯示載入中、
 * 失敗要顯示錯誤……這些事每一種後端資料都要做一遍，TanStack Query 就是把這套流程包好的套件。
 *
 * 分工（跟第 8 關的 store 對照）：
 *   Zustand（authStore）  → 「前端自己的狀態」：accessToken、initialized、notice
 *   TanStack Query（這裡） → 「後端資料的快取」：user，之後練習專案的 todo、category……
 */
import { QueryClient } from "@tanstack/react-query";
import { useAuthStore } from "../auth/authStore";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 抓回來的資料 30 秒內算「新鮮」，期間再 mount 同一個 query 直接用快取、不重抓。
      // 預設是 0（永遠算過期），每次切回分頁、每個元件 mount 都重抓，對這個專案太頻繁。
      staleTime: 30_000,
      // 失敗重試 1 次（預設 3 次）。401 已經由 axios 攔截器處理過（refresh 再重送），
      // 走到這裡的失敗通常是後端掛了或網路斷了，重試太多次只是拖長「載入中」。
      retry: 1,
    },
  },
});

// 登出（或登入過期）時把快取清掉。
// 理由：快取的 key 是 ["me"]，不含使用者 id。A 登出、B 登入，如果快取還在，B 會先看到 A 的資料一瞬間。
// 不寫在 logout 裡而是「訂閱 store」，是因為清 token 的地方有三個（logout、logoutAll、axios 攔截器 refresh 失敗），
// 盯著「token 從有變沒有」這一件事，三條路都不會漏。
useAuthStore.subscribe((state, prev) => {
  if (prev.accessToken && !state.accessToken) {
    queryClient.clear();
  }
});

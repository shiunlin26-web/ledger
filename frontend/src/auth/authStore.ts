/**
 * 【關卡 8】登入狀態的「倉庫」（Zustand store）
 *
 * 取代第 6 關的兩樣手寫東西：
 * - client.ts 裡的 `let accessToken` + 手寫的訂閱機制（subscribeAccessToken）
 * - AuthContext + AuthProvider 裡的 useState
 *
 * Zustand 的 store 有兩種用法：
 * - 在元件裡：useAuthStore((s) => s.user)  → 資料一變，元件自動重新渲染（取代手寫的訂閱）
 * - 在元件外：useAuthStore.getState()       → 直接讀寫，axios 攔截器就是這樣拿 token 的
 *
 * 這裡只放「資料」和「改資料的小函式」，登入、登出等流程放在 authService.ts。
 *
 * 【關卡 12】user 搬走了。它是「後端資料的副本」，交給 TanStack Query 管（auth/useMe.ts）。
 * 這裡只剩「前端自己的狀態」：token、初始化了沒、提示文字。
 */
import { create } from "zustand";

export type AuthStatus =
  | "loading" // App 剛啟動，正在用 refresh token 檢查是否已登入
  | "authenticated" // 已登入
  | "unauthenticated"; // 未登入

type AuthState = {
  initialized: boolean; // App 啟動時的登入檢查做完了沒
  accessToken: string | null; // 存在記憶體（store 也是記憶體），重新整理就消失
  notice: string; // 登入、登出等狀態變化的提示文字

  setAccessToken: (token: string | null) => void;
  setNotice: (notice: string) => void;
  setInitialized: () => void;
  /** 登出時共同要做的事：清掉 token，顯示提示（query 快取由 api/queryClient.ts 訂閱 store 自己清） */
  clearSession: (notice: string) => void;
};

// create() 建立 store：傳入一個函式，回傳初始資料和改資料的方法
// set({...}) 只會改有寫到的欄位，其他欄位保持原樣（跟 React 的 setState 一樣）
export const useAuthStore = create<AuthState>()((set) => ({
  initialized: false,
  accessToken: null,
  notice: "",

  setAccessToken: (accessToken) => set({ accessToken }),
  setNotice: (notice) => set({ notice }),
  setInitialized: () => set({ initialized: true }),
  clearSession: (notice) => set({ accessToken: null, notice }),
}));

/**
 * 從 store 的資料算出登入狀態（第 6 關的原則：能算出來的就不另外存）
 * 有 token 就是已登入，不可能出現「token 清掉了，狀態還是已登入」
 */
export function selectStatus(state: AuthState): AuthStatus {
  if (!state.initialized) return "loading";
  return state.accessToken ? "authenticated" : "unauthenticated";
}

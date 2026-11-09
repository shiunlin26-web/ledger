/**
 * 【關卡 8】登入相關的「動作」：初始化、登入、登出……
 *
 * 原本寫在 AuthProvider.tsx 裡（第 6 關），現在搬成一般的函式。
 * 因為 Zustand 的 store 在 React 外面也能讀寫，這些函式不需要放在元件裡。
 *
 * 分工：
 *   authStore.ts   → 存資料（token、notice）
 *   authService.ts → 做事情（呼叫 API，然後更新 store）
 *   useAuth.ts     → 給元件用的 hook，把兩者包在一起
 *
 * 【關卡 12】這裡不再呼叫 getMe()。登入成功只要把 token 放進 store，
 * useMe() 看到 status 變成 authenticated 就會自己去抓使用者資料。reloadUser 也不需要了（改用 query 的 refetch）。
 */
import * as authApi from "../api/auth";
import { refreshAccessToken } from "../api/client";
import { useAuthStore } from "./authStore";

// 取得 store 裡改資料的函式（在 React 外面用 getState()）
const store = () => useAuthStore.getState();

/**
 * App 啟動時呼叫一次（在 main.tsx）：
 * 用 cookie 裡的 refresh token 換 access token，換得到就代表之前登入過
 *
 * 第 6 關放在 useEffect 裡，還要用 didInit 擋掉 StrictMode 跑兩次的問題；
 * 現在是一般函式，在 main.tsx 呼叫一次就好，不會被 React 重複執行。
 */
export async function initializeAuth(): Promise<void> {
  try {
    const token = await refreshAccessToken();
    if (token) {
      store().setAccessToken(token);
    }
  } catch {
    // 沒登入過或網路錯誤，維持未登入狀態
  } finally {
    store().setInitialized();
  }
}

export async function login(email: string, password: string): Promise<void> {
  store().setNotice("");
  const { access_token } = await authApi.login(email, password); // 失敗會丟出錯誤，交給元件顯示
  store().setAccessToken(access_token);
  store().setNotice("登入成功");
}

export async function logout(): Promise<void> {
  await authApi.logout();
  store().clearSession("已登出");
}

export async function logoutAll(): Promise<void> {
  await authApi.logoutAll();
  store().clearSession("已登出所有裝置");
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  store().setNotice("");
  const { access_token } = await authApi.changePassword(currentPassword, newPassword);
  store().setAccessToken(access_token); // 後端撤銷了所有 refresh token，並發新的給這台裝置
  store().setNotice("密碼已更新，其他裝置都已登出");
}

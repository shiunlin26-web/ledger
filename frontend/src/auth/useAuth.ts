/**
 * 【關卡 6】在任何元件裡取得登入狀態：
 *   const { status, login, logout } = useAuth();
 *
 * 【關卡 8】背後從 AuthContext 換成 Zustand，但用法完全一樣，所以元件一行都不用改。
 * 也不再需要在 main.tsx 包 <AuthProvider>：Zustand 的 store 不需要 Provider。
 *
 * 【關卡 12】user 和 reloadUser 從這裡拿掉了。使用者資料改用 useMe()（auth/useMe.ts）：
 *   const { data: me, refetch } = useMe();
 */
import { useShallow } from "zustand/react/shallow";
import * as authService from "./authService";
import { selectStatus, useAuthStore } from "./authStore";

export function useAuth() {
  // useAuthStore(選擇器)：從 store 挑出需要的資料，這些資料一變，元件就重新渲染
  // useShallow：挑出好幾個欄位組成物件時要加，不然每次都是「新物件」，會一直重新渲染
  const state = useAuthStore(
    useShallow((s) => ({
      status: selectStatus(s),
      accessToken: s.accessToken,
      notice: s.notice,
    })),
  );

  return {
    ...state,
    login: authService.login,
    logout: authService.logout,
    logoutAll: authService.logoutAll,
    changePassword: authService.changePassword,
  };
}

/**
 * 【關卡 8】API 的底層，改用 axios
 *
 * 第 6 關手寫的 apiFetch，換成 axios 的「攔截器（interceptor）」：
 * - 請求攔截器：每個請求送出前，自動加上 Authorization header
 * - 回應攔截器：收到 401 時，自動 refresh 再重送一次
 *
 * 有兩個 axios 實例（instance）：
 * - publicApi：不需要登入的 API（登入、註冊、refresh、登出），沒有攔截器
 * - api：需要登入的 API，有攔截器
 * 對應第 6 關的「一般 fetch」和「apiFetch」。
 */
import axios, { type AxiosError, type InternalAxiosRequestConfig } from "axios";
import { useAuthStore } from "../auth/authStore";

// 【關卡 10】預設打「自己網域的 /api」，不直接打後端網址。
// 本機：Vite 的 server.proxy 把 /api/* 轉到 http://localhost:8000（vite.config.ts）
// 正式：Vercel 的 rewrites 把 /api/* 轉到 Render（vercel.json）
// 兩邊對瀏覽器來說都是「同一個網站」，refresh cookie 才會被帶上。
// VITE_API_URL 留著當逃生口：想直接打後端（例如除錯）時才設定。
export const API_URL: string = import.meta.env.VITE_API_URL ?? "/api";

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

// axios.create：建立一個有預設設定的 axios，之後呼叫時只要寫路徑
//   baseURL：自動加在路徑前面，api.get("/me") 會送到 /api/me
//   withCredentials：跨網域時也帶上 cookie（等於 fetch 的 credentials: "include"）。
//     同站之後其實用不到，留著是為了 VITE_API_URL 直接打後端的情況
// axios 會自動把物件轉成 JSON 送出、把回應的 JSON 轉成物件，也不用自己寫 Content-Type
export const publicApi = axios.create({ baseURL: API_URL, withCredentials: true });
export const api = axios.create({ baseURL: API_URL, withCredentials: true });

// ============================================================
// refresh：用 cookie 裡的 refresh token 換新的 access token
// ============================================================
// 【關卡 1】single-flight：同一時間只送出一個 refresh 請求。
// 這個 axios 不會幫你做，所以保留手寫的版本（邏輯跟第 6 關一模一樣）。

let refreshPromise: Promise<string | null> | null = null;

export function refreshAccessToken(): Promise<string | null> {
  if (!refreshPromise) {
    refreshPromise = publicApi
      .post<TokenResponse>("/auth/refresh")
      .then((res) => res.data.access_token)
      .catch(() => null) // 401 或網路錯誤都當作 refresh 失敗
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

// ============================================================
// 請求攔截器：送出前自動帶上 access token
// ============================================================
api.interceptors.request.use((config) => {
  // 在 React 外面讀 Zustand store：getState()
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// ============================================================
// 回應攔截器：401 → refresh → 重送
// ============================================================
// _retry：標記「這個請求已經重送過了」，避免重送後又 401 時無限循環
type RetryableConfig = InternalAxiosRequestConfig & { _retry?: boolean };

api.interceptors.response.use(
  // 成功的回應：原封不動交出去
  (response) => response,
  // 失敗的回應（axios 遇到 4xx、5xx 會自動當成錯誤）
  async (error: AxiosError) => {
    const original = error.config as RetryableConfig | undefined;

    // 不是 401，或已經重送過了 → 不處理，把錯誤往外丟
    if (error.response?.status !== 401 || !original || original._retry) {
      throw error;
    }
    original._retry = true;

    const newToken = await refreshAccessToken();
    if (!newToken) {
      // refresh 也失敗（refresh token 過期或被撤銷）→ 登入過期
      useAuthStore.getState().clearSession("登入已過期，請重新登入");
      throw error;
    }

    useAuthStore.getState().setAccessToken(newToken);
    original.headers.Authorization = `Bearer ${newToken}`;
    return api(original); // 用新 token 重送原本的請求
  },
);

// ============================================================
// 錯誤訊息
// ============================================================

/**
 * 把後端的 detail 整理成人看得懂的文字
 * - 一般錯誤：detail 是字串，例如 "Incorrect email or password"
 * - 422 驗證錯誤：detail 是陣列，每一項的 msg 是錯誤原因
 */
function formatDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item: { msg?: string }) => (item.msg ?? "").replace(/^Value error, /, ""))
      .join("；");
  }
  return "發生未知錯誤";
}

/** 從任何錯誤取出要顯示給使用者的文字 */
export function getErrorMessage(error: unknown): string {
  // axios 的錯誤：後端有回應的話，從回應內容的 detail 取訊息
  if (axios.isAxiosError<{ detail?: unknown }>(error)) {
    const detail = error.response?.data?.detail;
    if (detail !== undefined) return formatDetail(detail);
    return error.message; // 沒有回應（例如網路斷線、後端沒開）
  }
  if (error instanceof Error) return error.message;
  return String(error);
}

/**
 * 【關卡 6】所有跟登入有關的 API，一個後端端點對應一個函式
 * 【關卡 8】改用 axios：不用自己寫 JSON.stringify、res.json()、判斷 res.ok
 *
 * axios 回傳的是一個物件，後端給的資料在 .data 裡：
 *   const { data } = await api.get<User>("/me");   // data 的型別就是 User
 * 後端回 4xx、5xx 時，axios 會直接丟出錯誤，交給呼叫的地方 catch。
 */
import { api, publicApi, type TokenResponse } from "./client";

// 對應後端 schemas.py 的 UserRead
export type User = {
  id: number;
  email: string;
  created_at: string;
  last_login_at: string | null;
};

// ---------- 不需要登入的 API：用 publicApi ----------
// 登入一定要用 publicApi：密碼錯誤的 401 不能被當成 token 過期而跑去 refresh

export async function register(email: string, password: string): Promise<User> {
  const { data } = await publicApi.post<User>("/auth/register", { email, password });
  return data;
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  const { data } = await publicApi.post<TokenResponse>("/auth/login", { email, password });
  return data;
}

export async function logout(): Promise<void> {
  // 靠 cookie 找到要刪的 refresh token，不需要 access token
  await publicApi.post("/auth/logout");
}

// ---------- 需要登入的 API：用 api（自動帶 token、自動 refresh）----------

export async function getMe(): Promise<User> {
  const { data } = await api.get<User>("/me");
  return data;
}

export async function logoutAll(): Promise<void> {
  await api.post("/auth/logout-all");
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<TokenResponse> {
  const { data } = await api.post<TokenResponse>("/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
  return data;
}

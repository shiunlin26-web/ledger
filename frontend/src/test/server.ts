/**
 * 【關卡 16】MSW（Mock Service Worker）：假的後端
 *
 * 測試不該依賴真的後端（要起 uvicorn、要資料庫、網路慢、資料會互相污染）。
 * MSW 在「網路層」攔截請求：axios 照常送出請求，MSW 接住並回傳你指定的內容，程式碼一行都不用改。
 * 這和後端測試用 TEST_DATABASE_URL 隔離資料庫是同一個精神：測的是你的程式，不是別人的服務。
 *
 * 這裡只放「預設」的 handler（正常回應）。個別測試要模擬 401、500 時，用 server.use(...) 蓋掉，
 * afterEach 會還原（setup.ts）。
 */
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import type { User } from "../api/auth";

export const fakeUser: User = {
  id: 1,
  email: "test@example.com",
  created_at: "2026-01-01T00:00:00Z",
  last_login_at: null,
};

// 路徑用 */api/... 開頭：axios 的 baseURL 是相對的 /api，jsdom 會補成 http://localhost:3000/api/...，* 代表不管主機是什麼
export const handlers = [
  http.get("*/api/me", () => HttpResponse.json(fakeUser)),
  http.post("*/api/auth/refresh", () =>
    HttpResponse.json({ access_token: "refreshed-token", token_type: "bearer" }),
  ),
  http.post("*/api/auth/login", () =>
    HttpResponse.json({ access_token: "login-token", token_type: "bearer" }),
  ),
  http.post("*/api/auth/logout", () => new HttpResponse(null, { status: 204 })),
];

export const server = setupServer(...handlers);

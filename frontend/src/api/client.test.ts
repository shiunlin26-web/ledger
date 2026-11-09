/**
 * 【關卡 16】測 axios 攔截器：401 → refresh → 重送、single-flight、refresh 失敗
 *
 * 這些是第 1、6、8 關手動在 Network 分頁驗證過的行為，現在寫成程式，改攔截器時跑一次就知道有沒有壞。
 * 和後端 test_auth.py 的「舊的 refresh token 再被使用會撤銷全部」是同一件事的兩端。
 */
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAuthStore } from "../auth/authStore";
import { fakeUser, server } from "../test/server";
import { getMe } from "./auth";

/** 讓 /me 只接受某個 token，其他都 401；回傳計數器方便 assert 呼叫次數 */
function acceptOnly(validToken: string) {
  const calls = { me: 0, refresh: 0 };
  server.use(
    http.get("*/api/me", ({ request }) => {
      calls.me += 1;
      return request.headers.get("Authorization") === `Bearer ${validToken}`
        ? HttpResponse.json(fakeUser)
        : HttpResponse.json({ detail: "Invalid or expired token" }, { status: 401 });
    }),
    http.post("*/api/auth/refresh", () => {
      calls.refresh += 1;
      return HttpResponse.json({ access_token: validToken, token_type: "bearer" });
    }),
  );
  return calls;
}

describe("axios 攔截器", () => {
  it("每個請求自動帶上 store 裡的 access token", async () => {
    useAuthStore.setState({ accessToken: "good" });
    const calls = acceptOnly("good");

    await expect(getMe()).resolves.toEqual(fakeUser);
    expect(calls).toEqual({ me: 1, refresh: 0 });
  });

  it("401 → refresh → 用新 token 重送，呼叫端完全沒感覺", async () => {
    useAuthStore.setState({ accessToken: "expired" });
    const calls = acceptOnly("fresh");

    await expect(getMe()).resolves.toEqual(fakeUser);
    expect(calls).toEqual({ me: 2, refresh: 1 }); // 第一次 401、refresh、第二次 200
    expect(useAuthStore.getState().accessToken).toBe("fresh"); // 新 token 寫進 store
  });

  it("single-flight：同時三個請求 401，只送一次 refresh", async () => {
    useAuthStore.setState({ accessToken: "expired" });
    const calls = acceptOnly("fresh");

    const results = await Promise.all([getMe(), getMe(), getMe()]);

    expect(results).toHaveLength(3);
    expect(calls.refresh).toBe(1); // 沒有 single-flight 會是 3，而且後兩次會觸發後端的重複使用偵測
    expect(calls.me).toBe(6); // 3 次 401 + 3 次重送
  });

  it("refresh 也失敗 → 清掉登入狀態、顯示提示", async () => {
    useAuthStore.setState({ accessToken: "expired", initialized: true });
    server.use(
      http.get("*/api/me", () => HttpResponse.json({ detail: "expired" }, { status: 401 })),
      http.post("*/api/auth/refresh", () =>
        HttpResponse.json({ detail: "No refresh token" }, { status: 401 }),
      ),
    );

    await expect(getMe()).rejects.toThrow();
    expect(useAuthStore.getState().accessToken).toBeNull();
    expect(useAuthStore.getState().notice).toBe("登入已過期，請重新登入");
  });

  it("_retry：重送後還是 401 就放棄，不會無限 refresh", async () => {
    useAuthStore.setState({ accessToken: "expired" });
    let refreshCalls = 0;
    server.use(
      http.get("*/api/me", () => HttpResponse.json({ detail: "still bad" }, { status: 401 })),
      http.post("*/api/auth/refresh", () => {
        refreshCalls += 1;
        return HttpResponse.json({ access_token: "fresh", token_type: "bearer" });
      }),
    );

    await expect(getMe()).rejects.toThrow();
    expect(refreshCalls).toBe(1); // 拿掉 client.ts 的 _retry，這裡會變成無限循環（測試會 timeout）
  });
});

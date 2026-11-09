/**
 * 【關卡 16】每個測試檔開始前自動執行（vitest.config.ts 的 setupFiles），相當於後端的 conftest.py
 *
 * 做三件事：
 * 1. 加 jest-dom 的 matcher：expect(element).toBeInTheDocument()、toBeDisabled() 這些
 * 2. 啟動 MSW 假後端；每個測試後把個別測試覆蓋的 handler 還原（和後端「每個測試前清空資料表」同一個精神）
 * 3. 每個測試後把 Zustand store、TanStack Query 快取、畫面清乾淨，測試之間不互相影響
 */
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { queryClient } from "../api/queryClient";
import { useAuthStore } from "../auth/authStore";
import { server } from "./server";

// onUnhandledFrame: "error"：有請求沒有對應的 handler 就讓測試失敗，不會默默打到真的網路
// （MSW 2 叫 onUnhandledRequest，v3 改名；網路上的教學大多還是舊名字）
beforeAll(() => server.listen({ onUnhandledFrame: "error" }));

afterEach(() => {
  server.resetHandlers();
  cleanup();
  queryClient.clear();
  useAuthStore.setState({ initialized: false, accessToken: null, notice: "" });
});

afterAll(() => server.close());

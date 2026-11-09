import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router";
import "./index.css";
import { queryClient } from "./api/queryClient.ts";
import { router } from "./app/router.tsx";
import { initializeAuth } from "./auth/authService.ts";

// 【關卡 8】App 啟動時檢查一次登入狀態（用 refresh token 換 access token）
// 不用 await：先把畫面畫出來（顯示「載入中」），檢查完 store 更新，畫面自動跟著變
initializeAuth();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* 【關卡 12】QueryClientProvider：讓底下所有元件的 useQuery 共用同一份快取（api/queryClient.ts） */}
    {/* Zustand 不需要 Provider，TanStack Query 需要：它的快取要跟著 React 樹的生命週期，而且測試時要能換一份乾淨的 */}
    <QueryClientProvider client={queryClient}>
      {/* 【關卡 7】RouterProvider：依網址顯示 router.tsx 裡對應的頁面 */}
      {/* 【關卡 8】不再需要 <AuthProvider>：登入狀態改放在 Zustand store，不需要 Provider */}
      <RouterProvider router={router} />
      {/* 【關卡 12】右下角的小圖示，點開可以看每個 query 的狀態（fresh / stale / fetching）和快取內容。正式 build 會自動拿掉 */}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  </StrictMode>,
);

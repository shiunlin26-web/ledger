/** 【關卡 16】測守門員：三種登入狀態各導去哪 */
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it } from "vitest";
import { useAuthStore } from "./authStore";
import { RequireAuth } from "./RequireAuth";

/** 用記憶體裡的路由表 render：/ 需要登入，/login 不用 */
function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route element={<RequireAuth />}>
          <Route path="/" element={<p>祕密頁面</p>} />
          <Route path="/settings" element={<p>設定頁面</p>} />
        </Route>
        <Route path="/login" element={<p>登入頁面</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("RequireAuth", () => {
  it("還在確認登入狀態時顯示載入中，不會先導走", () => {
    useAuthStore.setState({ initialized: false });
    renderAt("/");
    expect(screen.getByText("載入中...")).toBeInTheDocument();
    expect(screen.queryByText("登入頁面")).not.toBeInTheDocument();
  });

  it("未登入 → 導到 /login", () => {
    useAuthStore.setState({ initialized: true, accessToken: null });
    renderAt("/settings");
    expect(screen.getByText("登入頁面")).toBeInTheDocument();
  });

  it("已登入 → 顯示頁面", () => {
    useAuthStore.setState({ initialized: true, accessToken: "token" });
    renderAt("/");
    expect(screen.getByText("祕密頁面")).toBeInTheDocument();
  });
});

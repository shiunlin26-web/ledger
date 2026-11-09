/**
 * 【關卡 7】所有頁面的路由表：哪個網址顯示哪個頁面、哪些頁面要登入
 *
 * 結構是一棵樹：外層的 element 會包住裡面的 children。
 *
 *   AppLayout（導覽列）
 *   ├── GuestOnly（只給未登入的人）
 *   │   ├── /login      LoginPage
 *   │   └── /register   RegisterPage
 *   ├── RequireAuth（需要登入）
 *   │   ├── /           HomePage
 *   │   └── /settings   SettingsPage
 *   └── *（其他網址）   NotFoundPage
 *
 * 新增頁面：在 pages/ 建立元件，然後加到對應的 children 裡。
 */
import { createBrowserRouter } from "react-router";
import { GuestOnly } from "../auth/GuestOnly";
import { RequireAuth } from "../auth/RequireAuth";
import { HomePage } from "../pages/HomePage";
import { LoginPage } from "../pages/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { RegisterPage } from "../pages/RegisterPage";
import { SettingsPage } from "../pages/SettingsPage";
import { AppLayout } from "./AppLayout";

export const router = createBrowserRouter([
  {
    element: <AppLayout />,
    children: [
      {
        element: <GuestOnly />,
        children: [
          { path: "/login", element: <LoginPage /> },
          { path: "/register", element: <RegisterPage /> },
        ],
      },
      {
        element: <RequireAuth />,
        children: [
          { path: "/", element: <HomePage /> },
          { path: "/settings", element: <SettingsPage /> },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);

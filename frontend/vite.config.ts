import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  // 【關卡 15】Tailwind v4 用 Vite 外掛接進來，不需要 tailwind.config.js 和 PostCSS 設定
  plugins: [react(), tailwindcss()],
  build: {
    // 【關卡 15】把 node_modules 裡的套件切成獨立的 chunk（vendor）。
    // 理由有二：(1) 套件很少變，切開後使用者的瀏覽器可以一直用快取，只重新下載你改過的那一小塊；
    // (2) 所有東西包成一個檔案超過 500 kB 時 Vite 會警告，專業的 repo 不留警告。
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: "react",
              test: /node_modules[\\/](react|react-dom|react-router|scheduler)[\\/]/,
            },
            { name: "vendor", test: /node_modules/ },
          ],
        },
      },
    },
  },
  server: {
    // 【關卡 10】本機的「反向代理」：瀏覽器打 http://localhost:5173/api/...，
    // Vite 收到後轉發給 http://localhost:8000/api/...，再把回應（含 Set-Cookie）原封不動送回瀏覽器。
    // 對瀏覽器來說前後端是同一個網站，所以：不需要 CORS、cookie 直接帶上、localhost 和 127.0.0.1 都能用。
    // 正式環境由 Vercel 的 rewrites 做同一件事（vercel.json）。
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});

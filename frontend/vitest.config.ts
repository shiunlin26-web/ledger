/**
 * 【關卡 16】Vitest 的設定：沿用 vite.config.ts（同一套外掛、同一套路徑解析），只加測試相關的部分
 *
 * Vitest 和 pytest 的對照：
 *   pytest.ini / conftest.py → 這個檔案 + src/test/setup.ts
 *   TEST_DATABASE_URL 的測試資料庫 → MSW 假後端（src/test/server.ts），不需要真的後端
 */
import { configDefaults, defineConfig, mergeConfig } from "vitest/config";
import viteConfig from "./vite.config.ts";

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      // jsdom：在 Node 裡模擬瀏覽器的 document、window、XMLHttpRequest，React 元件才能 render
      environment: "jsdom",
      // 每個測試檔跑之前先執行的東西：jest-dom 的 matcher、MSW 的啟動與重設
      setupFiles: ["./src/test/setup.ts"],
      // 測試不需要真的處理 Tailwind 的 CSS
      css: false,
      // 【關卡 21】e2e/ 裡的 *.spec.ts 是 Playwright 的，不是 Vitest 的（檔名規則一樣，所以要明講排除）
      exclude: [...configDefaults.exclude, "e2e/**"],
      coverage: { provider: "v8", reporter: ["text"], include: ["src/**/*.{ts,tsx}"] },
    },
  }),
);

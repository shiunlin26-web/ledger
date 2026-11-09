/**
 * 【關卡 14】表單的驗證規則，用 Zod 寫成 schema
 *
 * 取代第 0 關手寫的 utils/password.ts。差別：
 * - 手寫版：一個 if 一條規則，只能回傳一句錯誤訊息；型別要另外宣告
 * - Zod：規則寫成資料（schema），同一份 schema 同時產生 TypeScript 型別（z.infer）和執行期驗證。
 *   後端 schemas.py 的 Pydantic 做的是一模一樣的事，Zod 就是前端的 Pydantic
 *
 * 規則要和後端 schemas.py 一致。前端檢查只是為了即時提示，真正把關的是後端（前端檢查可以被繞過）。
 */
import { z } from "zod";

export const PASSWORD_HINT = "8～72 個英文字母、數字或符號";

// 【關卡 0】8～72 個可列印 ASCII 字元（\x20 是空白，\x7E 是 ~），理由見後端 schemas.py
export const passwordSchema = z
  .string()
  .regex(/^[\x20-\x7E]*$/, "密碼只能包含英文字母、數字、空白與符號")
  .min(8, "密碼至少 8 個字元")
  .max(72, "密碼最多 72 個字元");

// 登入：只要有填就好。密碼規則只在「設定密碼」時檢查（關卡 0：規則改了，舊規則註冊的人還是要能登入）
export const loginSchema = z.object({
  email: z.string().trim().min(1, "請輸入 Email"),
  password: z.string().min(1, "請輸入密碼"),
});

export const registerSchema = z.object({
  email: z.email("Email 格式不正確"),
  password: passwordSchema,
});

// refine：跨欄位的規則（兩個欄位一起看）。path 指定錯誤要掛在哪個欄位上
export const changePasswordSchema = z
  .object({
    currentPassword: z.string().min(1, "請輸入目前密碼"), // 不套規則，理由同登入
    newPassword: passwordSchema,
  })
  .refine((data) => data.currentPassword !== data.newPassword, {
    message: "新密碼不能和目前密碼相同", // 後端也會擋（400），這裡只是提早提示
    path: ["newPassword"],
  });

// z.infer：從 schema 推出 TypeScript 型別，不用再手寫一份 type，兩邊永遠一致
export type LoginInput = z.infer<typeof loginSchema>;
export type RegisterInput = z.infer<typeof registerSchema>;
export type ChangePasswordInput = z.infer<typeof changePasswordSchema>;

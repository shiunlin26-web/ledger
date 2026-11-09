/**
 * 【關卡 6】登入表單（關卡 7：註冊拆到 RegisterForm，各自一個頁面）
 *
 * 【關卡 14】改用 React Hook Form + Zod。對照第 6 關的手寫版：
 *   useState 一個欄位一個       → useForm 一次管所有欄位
 *   onChange={(e) => setX(...)}  → {...register("x")}
 *   手算 canLogin               → formState.isValid（由 zod schema 決定）
 *   event.preventDefault()      → handleSubmit 幫你做
 *
 * 【關卡 15】後端回的錯誤（密碼錯）留在元件自己的 useState，不用 setError("root")：
 * setError 會把 isValid 設成 false，按鈕會灰掉直到使用者改了某個欄位，想用同一組帳密重試（例如剛才網路斷線）做不到。
 * 原則：表單狀態只管「欄位」，伺服器的回應是另一回事。
 */
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { getErrorMessage } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { loginSchema, type LoginInput } from "../schemas/auth";
import { Alert, Button, TextInput } from "./ui";

export function LoginForm({ defaultEmail = "" }: { defaultEmail?: string }) {
  const { login } = useAuth();
  const [serverError, setServerError] = useState("");
  const {
    register, // 把 input 接上表單：register("email") 回傳 name、onChange、onBlur、ref
    handleSubmit, // 先跑 zod 驗證，全部通過才呼叫你的 onSubmit
    formState: { isValid, isSubmitting },
  } = useForm<LoginInput>({
    resolver: zodResolver(loginSchema), // 驗證規則交給 zod
    mode: "onChange", // 每次輸入都驗證，isValid 才會即時更新（預設是送出時才驗）
    defaultValues: { email: defaultEmail, password: "" },
  });

  const onSubmit = async (data: LoginInput) => {
    setServerError("");
    try {
      // 成功後 store 更新為已登入 → GuestOnly 發現已登入，自動導到首頁（或原本想去的頁面）
      await login(data.email, data.password);
    } catch (error) {
      setServerError(`登入失敗：${getErrorMessage(error)}`);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <TextInput placeholder="Email" autoComplete="email" {...register("email")} />
      <TextInput
        placeholder="Password"
        type="password"
        autoComplete="current-password"
        {...register("password")}
      />
      {/* isSubmitting：onSubmit 還在 await 時是 true，擋住連點兩次 */}
      <Button type="submit" disabled={!isValid || isSubmitting}>
        {isSubmitting ? "登入中..." : "登入"}
      </Button>
      {serverError && <Alert>{serverError}</Alert>}
    </form>
  );
}

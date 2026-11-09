/** 【關卡 7】註冊表單（從原本的 LoginForm 拆出來）；【關卡 14】改用 React Hook Form + Zod */
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { register as registerUser } from "../api/auth"; // 改名：避免和 useForm 的 register 撞名
import { getErrorMessage } from "../api/client";
import { PASSWORD_HINT, registerSchema, type RegisterInput } from "../schemas/auth";
import { Alert, Button, Hint, TextInput } from "./ui";

/** onSuccess：註冊成功後要做什麼，由使用這個元件的頁面決定（RegisterPage 會導到登入頁） */
export function RegisterForm({ onSuccess }: { onSuccess: (email: string) => void }) {
  const [serverError, setServerError] = useState(""); // 【關卡 15】後端錯誤不進表單狀態，理由見 LoginForm
  const {
    register,
    handleSubmit,
    formState: { errors, isValid, isSubmitting },
  } = useForm<RegisterInput>({
    resolver: zodResolver(registerSchema),
    mode: "onChange",
    defaultValues: { email: "", password: "" },
  });

  const onSubmit = async (data: RegisterInput) => {
    setServerError("");
    try {
      const user = await registerUser(data.email, data.password);
      onSuccess(user.email);
    } catch (error) {
      setServerError(`註冊失敗：${getErrorMessage(error)}`);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <TextInput placeholder="Email" autoComplete="email" {...register("email")} />
      {errors.email && <Hint error>{errors.email.message}</Hint>}
      <TextInput
        placeholder="Password"
        type="password"
        autoComplete="new-password"
        {...register("password")}
      />
      {/* errors.password 是 zod 第一條沒過的規則的訊息；沒錯誤就顯示規則提示 */}
      <Hint error={errors.password !== undefined}>{errors.password?.message ?? PASSWORD_HINT}</Hint>
      <Button type="submit" disabled={!isValid || isSubmitting}>
        {isSubmitting ? "註冊中..." : "註冊"}
      </Button>
      {serverError && <Alert>{serverError}</Alert>}
    </form>
  );
}

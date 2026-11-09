/** 【關卡 6】登入後顯示：修改密碼表單；【關卡 14】改用 React Hook Form + Zod */
import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { getErrorMessage } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { PASSWORD_HINT, changePasswordSchema, type ChangePasswordInput } from "../schemas/auth";
import { Alert, Button, Hint, TextInput } from "./ui";

export function ChangePasswordForm() {
  const { changePassword } = useAuth();
  const [serverError, setServerError] = useState(""); // 【關卡 15】後端錯誤不進表單狀態，理由見 LoginForm
  const {
    register,
    handleSubmit,
    reset, // 成功後把欄位清空
    formState: { errors, isValid, isSubmitting },
  } = useForm<ChangePasswordInput>({
    resolver: zodResolver(changePasswordSchema),
    mode: "onChange",
    defaultValues: { currentPassword: "", newPassword: "" },
  });

  const onSubmit = async (data: ChangePasswordInput) => {
    setServerError("");
    try {
      await changePassword(data.currentPassword, data.newPassword);
      reset();
    } catch (error) {
      setServerError(`改密碼失敗：${getErrorMessage(error)}`);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <h3 className="mb-2 text-lg font-semibold">修改密碼</h3>
      <TextInput
        placeholder="目前密碼"
        type="password"
        autoComplete="current-password"
        {...register("currentPassword")}
      />
      <TextInput
        placeholder="新密碼"
        type="password"
        autoComplete="new-password"
        {...register("newPassword")}
      />
      <Hint error={errors.newPassword !== undefined}>
        {errors.newPassword?.message ?? PASSWORD_HINT}
      </Hint>
      <Button type="submit" disabled={!isValid || isSubmitting}>
        {isSubmitting ? "修改中..." : "修改密碼"}
      </Button>
      {serverError && <Alert>{serverError}</Alert>}
    </form>
  );
}

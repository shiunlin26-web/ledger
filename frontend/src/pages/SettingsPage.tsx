/** 【關卡 7】帳號設定頁：/settings（需要登入） */
import { useState } from "react";
import { getErrorMessage } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { ChangePasswordForm } from "../components/ChangePasswordForm";
import { Alert, Button } from "../components/ui";

export function SettingsPage() {
  const { logoutAll } = useAuth();
  const [message, setMessage] = useState("");

  const handleLogoutAll = async () => {
    setMessage("");
    try {
      await logoutAll(); // 登出後 RequireAuth 會自動導到 /login
    } catch (error) {
      setMessage(getErrorMessage(error));
    }
  };

  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold">帳號設定</h2>

      <ChangePasswordForm />

      <h3 className="mt-8 mb-1 text-lg font-semibold">登出所有裝置</h3>
      <p className="mb-2 text-sm text-zinc-500">手機遺失或在別人的電腦登入忘了登出時使用。</p>
      <Button variant="danger" onClick={handleLogoutAll}>
        登出所有裝置
      </Button>
      {message && <Alert>{message}</Alert>}
    </section>
  );
}

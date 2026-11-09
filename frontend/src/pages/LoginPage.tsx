/** 【關卡 7】登入頁：/login */
import { Link, useLocation } from "react-router";
import { LoginForm } from "../components/LoginForm";
import { Alert } from "../components/ui";

export function LoginPage() {
  // 從註冊頁跳過來時，RegisterPage 會用 navigate 的 state 帶上剛註冊的 email
  const location = useLocation();
  const registeredEmail = (location.state as { registeredEmail?: string } | null)?.registeredEmail;

  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold">登入</h2>
      {registeredEmail && <Alert tone="info">註冊成功，請登入</Alert>}
      <LoginForm defaultEmail={registeredEmail} />
      <p className="mt-4 text-sm text-zinc-500">
        還沒有帳號？
        <Link to="/register" className="text-indigo-600 underline underline-offset-4">
          註冊
        </Link>
      </p>
    </section>
  );
}

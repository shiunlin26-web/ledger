/** 【關卡 7】註冊頁：/register */
import { Link, useNavigate } from "react-router";
import { RegisterForm } from "../components/RegisterForm";

export function RegisterPage() {
  // useNavigate：用程式碼換頁（相當於點了一個連結）
  const navigate = useNavigate();

  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold">註冊</h2>
      {/* 註冊成功 → 換到登入頁，並把 email 帶過去，登入頁的 email 欄位會自動填好 */}
      <RegisterForm
        onSuccess={(email) => navigate("/login", { state: { registeredEmail: email } })}
      />
      <p className="mt-4 text-sm text-zinc-500">
        已經有帳號了？
        <Link to="/login" className="text-indigo-600 underline underline-offset-4">
          登入
        </Link>
      </p>
    </section>
  );
}

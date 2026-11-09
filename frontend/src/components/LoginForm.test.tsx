/** 【關卡 16】測登入表單：驗證擋住送出、後端的錯誤訊息會顯示、成功後 token 進 store */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { useAuthStore } from "../auth/authStore";
import { server } from "../test/server";
import { LoginForm } from "./LoginForm";

describe("LoginForm", () => {
  it("欄位沒填完之前按鈕是 disabled", async () => {
    const user = userEvent.setup();
    render(<LoginForm />);
    const button = screen.getByRole("button", { name: "登入" });

    expect(button).toBeDisabled();
    await user.type(screen.getByPlaceholderText("Email"), "a@b.com");
    expect(button).toBeDisabled(); // 密碼還沒填
    await user.type(screen.getByPlaceholderText("Password"), "x");
    expect(button).toBeEnabled();
  });

  it("密碼錯誤：顯示後端的訊息，按鈕恢復可按（可以直接重試）", async () => {
    server.use(
      http.post("*/api/auth/login", () =>
        HttpResponse.json({ detail: "Incorrect email or password" }, { status: 401 }),
      ),
    );
    const user = userEvent.setup();
    render(<LoginForm defaultEmail="a@b.com" />);

    await user.type(screen.getByPlaceholderText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "登入" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "登入失敗：Incorrect email or password",
    );
    expect(screen.getByRole("button", { name: "登入" })).toBeEnabled(); // 關卡 15 修的 bug
    expect(useAuthStore.getState().accessToken).toBeNull();
  });

  it("登入成功：token 進 store、提示登入成功", async () => {
    const user = userEvent.setup();
    render(<LoginForm defaultEmail="a@b.com" />);

    await user.type(screen.getByPlaceholderText("Password"), "correct-password");
    await user.click(screen.getByRole("button", { name: "登入" }));

    await expect.poll(() => useAuthStore.getState().accessToken).toBe("login-token");
    expect(useAuthStore.getState().notice).toBe("登入成功");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

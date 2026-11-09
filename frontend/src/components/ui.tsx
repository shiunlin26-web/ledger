/**
 * 【關卡 15】共用的小元件：輸入框、按鈕、提示、警示
 *
 * 取代第 6 關的 styles.ts（inputStyle、hintStyle）。Tailwind 的 class 很長，同一組 class 在三個表單重複貼，
 * 改一次要改三處，所以包成元件。這是 Tailwind 專案的慣例：重複的 class 組合 → 元件，不是 → 另外寫 CSS。
 *
 * React 19 起 ref 是普通的 prop，所以 {...register("email")}（裡面有 ref）直接展開到 <TextInput> 上就能用，
 * 不需要 forwardRef。
 */
import type { ComponentProps, ReactNode } from "react";

export function TextInput(props: ComponentProps<"input">) {
  return (
    <input
      {...props}
      className="mb-2 block w-full rounded-md border border-zinc-300 bg-white px-3 py-2 text-zinc-900 placeholder:text-zinc-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200 focus:outline-none dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:ring-indigo-900"
    />
  );
}

// variant 的合法值從 buttonVariants 的 key 推出來：加一種按鈕只改下面那個物件，型別自動跟上（和 Zod 的 z.infer 同一個原則：型別從定義推，不手抄）
type ButtonProps = ComponentProps<"button"> & { variant?: keyof typeof buttonVariants };

// 三種按鈕只差顏色，用 variant 切換；disabled 時變淡、游標變成禁止
const buttonVariants = {
  primary: "bg-indigo-600 text-white hover:bg-indigo-700",
  secondary:
    "border border-zinc-300 bg-white text-zinc-800 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800",
  danger: "bg-red-600 text-white hover:bg-red-700",
};

export function Button({ variant = "primary", className = "", ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={`rounded-md px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${buttonVariants[variant]} ${className}`}
    />
  );
}

/** 欄位下方的小字：規則提示（灰）或錯誤（紅） */
export function Hint({ error = false, children }: { error?: boolean; children: ReactNode }) {
  return (
    <p className={`mb-2 text-xs ${error ? "text-red-600 dark:text-red-400" : "text-zinc-500"}`}>
      {children}
    </p>
  );
}

/**
 * 整張表單或整頁的訊息。role="alert" 讓螢幕閱讀器會唸出來，也方便測試用 [role="alert"] 找到它
 */
export function Alert({
  tone = "error",
  children,
}: {
  tone?: "error" | "info";
  children: ReactNode;
}) {
  const toneClass =
    tone === "error"
      ? "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300"
      : "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300";
  return (
    <p role="alert" className={`my-2 rounded-md px-3 py-2 text-sm ${toneClass}`}>
      {children}
    </p>
  );
}

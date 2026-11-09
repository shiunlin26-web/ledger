/**
 * 【關卡 6】使用者資料（關卡 7：登出移到導覽列、登出所有裝置移到帳號設定頁）
 *
 * 【關卡 12】「手寫版 → 套件版」的對照就在這個檔案：
 *   第 8 關：useState 存錯誤訊息、自己 try/catch、reloadUser() 抓完再寫進 store，沒有「載入中」
 *   第 12 關：useMe() 一次給你 data、isPending、isFetching、error、refetch，全部由套件維護
 */
import { getErrorMessage } from "../api/client";
import { useAuth } from "../auth/useAuth";
import { useMe } from "../auth/useMe";
import { Alert, Button } from "./ui";

export function UserPanel() {
  const { accessToken } = useAuth();
  // data：抓到的使用者資料（還沒抓到是 undefined）
  // isPending：第一次抓、還沒有任何資料
  // isFetching：正在抓（包含背景重抓；這時 data 還是舊的，畫面不會閃成空白）
  // error：最後一次抓失敗的錯誤；refetch：手動重抓
  // dataUpdatedAt：上次成功抓到的時間，用來觀察「什麼時候重抓了」
  const { data: me, isPending, isFetching, error, refetch, dataUpdatedAt } = useMe();

  return (
    <div>
      {/* 學習用：顯示 access token 的前 40 個字，正式專案不需要 */}
      <p className="mb-3 text-xs break-all text-zinc-500">Token: {accessToken?.slice(0, 40)}...</p>

      <div className="flex flex-wrap items-center gap-3">
        {/* 第 8 關這顆按鈕要自己 try/catch、自己管錯誤訊息；現在只是叫 query 重抓 */}
        <Button variant="secondary" onClick={() => refetch()} disabled={isFetching}>
          {isFetching ? "更新中..." : "重新取得我的資料"}
        </Button>
        {dataUpdatedAt > 0 && (
          <span className="text-xs text-zinc-500">
            上次更新：{new Date(dataUpdatedAt).toLocaleTimeString()}
          </span>
        )}
      </div>
      {error && <Alert>{getErrorMessage(error)}</Alert>}

      {isPending && <p className="mt-3 text-sm text-zinc-500">載入中...</p>}
      {me && (
        <pre className="mt-3 overflow-x-auto rounded-md bg-zinc-100 p-3 text-sm text-zinc-800 dark:bg-zinc-900 dark:text-zinc-200">
          {JSON.stringify(me, null, 2)}
        </pre>
      )}
    </div>
  );
}

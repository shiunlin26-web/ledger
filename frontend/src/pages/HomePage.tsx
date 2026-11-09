/** 【關卡 7】首頁：/（需要登入） */
import { useMe } from "../auth/useMe";
import { UserPanel } from "../components/UserPanel";

export function HomePage() {
  // 【關卡 12】使用者資料從 useAuth().user 改成 useMe().data
  // AppLayout 也用 useMe()：同一個 query key，兩個元件共用一份快取，/me 只會抓一次
  const { data: me } = useMe();

  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold">嗨，{me?.email ?? "..."}</h2>
      <UserPanel />
    </section>
  );
}

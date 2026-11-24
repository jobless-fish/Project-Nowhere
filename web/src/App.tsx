import { useEffect, useState } from "react";
import { getSession, setSession } from "./api";
import type { Session } from "./types";
import { Avatar, Icon } from "./ui";
import Admin from "./pages/Admin";
import Chat from "./pages/Chat";
import Controls from "./pages/Controls";
import Home from "./pages/Home";
import Login from "./pages/Login";
import MailPage from "./pages/Mail";
import News from "./pages/News";
import Org from "./pages/Org";

const NAV = [
  { id: "home", label: "홈", icon: "home" }, { id: "news", label: "소식", icon: "news" },
  { id: "mail", label: "메일", icon: "mail" }, { id: "chat", label: "메신저", icon: "chat" }, { id: "org", label: "조직도", icon: "org" },
] as const;

const useRoute = () => {
  const get = () => (location.hash.replace("#/", "") || "home");
  const [r, setR] = useState(get);
  useEffect(() => { const f = () => setR(get()); addEventListener("hashchange", f); return () => removeEventListener("hashchange", f); }, []);
  return r;
};

export default function App() {
  const [session, set] = useState<Session | null>(getSession);
  const route = useRoute();
  const login = (s: Session) => { setSession(s); set(s); location.hash = "#/home"; };
  const logout = () => { setSession(null); set(null); };
  if (!session) return <Login onLogin={login} />;

  const page = { home: <Home s={session} />, news: <News s={session} />, mail: <MailPage s={session} />,
    chat: <Chat s={session} />, org: <Org s={session} />, admin: <Admin />, controls: <Controls /> }[route] ?? <Home s={session} />;
  const link = (id: string, label: string, icon: Parameters<typeof Icon>[0]["n"]) => (
    <a key={id} href={`#/${id}`} aria-current={route === id ? "page" : undefined}><Icon n={icon} />{label}</a>
  );
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">nowhere</div>
        <nav className="nav" aria-label="주 메뉴">
          {NAV.map((n) => link(n.id, n.label, n.icon))}
          <div className="sep" /><span className="label">관리</span>
          {link("admin", "관리자 콘솔", "admin")}
        </nav>
        <div className="me">
          <Avatar name={session.user.name} />
          <div style={{ minWidth: 0 }}><div className="trunc" style={{ fontWeight: 700 }}>{session.user.name}</div>
            <div className="small trunc muted">{session.user.title}</div></div>
          <button className="btn quiet" onClick={logout} aria-label="로그아웃" title="로그아웃" style={{ padding: 0, minWidth: 44 }}><Icon n="out" /></button>
        </div>
      </aside>
      <main className="main">{page}</main>
    </div>
  );
}

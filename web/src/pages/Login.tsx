import { useEffect, useState } from "react";
import { world } from "../api";
import type { Session, User } from "../types";
import { Avatar, Skeletons } from "../ui";

export default function Login({ onLogin }: { onLogin: (s: Session) => void }) {
  const [users, setUsers] = useState<User[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { fetch("/world/sso/users").then((r) => r.json()).then(setUsers).catch(() => setErr("사내 시스템에 연결할 수 없습니다. ./run_demo.sh 로 서버를 먼저 실행하세요.")); }, []);
  const pick = async (u: User) => {
    try {
      const t = await world.post<{ access_token: string }>("/sso/token", { user_id: u.id, password: "demo1234" });
      onLogin({ user: u, token: t.access_token });
    } catch { setErr("로그인에 실패했습니다."); }
  };
  return (
    <div className="login"><div className="card stack" style={{ gap: 16 }}>
      <div className="brand">nowhere</div>
      <div><h1>오늘도 어디에도 없는 곳에서</h1>
        <p className="muted" style={{ marginTop: 8 }}>가상 기업 노웨어의 업무 비서 데모예요. 로그인할 직원을 골라 주세요.</p></div>
      {err && <div className="banner" role="alert">{err}</div>}
      {!users && !err && <Skeletons n={4} />}
      <div className="stack" style={{ gap: 8 }}>
        {users?.map((u) => (
          <button key={u.id} className="user-pick" onClick={() => pick(u)}>
            <Avatar name={u.name} /><span className="grow"><b>{u.name}</b><br /><span className="small muted">{u.team} · {u.title}</span></span>
            {u.role === "executive" && <span className="badge accent">임원</span>}
          </button>
        ))}
      </div>
      <p className="small faint">노웨어는 실존하지 않는 가상의 기업이며, 모든 데이터는 가상입니다.</p>
    </div></div>
  );
}

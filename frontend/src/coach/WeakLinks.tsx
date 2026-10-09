import { Link } from "react-router-dom";
import type { TeamScope } from "../types";
import { Hint, Logo, SnapDefinition, filmUrl, teamName, useStatic, type Teams } from "./shared";

interface WeakLinksData {
  positions: [string, number, number][];
  top: { name: string; pos: string; team: string; count: number; plays: { gameId: number; playId: number; frame: number | null }[] }[];
}
const POS: Record<string, string> = { RB: "Running back", TE: "Tight end", FB: "Fullback" };

export default function WeakLinks({ scope }: { scope: TeamScope }) {
  const data = useStatic<WeakLinksData>("weak_links");
  const teams = useStatic<Teams>("teams");
  if (!data) return <div className="coach"><div className="loading">Loading…</div></div>;

  return (
    <div className="coach">
      <p className="summary">
        Share of pass-block snaps that allow a sack, hit or hurry (PFF), by position. <b>Running backs are the weakest link.</b>
      </p>
      <SnapDefinition />
      <div className="stats">
        {data.positions.map(([label, rate, n], i) => (
          <div key={label} className={`stat ${i === 0 ? "hl" : ""}`}>
            <b>{rate.toFixed(1)}%</b>
            <span>{label} · {n.toLocaleString("en-US")} snaps</span>
          </div>
        ))}
      </div>

      <h2>Backs and tight ends who allowed the most pressure</h2>
      <Hint>Click Play 1, 2 or 3 to watch the error.</Hint>
      <div className="card table-wrap">
        <table>
          <thead><tr><th>Player</th><th>Team</th><th>Flags</th><th>Replays</th></tr></thead>
          <tbody>
            {data.top.map((r) => (
              <tr key={r.name + r.team}>
                <td><b>{r.name}</b> <span style={{ color: "var(--muted)" }}>{POS[r.pos] ?? r.pos}</span></td>
                <td title={teamName(teams, r.team)}><Logo team={r.team} teams={teams} /> {r.team}</td>
                <td className="num">{r.count}</td>
                <td>
                  {r.plays.slice(0, 3).map((p, i) => (
                    <Link key={i} className="play" to={filmUrl(scope, p.gameId, p.playId, p.frame)}>Play {i + 1}</Link>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

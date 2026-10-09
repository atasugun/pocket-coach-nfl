import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Pattern, TeamScope } from "../types";
import { DOWN, Hint, Logo, SnapDefinition, errorLabel, filmUrl, focusTeam, teamName, useStatic, type Players, type Teams } from "./shared";

const ZONE: Record<string, string> = { own_territory: "own half", midfield: "midfield", opp_territory: "their half", red_zone: "red zone", backed_up: "backed up" };
const SCORE: Record<string, string> = { trailing: "trailing", leading: "leading", tied: "tied", close: "close game" };

/** "1|long|own_territory|trailing" -> "1st & long · own half · trailing" */
function situation(key: string) {
  const [down, dist, zone, score] = key.split("|");
  const d = DOWN[Number(down)] ?? down;
  return [d && dist ? `${d} & ${dist}` : d || dist, zone && (ZONE[zone] ?? zone.replace(/_/g, " ")), score && (SCORE[score] ?? score)]
    .filter(Boolean).join(" · ");
}

export default function CoachPatterns({ scope }: { scope: TeamScope }) {
  const teams = useStatic<Teams>("teams");
  const players = useStatic<Players>("players");
  const [patterns, setPatterns] = useState<Pattern[] | null>(null);
  const t = focusTeam(scope);

  useEffect(() => {
    if (!scope.myTeam || !scope.opponent) return;
    setPatterns(null);
    api.patterns(scope, { perspective: scope.mode }).then(setPatterns).catch(() => setPatterns([]));
  }, [scope.myTeam, scope.opponent, scope.mode]);

  if (!scope.myTeam || !scope.opponent) {
    return <div className="coach"><div className="empty">Pick your team and an opponent above to see recurring errors.</div></div>;
  }
  if (!patterns) return <div className="coach"><div className="loading">Loading patterns…</div></div>;

  const rows = [...patterns].sort((a, b) => b.rankScore - a.rankScore).slice(0, 40);
  const pct = (x: number) => (100 * x).toFixed(0);

  return (
    <div className="coach">
      <p className="summary">
        <Logo team={t} size={28} teams={teams} /> Recurring errors for <b>{teamName(teams, t)}</b>, ranked by how often × how costly.
      </p>
      <SnapDefinition />
      <Hint>Click Play 1, 2 or 3 to watch an example of each error.</Hint>
      {rows.length ? (
        <div className="card table-wrap">
          <table>
            <thead>
              <tr><th>Player</th><th>Error</th><th>Situation</th><th>Times / snaps</th><th>Rate · 90% interval</th><th>Replays</th></tr>
            </thead>
            <tbody>
              {rows.map((p) => {
                const pl = p.nflId != null ? players?.[String(p.nflId)] : undefined;
                return (
                  <tr key={p.patternId}>
                    <td><b>{pl?.[0] ?? (p.nflId != null ? `#${p.nflId}` : "Team")}</b> <span style={{ color: "var(--muted)" }}>{pl?.[1] ?? ""}</span></td>
                    <td>{errorLabel(p.errorType)}</td>
                    <td>{situation(p.situationKey)}</td>
                    <td className="num">{p.count} / {p.opportunities}</td>
                    <td>
                      <div className="ci">
                        <span className="num">{pct(p.rate)}%</span>
                        <div className="track">
                          <span style={{ left: `${100 * p.rateLow90}%`, width: `${100 * (p.rateHigh90 - p.rateLow90)}%` }} />
                          <i style={{ left: `${100 * p.rate}%` }} />
                        </div>
                        <span style={{ color: "var(--muted)", fontSize: 13 }}>{pct(p.rateLow90)} to {pct(p.rateHigh90)}%</span>
                      </div>
                    </td>
                    <td>
                      {p.playRefs.slice(0, 3).map((r, i) => (
                        <Link key={i} className="play" to={filmUrl(scope, r.gameId, r.playId)}>Play {i + 1}</Link>
                      ))}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="card"><div className="empty">No pattern has enough snaps yet for this matchup.</div></div>
      )}
    </div>
  );
}

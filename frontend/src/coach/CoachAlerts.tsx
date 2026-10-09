import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { ConfidenceLevel, Flag, PlayListItem, TeamScope } from "../types";
import { DOWN, Hint, Logo, errorLabel, filmUrl, focusTeam, teamName, useStatic, type Players, type Teams } from "./shared";

const LEVELS: { key: ConfidenceLevel; n: number; title: string; desc: string }[] = [
  { key: "Confirmed", n: 1, title: "Level 1 · Confirmed", desc: "Recorded in the data: PFF charted the sack, hit, hurry or beat, or the referee threw a flag. No modelling involved." },
  { key: "Likely", n: 2, title: "Level 2 · Likely", desc: "Caught by a clear tracking rule, such as an unblocked rusher or a stunt the line failed to pass off. Likely an error, so check the film." },
  { key: "Possible", n: 3, title: "Level 3 · Possible", desc: "Flagged by a model: a block that went far worse than expected, or the blocker nearest the rusher when the chance of pressure suddenly jumped. Worth reviewing." },
];

function severity(c: number | null) {
  if (c == null) return { cls: "sev-na", label: "Unknown", text: "Cost unknown" };
  const pts = -c;
  if (pts >= 3) return { cls: "sev-hi", label: "Drive-killer", text: `Cost about ${pts.toFixed(1)} points` };
  if (pts >= 1) return { cls: "sev-md", label: "Costly", text: `Cost about ${pts.toFixed(1)} points` };
  if (pts > 0) return { cls: "sev-lo", label: "Minor", text: `Cost about ${pts.toFixed(1)} points` };
  return { cls: "sev-ok", label: "Survived", text: `Play still gained ${(-pts).toFixed(1)} points` };
}
const RESULT: Record<string, string> = { C: "Complete pass", I: "Incomplete pass", S: "Sack", IN: "Interception", R: "QB scramble" };

export default function CoachAlerts({ scope }: { scope: TeamScope }) {
  const teams = useStatic<Teams>("teams");
  const players = useStatic<Players>("players");
  const [flags, setFlags] = useState<Flag[] | null>(null);
  const [plays, setPlays] = useState<PlayListItem[]>([]);
  const [level, setLevel] = useState<ConfidenceLevel>("Confirmed");
  const [type, setType] = useState("");
  const [player, setPlayer] = useState("");
  const t = focusTeam(scope);
  const other = (scope.mode === "self" ? scope.opponent : scope.myTeam) ?? "";

  useEffect(() => {
    if (!scope.myTeam || !scope.opponent) return;
    setFlags(null);
    api.flags(scope).then(setFlags).catch(() => setFlags([]));
    api.plays(scope).then(setPlays).catch(() => setPlays([]));
  }, [scope.myTeam, scope.opponent, scope.mode]);

  useEffect(() => { setType(""); setPlayer(""); }, [level, scope.myTeam, scope.opponent, scope.mode]);

  const playMeta = useMemo(() => new Map(plays.map((p) => [`${p.gameId}_${p.playId}`, p])), [plays]);
  const who = (f: Flag) => {
    const id = f.involvedNflIds[0];
    const p = id != null ? players?.[String(id)] : undefined;
    return { name: p?.[0] ?? (id != null ? `#${id}` : "Unassigned"), pos: p?.[1] ?? "" };
  };

  if (!scope.myTeam || !scope.opponent) {
    return <div className="coach"><div className="empty">Pick your team and an opponent above to see the errors in their games.</div></div>;
  }
  if (!flags) return <div className="coach"><div className="loading">Loading errors…</div></div>;

  const atLevel = flags.filter((f) => f.confidenceLevel === level);
  const types = [...new Set(atLevel.map((f) => f.errorType))].sort();
  const names = [...new Set(atLevel.map((f) => who(f).name))].sort();
  const rows = atLevel
    .filter((f) => (!type || f.errorType === type) && (!player || who(f).name === player))
    .sort((a, b) => (a.epaCost ?? 0) - (b.epaCost ?? 0));
  const L = LEVELS.find((l) => l.key === level)!;

  return (
    <div className="coach">
      <div className="teamline">
        <Logo team={t} size={56} teams={teams} />
        <div>
          <h1>{teamName(teams, t)}</h1>
          <p>
            <b>{flags.length}</b> protection errors {scope.mode === "self" ? "to fix" : "to attack"} in games against{" "}
            <Logo team={other} size={18} teams={teams} /> {teamName(teams, other)}, grouped by how sure we are
          </p>
        </div>
      </div>

      <div className="levels">
        {LEVELS.map((l) => (
          <button key={l.key} className={`lvl ${l.key} ${l.key === level ? "on" : ""}`} onClick={() => setLevel(l.key)}>
            <span className="lvn">{l.n}</span>
            <span><b>{l.title}</b><small>{flags.filter((f) => f.confidenceLevel === l.key).length} errors</small></span>
          </button>
        ))}
      </div>
      <p className="leveldesc">{L.desc}</p>

      <div className="toolbar">
        <select aria-label="Error type" value={type} onChange={(e) => setType(e.target.value)}>
          <option value="">All error types</option>
          {types.map((k) => <option key={k} value={k}>{errorLabel(k)}</option>)}
        </select>
        <select aria-label="Player" value={player} onChange={(e) => setPlayer(e.target.value)}>
          <option value="">All players</option>
          {names.map((n) => <option key={n}>{n}</option>)}
        </select>
      </div>

      <Hint>Click any error below to watch the play and see the moment it happened.</Hint>

      <div className="card">
        {rows.length ? rows.map((f) => {
          const w = who(f), s = severity(f.epaCost), m = playMeta.get(`${f.gameId}_${f.playId}`);
          return (
            <Link key={f.flagId} className="list-row" to={filmUrl(scope, f.gameId, f.playId, f.errorFrameId)}>
              <div><span className="who">{w.name}</span> <span className="pos">{w.pos}</span> · {errorLabel(f.errorType)}</div>
              <div className="cost">
                <span className={`sev ${s.cls}`}>{s.label}</span>
                <b>{s.text}</b>
                {m && <small>{RESULT[m.result] ?? m.result}</small>}
              </div>
              <div className="meta">
                {m ? <>Week {m.week} · {DOWN[m.down]} &amp; {m.yardsToGo} · </> : null}{f.explanation}
              </div>
            </Link>
          );
        }) : <div className="empty">No errors at this level for this matchup.</div>}
      </div>
      <p className="summary" style={{ marginTop: 10, fontSize: 13 }}>
        Points = expected points: how much the play changed the offense's expected score compared with an average play. When a play has several errors, the cost is shared between them.
      </p>
    </div>
  );
}

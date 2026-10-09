import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ErrorBar, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { Mode, Pattern, TeamScope } from "../types";
import { scopeQuery } from "../useTeamScope";
import "./PatternsScreen.css";

export default function PatternsScreen({ scope }: { scope: TeamScope }) {
  const [perspective, setPerspective] = useState<Mode>(scope.mode);
  const [patterns, setPatterns] = useState<Pattern[]>([]);
  const [selected, setSelected] = useState<Pattern | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setPerspective(scope.mode);
  }, [scope.mode]);

  useEffect(() => {
    if (!scope.myTeam || !scope.opponent) {
      setPatterns([]);
      return;
    }
    setLoading(true);
    api
      .patterns({ ...scope, mode: perspective }, { perspective })
      .then((p) => {
        setPatterns(p);
        setSelected(p[0] ?? null);
      })
      .catch(() => setPatterns([]))
      .finally(() => setLoading(false));
  }, [scope.myTeam, scope.opponent, perspective]);

  const chartData = patterns.slice(0, 12).map((p) => ({
    name: `${p.errorType.replace(/_/g, " ")}`,
    rate: Math.round(p.rate * 1000) / 10,
    errLow: Math.round((p.rate - p.rateLow90) * 1000) / 10,
    errHigh: Math.round((p.rateHigh90 - p.rate) * 1000) / 10,
  }));

  if (!scope.myTeam || !scope.opponent) {
    return <div className="patterns-screen__empty">Pick a team and an opponent above to see recurring patterns.</div>;
  }

  return (
    <div className="patterns-screen">
      <div className="patterns-screen__head">
        <h1>Patterns</h1>
        <div className="patterns-screen__tabs" role="tablist">
          <button role="tab" aria-selected={perspective === "self"} className={perspective === "self" ? "active" : ""} onClick={() => setPerspective("self")}>
            Self-scout
          </button>
          <button role="tab" aria-selected={perspective === "opponent"} className={perspective === "opponent" ? "active" : ""} onClick={() => setPerspective("opponent")}>
            Opponent
          </button>
        </div>
      </div>
      <p className="patterns-screen__sub">{loading ? "Loading…" : `${patterns.length} patterns with at least 10 opportunities, ranked by frequency × avg cost`}</p>

      {chartData.length > 0 && (
        <div className="patterns-screen__chart">
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={chartData} layout="vertical" margin={{ left: 140, right: 20, top: 10, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
              <XAxis type="number" unit="%" stroke="var(--text-faint)" fontSize={11} />
              <YAxis type="category" dataKey="name" width={135} stroke="var(--text-faint)" fontSize={11} />
              <Tooltip
                contentStyle={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 8, fontSize: 12 }}
              />
              <Bar dataKey="rate" fill="var(--accent)" radius={3}>
                <ErrorBar
                  dataKey={(d: { errLow: number; errHigh: number }) => [d.errLow, d.errHigh]}
                  width={4}
                  strokeWidth={1.5}
                  stroke="var(--text-faint)"
                  direction="x"
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="patterns-screen__body">
        <div className="patterns-screen__table">
          <div className="patterns-screen__row patterns-screen__row--head">
            <span>Error</span>
            <span>Situation</span>
            <span>Count</span>
            <span>Rate (90% CI)</span>
            <span>Sample</span>
            <span>Avg cost</span>
          </div>
          {patterns.map((p) => (
            <button key={p.patternId} className={`patterns-screen__row ${selected?.patternId === p.patternId ? "selected" : ""}`} onClick={() => setSelected(p)}>
              <span className="tag">{p.errorType.replace(/_/g, " ")}</span>
              <span className="patterns-screen__situation">{p.situationKey.replace(/\|/g, " · ")}</span>
              <span className="mono">{p.count}</span>
              <span className="mono">
                {(p.rate * 100).toFixed(1)}% ({(p.rateLow90 * 100).toFixed(0)}–{(p.rateHigh90 * 100).toFixed(0)}%)
              </span>
              <span className="mono">{p.sampleSize}</span>
              <span className="mono">{p.avgCost !== null ? p.avgCost.toFixed(2) : "—"}</span>
            </button>
          ))}
        </div>

        {selected && (
          <div className="patterns-screen__plays">
            <h3>Plays</h3>
            {selected.playRefs.map((ref) => (
              <Link key={`${ref.gameId}-${ref.playId}`} to={`/plays/${ref.gameId}/${ref.playId}?${scopeQuery(scope)}`} className="patterns-screen__play-link">
                Game {ref.gameId} · Play {ref.playId}
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { PlayerDetail, TeamScope } from "../types";
import { scopeQuery } from "../useTeamScope";
import "./PlayerPage.css";

export default function PlayerPage({ scope }: { scope: TeamScope }) {
  const { nflId } = useParams();
  const [data, setData] = useState<PlayerDetail | null>(null);

  useEffect(() => {
    if (!nflId) return;
    api.player(Number(nflId), scope).then(setData).catch(() => setData(null));
  }, [nflId, scope.myTeam, scope.opponent, scope.mode]);

  if (!data) return <div className="player-page__state">Loading…</div>;

  return (
    <div className="player-page">
      <h1>
        {data.player.name} <span className="player-page__pos">{data.player.position}</span>
      </h1>

      <div className="player-page__metrics">
        {data.metrics.map((m) => (
          <div key={m.name} className="player-page__metric">
            <div className="player-page__metric-name">{m.name}</div>
            <div className="player-page__metric-value mono">{m.value !== null ? m.value.toFixed(2) : "—"}</div>
            <div className="player-page__metric-n mono">n = {m.sampleSize}</div>
          </div>
        ))}
      </div>

      <div className="player-page__cols">
        <div className="player-page__panel">
          <h2>Flags</h2>
          {data.flags.length === 0 && <p className="player-page__none">No flags for this player in the scoped games.</p>}
          {data.flags.map((f) => (
            <Link key={f.flagId} to={`/plays/${f.gameId}/${f.playId}?${scopeQuery(scope)}&frame=${f.errorFrameId}`} className="player-page__flag-row">
              <span className={`confidence-pill ${f.confidenceLevel}`}>{f.confidenceLevel}</span>
              <span>{f.explanation}</span>
            </Link>
          ))}
        </div>

        <div className="player-page__panel">
          <h2>Patterns</h2>
          {data.patterns.length === 0 && <p className="player-page__none">No recurring patterns (below the minimum sample size).</p>}
          {data.patterns.map((p) => (
            <div key={p.patternId} className="player-page__pattern-row">
              <span className="tag">{p.errorType.replace(/_/g, " ")}</span>
              <span className="player-page__pattern-situation">{p.situationKey.replace(/\|/g, " · ")}</span>
              <span className="mono">{(p.rate * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

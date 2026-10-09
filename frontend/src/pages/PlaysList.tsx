import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { PlayListItem, TeamScope } from "../types";
import { scopeQuery } from "../useTeamScope";
import "./PlaysList.css";

export default function PlaysList({ scope }: { scope: TeamScope }) {
  const [plays, setPlays] = useState<PlayListItem[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .plays(scope)
      .then(setPlays)
      .catch(() => setPlays([]))
      .finally(() => setLoading(false));
  }, [scope.myTeam, scope.opponent, scope.mode]);

  if (!scope.myTeam || !scope.opponent) {
    return <div className="plays-list__empty">Pick a team and an opponent above to load film.</div>;
  }

  return (
    <div className="plays-list">
      <h1>Film room</h1>
      <p className="plays-list__sub">{loading ? "Loading…" : `${plays.length} dropback passes between ${scope.myTeam} and ${scope.opponent}`}</p>

      <div className="plays-list__table">
        <div className="plays-list__row plays-list__row--head">
          <span>Wk</span>
          <span>Down &amp; Dist</span>
          <span>Offense</span>
          <span>Defense</span>
          <span>Result</span>
          <span>Flags</span>
          <span>Description</span>
        </div>
        {plays.map((p) => (
          <Link
            key={`${p.gameId}-${p.playId}`}
            to={`/plays/${p.gameId}/${p.playId}?${scopeQuery(scope)}`}
            className="plays-list__row"
          >
            <span className="mono">{p.week}</span>
            <span className="mono">
              {p.down}&amp;{p.yardsToGo}
            </span>
            <span>{p.offense}</span>
            <span>{p.defense}</span>
            <span className="tag">{p.result}</span>
            <span className={p.flagCount > 0 ? "plays-list__flagcount plays-list__flagcount--active" : "plays-list__flagcount"}>
              {p.flagCount}
            </span>
            <span className="plays-list__desc">{p.playDescription}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}

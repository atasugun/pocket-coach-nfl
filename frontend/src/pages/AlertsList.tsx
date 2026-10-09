import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import type { ConfidenceLevel, Flag, TeamScope } from "../types";
import { scopeQuery } from "../useTeamScope";
import "./AlertsList.css";

const CONFIDENCE_LEVELS: ConfidenceLevel[] = ["Confirmed", "Likely", "Possible"];

export default function AlertsList({ scope }: { scope: TeamScope }) {
  const [flags, setFlags] = useState<Flag[]>([]);
  const [loading, setLoading] = useState(false);
  const [confidenceFilter, setConfidenceFilter] = useState<string>("");
  const [errorTypeFilter, setErrorTypeFilter] = useState<string>("");

  useEffect(() => {
    if (!scope.myTeam || !scope.opponent) {
      setFlags([]);
      return;
    }
    setLoading(true);
    api
      .flags(scope, { confidenceLevel: confidenceFilter || undefined, errorType: errorTypeFilter || undefined })
      .then(setFlags)
      .catch(() => setFlags([]))
      .finally(() => setLoading(false));
  }, [scope.myTeam, scope.opponent, scope.mode, confidenceFilter, errorTypeFilter]);

  const errorTypes = useMemo(() => [...new Set(flags.map((f) => f.errorType))].sort(), [flags]);
  const charged = scope.mode === "opponent" ? scope.opponent : scope.myTeam;

  if (!scope.myTeam || !scope.opponent) {
    return (
      <div className="alerts-list__empty">
        <h1>Pick a matchup</h1>
        <p>Select a team and an opponent above to see flagged pass-protection errors.</p>
      </div>
    );
  }

  return (
    <div className="alerts-list">
      <div className="alerts-list__head">
        <div>
          <h1>Alerts</h1>
          <p className="alerts-list__sub">
            {scope.mode === "self" ? `${charged}'s own errors` : `${charged}'s weaknesses to attack`} — {loading ? "loading…" : `${flags.length} flags`}
          </p>
        </div>

        <div className="alerts-list__filters">
          <select value={confidenceFilter} onChange={(e) => setConfidenceFilter(e.target.value)}>
            <option value="">All confidence</option>
            {CONFIDENCE_LEVELS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select value={errorTypeFilter} onChange={(e) => setErrorTypeFilter(e.target.value)}>
            <option value="">All error types</option>
            {errorTypes.map((e) => (
              <option key={e} value={e}>
                {e.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="alerts-list__table">
        <div className="alerts-list__row alerts-list__row--head">
          <span>Confidence</span>
          <span>Error</span>
          <span>Team</span>
          <span>Explanation</span>
          <span>Play EPA (shared)</span>
        </div>
        {flags.map((f) => (
          <Link
            key={f.flagId}
            to={`/plays/${f.gameId}/${f.playId}?${scopeQuery(scope)}&frame=${f.errorFrameId}`}
            className="alerts-list__row"
          >
            <span className={`confidence-pill ${f.confidenceLevel}`}>{f.confidenceLevel}</span>
            <span className="tag">{f.errorType.replace(/_/g, " ")}</span>
            <span>{f.team}</span>
            <span className="alerts-list__explanation">{f.explanation}</span>
            <span className="mono alerts-list__cost">
              {f.epaCost !== null ? f.epaCost.toFixed(2) : "cost unavailable"}
            </span>
          </Link>
        ))}
        {!loading && flags.length === 0 && <div className="alerts-list__none">No flags match these filters.</div>}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { api } from "../api";
import type { TeamScope } from "../types";
import "./TeamSelector.css";

interface Props {
  scope: TeamScope;
  onChange: (next: Partial<TeamScope>) => void;
}

export default function TeamSelector({ scope, onChange }: Props) {
  const [teams, setTeams] = useState<string[]>([]);

  useEffect(() => {
    api.teams().then(setTeams).catch(() => setTeams([]));
  }, []);

  return (
    <div className="team-selector">
      <div className="team-selector__field">
        <label htmlFor="myTeam">My team</label>
        <div className="team-selector__pick">
          {scope.myTeam && <img className="team-selector__logo" src={`/logos/${scope.myTeam}.png`} alt="" width={26} height={26} />}
          <select id="myTeam" value={scope.myTeam ?? ""} onChange={(e) => onChange({ myTeam: e.target.value || null })}>
            <option value="">Select…</option>
            {teams.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      <span className="team-selector__vs">vs</span>

      <div className="team-selector__field">
        <label htmlFor="opponent">Opponent</label>
        <div className="team-selector__pick">
          {scope.opponent && <img className="team-selector__logo" src={`/logos/${scope.opponent}.png`} alt="" width={26} height={26} />}
          <select id="opponent" value={scope.opponent ?? ""} onChange={(e) => onChange({ opponent: e.target.value || null })}>
            <option value="">Select…</option>
            {teams.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="team-selector__mode" role="tablist" aria-label="Perspective">
        <button
          role="tab"
          aria-selected={scope.mode === "self"}
          className={scope.mode === "self" ? "active" : ""}
          onClick={() => onChange({ mode: "self" })}
        >
          Self-scout
        </button>
        <button
          role="tab"
          aria-selected={scope.mode === "opponent"}
          className={scope.mode === "opponent" ? "active" : ""}
          onClick={() => onChange({ mode: "opponent" })}
        >
          Opponent
        </button>
      </div>
    </div>
  );
}

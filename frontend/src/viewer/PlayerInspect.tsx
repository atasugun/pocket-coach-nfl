import { Link } from "react-router-dom";
import type { Flag, Frame } from "../types";
import { teamColor } from "./teamColors";
import "./PlayerInspect.css";

interface Props {
  nflId: number;
  frames: Frame[];
  flags: Flag[];
  scopeQuery: string;
  onClose: () => void;
}

export default function PlayerInspect({ nflId, frames, flags, scopeQuery, onClose }: Props) {
  const firstObj = frames.flatMap((f) => f.objects).find((o) => o.nflId === nflId);
  const playerFlags = flags.filter((f) => f.involvedNflIds.includes(nflId));

  if (!firstObj) return null;

  return (
    <div className="player-inspect">
      <button className="player-inspect__close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <div className="player-inspect__head">
        <span className="player-inspect__dot" style={{ background: teamColor(firstObj.team) }} />
        <span className="player-inspect__jersey mono">#{firstObj.jersey}</span>
        <span className="player-inspect__team">{firstObj.team}</span>
      </div>
      <div className="player-inspect__role">{firstObj.role ?? "—"}</div>
      <Link to={`/players/${nflId}?${scopeQuery}`} className="player-inspect__link">
        View player page →
      </Link>
      {playerFlags.length > 0 && (
        <div className="player-inspect__flags">
          {playerFlags.map((f) => (
            <div key={f.flagId} className="player-inspect__flag">
              <span className={`confidence-pill ${f.confidenceLevel}`}>{f.confidenceLevel}</span>
              <span>{f.explanation}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

import type { PlayHeaderData } from "../types";
import { teamColor } from "./teamColors";
import "./PlayHeader.css";

export default function PlayHeader({ header }: { header: PlayHeaderData }) {
  return (
    <div className="play-header">
      <div className="play-header__teams">
        <span className="play-header__team" style={{ color: teamColor(header.offense) }}>
          {header.offense}
        </span>
        <span className="play-header__at">vs</span>
        <span className="play-header__team" style={{ color: teamColor(header.defense) }}>
          {header.defense}
        </span>
      </div>
      <div className="play-header__facts mono">
        <span>Q{header.quarter}</span>
        <span>{header.clock}</span>
        <span>
          {header.down}&amp;{header.distance}
        </span>
        <span className="tag">{header.result}</span>
        {header.coverage && <span className="tag">{header.coverage}</span>}
      </div>
      <p className="play-header__desc">{header.playDescription}</p>
    </div>
  );
}

import type { Flag, Frame } from "../types";
import "./Timeline.css";

const EVENT_LABELS: Record<string, string> = {
  ball_snap: "Snap",
  autoevent_ballsnap: "Snap",
  pass_forward: "Throw",
  autoevent_passforward: "Throw",
  qb_sack: "Sack",
  qb_strip_sack: "Sack",
};

const CONFIDENCE_COLOR: Record<string, string> = {
  Confirmed: "var(--confirmed)",
  Likely: "var(--likely)",
  Possible: "var(--possible)",
};

interface Props {
  frames: Frame[];
  currentFrameIndex: number;
  flags: Flag[];
  onSeek: (frameIndex: number) => void;
}

export default function Timeline({ frames, currentFrameIndex, flags, onSeek }: Props) {
  const n = frames.length;
  if (n === 0) return null;

  const frameIdToIndex = new Map(frames.map((f, i) => [f.frameId, i]));

  function handleClick(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const frac = (e.clientX - rect.left) / rect.width;
    onSeek(Math.max(0, Math.min(n - 1, Math.round(frac * (n - 1)))));
  }

  return (
    <div className="timeline">
      <div className="timeline__track" onClick={handleClick}>
        <div className="timeline__fill" style={{ width: `${(currentFrameIndex / Math.max(1, n - 1)) * 100}%` }} />
        {frames.map((f, i) => {
          const label = EVENT_LABELS[f.event];
          if (!label) return null;
          return (
            <div
              key={`event-${i}`}
              className="timeline__event"
              style={{ left: `${(i / Math.max(1, n - 1)) * 100}%` }}
              title={label}
            >
              <span>{label}</span>
            </div>
          );
        })}
        {flags.map((flag) => {
          const idx = frameIdToIndex.get(flag.errorFrameId);
          if (idx === undefined) return null;
          return (
            <div
              key={flag.flagId}
              className="timeline__flag"
              style={{
                left: `${(idx / Math.max(1, n - 1)) * 100}%`,
                background: CONFIDENCE_COLOR[flag.confidenceLevel],
              }}
              title={`${flag.confidenceLevel}: ${flag.explanation}`}
            />
          );
        })}
        <div className="timeline__playhead" style={{ left: `${(currentFrameIndex / Math.max(1, n - 1)) * 100}%` }} />
      </div>
    </div>
  );
}

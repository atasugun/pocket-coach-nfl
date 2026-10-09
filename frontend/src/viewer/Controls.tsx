import { useEffect } from "react";
import "./Controls.css";

const SPEEDS = [0.25, 0.5, 1] as const;

interface Props {
  playing: boolean;
  onTogglePlay: () => void;
  speed: number;
  onSpeedChange: (speed: number) => void;
  frameIndex: number;
  frameCount: number;
  onSeek: (frameIndex: number) => void;
  showFullPath: boolean;
  onToggleFullPath: () => void;
}

export default function Controls({
  playing,
  onTogglePlay,
  speed,
  onSpeedChange,
  frameIndex,
  frameCount,
  onSeek,
  showFullPath,
  onToggleFullPath,
}: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "ArrowRight") {
        onSeek(Math.min(frameCount - 1, frameIndex + 1));
      } else if (e.key === "ArrowLeft") {
        onSeek(Math.max(0, frameIndex - 1));
      } else if (e.key === " ") {
        e.preventDefault();
        onTogglePlay();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [frameIndex, frameCount, onSeek, onTogglePlay]);

  return (
    <div className="controls">
      <button className="controls__play" onClick={onTogglePlay} aria-label={playing ? "Pause" : "Play"}>
        {playing ? "❙❙" : "▶"}
      </button>

      <div className="controls__speeds" role="group" aria-label="Playback speed">
        {SPEEDS.map((s) => (
          <button key={s} className={s === speed ? "active" : ""} onClick={() => onSpeedChange(s)}>
            {s}x
          </button>
        ))}
      </div>

      <input
        className="controls__scrubber"
        type="range"
        min={0}
        max={Math.max(0, frameCount - 1)}
        value={frameIndex}
        onChange={(e) => onSeek(Number(e.target.value))}
        aria-label="Frame scrubber"
      />

      <span className="controls__count mono">
        {frameIndex + 1} / {frameCount}
      </span>

      <label className="controls__toggle">
        <input type="checkbox" checked={showFullPath} onChange={onToggleFullPath} />
        Full path
      </label>
    </div>
  );
}

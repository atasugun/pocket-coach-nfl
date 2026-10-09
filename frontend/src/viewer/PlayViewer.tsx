import { useEffect, useRef, useState } from "react";
import type { PlayDetail } from "../types";
import FieldCanvas from "./FieldCanvas";
import PlayHeader from "./PlayHeader";
import Timeline from "./Timeline";
import Controls from "./Controls";
import PlayerInspect from "./PlayerInspect";
import "./PlayViewer.css";

const FRAME_INTERVAL_MS = 100; // 10fps base rate

interface Props {
  play: PlayDetail;
  initialFrameIndex?: number;
  scopeQuery: string;
}

export default function PlayViewer({ play, initialFrameIndex = 0, scopeQuery }: Props) {
  const [frameIndex, setFrameIndex] = useState(initialFrameIndex);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [showFullPath, setShowFullPath] = useState(false);
  const [selectedNflId, setSelectedNflId] = useState<number | null>(null);

  const lastTickRef = useRef<number>(0);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    setFrameIndex(initialFrameIndex);
  }, [initialFrameIndex, play]);

  useEffect(() => {
    if (!playing) return;

    function tick(now: number) {
      if (now - lastTickRef.current >= FRAME_INTERVAL_MS / speed) {
        lastTickRef.current = now;
        setFrameIndex((i) => {
          if (i >= play.frames.length - 1) {
            return i;
          }
          return i + 1;
        });
      }
      rafRef.current = requestAnimationFrame(tick);
    }
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [playing, speed, play.frames.length]);

  useEffect(() => {
    if (frameIndex >= play.frames.length - 1) {
      setPlaying(false);
    }
  }, [frameIndex, play.frames.length]);

  return (
    <div className="play-viewer">
      <div className="play-viewer__main">
        <PlayHeader header={play.header} />
        <FieldCanvas
          frames={play.frames}
          currentFrameIndex={frameIndex}
          meta={play.meta}
          flags={play.flags}
          showFullPath={showFullPath}
          selectedNflId={selectedNflId}
          onSelectPlayer={setSelectedNflId}
        />
        <Timeline frames={play.frames} currentFrameIndex={frameIndex} flags={play.flags} onSeek={setFrameIndex} />
        <Controls
          playing={playing}
          onTogglePlay={() => setPlaying((p) => !p)}
          speed={speed}
          onSpeedChange={setSpeed}
          frameIndex={frameIndex}
          frameCount={play.frames.length}
          onSeek={setFrameIndex}
          showFullPath={showFullPath}
          onToggleFullPath={() => setShowFullPath((v) => !v)}
        />
      </div>

      <div className="play-viewer__side">
        {selectedNflId !== null && (
          <PlayerInspect
            nflId={selectedNflId}
            frames={play.frames}
            flags={play.flags}
            scopeQuery={scopeQuery}
            onClose={() => setSelectedNflId(null)}
          />
        )}
        <FlagList flags={play.flags} onSeekToFrame={(frameId) => {
          const idx = play.frames.findIndex((f) => f.frameId === frameId);
          if (idx >= 0) setFrameIndex(idx);
        }} />
      </div>
    </div>
  );
}

function FlagList({ flags, onSeekToFrame }: { flags: PlayDetail["flags"]; onSeekToFrame: (frameId: number) => void }) {
  if (flags.length === 0) {
    return <div className="play-viewer__no-flags">No flags on this play.</div>;
  }
  return (
    <div className="play-viewer__flags">
      <h3>Flags on this play</h3>
      {flags.map((f) => (
        <button key={f.flagId} className="play-viewer__flag-row" onClick={() => onSeekToFrame(f.errorFrameId)}>
          <span className={`confidence-pill ${f.confidenceLevel}`}>{f.confidenceLevel}</span>
          <span className="play-viewer__flag-text">{f.explanation}</span>
          <span className="mono play-viewer__flag-cost">
            {f.epaCost !== null ? f.epaCost.toFixed(2) : "cost unavailable"}
          </span>
        </button>
      ))}
    </div>
  );
}

import { useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import type { PlayDetail, TeamScope } from "../types";
import PlayViewer from "../viewer/PlayViewer";
import { scopeQuery } from "../useTeamScope";
import "./PlayViewerPage.css";

export default function PlayViewerPage({ scope }: { scope: TeamScope }) {
  const { gameId, playId } = useParams();
  const [params] = useSearchParams();
  const [play, setPlay] = useState<PlayDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!gameId || !playId) return;
    setPlay(null);
    setError(null);
    api
      .play(Number(gameId), Number(playId))
      .then(setPlay)
      .catch(() => setError("Could not load this play."));
  }, [gameId, playId]);

  if (error) return <div className="play-viewer-page__state">{error}</div>;
  if (!play) return <div className="play-viewer-page__state">Loading film…</div>;

  const frameParam = params.get("frame");
  const initialFrameIndex = frameParam
    ? Math.max(0, play.frames.findIndex((f) => f.frameId === Number(frameParam)))
    : 0;

  return <PlayViewer play={play} initialFrameIndex={initialFrameIndex === -1 ? 0 : initialFrameIndex} scopeQuery={scopeQuery(scope)} />;
}

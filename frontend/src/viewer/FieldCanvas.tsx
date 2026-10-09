import { useEffect, useRef } from "react";
import type { Flag, Frame, PlayMeta } from "../types";
import { teamColor, teamTextColor } from "./teamColors";
import { convexHull } from "./geometry";
import "./FieldCanvas.css";

const FIELD_LENGTH = 120;
const FIELD_WIDTH = 53.3;
const TRAIL_FRAMES = 10; // 1 second at 10fps

const CONFIDENCE_RING: Record<string, string> = {
  Confirmed: "#5fbe84",
  Likely: "#e3ac4d",
  Possible: "#86a6ec",
};

interface Props {
  frames: Frame[];
  currentFrameIndex: number;
  meta: PlayMeta | null;
  flags: Flag[];
  showFullPath: boolean;
  selectedNflId: number | null;
  onSelectPlayer: (nflId: number | null) => void;
}

export default function FieldCanvas({
  frames,
  currentFrameIndex,
  meta,
  flags,
  showFullPath,
  selectedNflId,
  onSelectPlayer,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const sizeRef = useRef({ w: 900, h: 900 * (FIELD_WIDTH / FIELD_LENGTH) });

  const ringByPlayer = buildRingByPlayer(flags);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0].contentRect.width;
      sizeRef.current = { w: width, h: width * (FIELD_WIDTH / FIELD_LENGTH) };
      resizeCanvas();
      draw();
    });
    observer.observe(el);
    return () => observer.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function resizeCanvas() {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const { w, h } = sizeRef.current;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    const ctx = canvas.getContext("2d");
    ctx?.scale(dpr, dpr);
  }

  function toCanvas(x: number, y: number): [number, number] {
    const { w, h } = sizeRef.current;
    return [(x / FIELD_LENGTH) * w, (y / FIELD_WIDTH) * h];
  }

  function draw() {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const { w, h } = sizeRef.current;

    ctx.clearRect(0, 0, w, h);
    drawField(ctx, w, h, meta);

    const frame = frames[currentFrameIndex];
    if (!frame) return;

    drawTrails(ctx, frames, currentFrameIndex, showFullPath, toCanvas);
    drawPocket(ctx, frame, toCanvas);

    for (const obj of frame.objects) {
      if (obj.isBall) continue;
      const [cx, cy] = toCanvas(obj.x, obj.y);
      const color = teamColor(obj.team);
      const ring = obj.nflId !== null ? ringByPlayer.get(obj.nflId) : undefined;
      const isSelected = obj.nflId === selectedNflId;

      if (ring) {
        ctx.beginPath();
        ctx.arc(cx, cy, 11, 0, Math.PI * 2);
        ctx.strokeStyle = ring;
        ctx.lineWidth = 2.5;
        ctx.stroke();
      }
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(cx, cy, 13, 0, Math.PI * 2);
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 3]);
        ctx.stroke();
        ctx.setLineDash([]);
      }

      ctx.beginPath();
      ctx.arc(cx, cy, 8, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 1;
      ctx.strokeStyle = "rgba(0,0,0,0.35)";
      ctx.stroke();

      if (obj.jersey !== null) {
        ctx.fillStyle = teamTextColor(obj.team);
        ctx.font = "600 8px 'IBM Plex Mono', monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(String(obj.jersey), cx, cy + 0.5);
      }
    }

    const ball = frame.objects.find((o) => o.isBall);
    if (ball) {
      const [cx, cy] = toCanvas(ball.x, ball.y);
      ctx.beginPath();
      ctx.ellipse(cx, cy, 4.5, 3, 0, 0, Math.PI * 2);
      ctx.fillStyle = "#8b5a2b";
      ctx.fill();
      ctx.strokeStyle = "#f5f0e6";
      ctx.lineWidth = 0.8;
      ctx.stroke();
    }
  }

  function handleClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;

    const frame = frames[currentFrameIndex];
    if (!frame) return;
    let closest: { nflId: number; dist: number } | null = null;
    for (const obj of frame.objects) {
      if (obj.isBall || obj.nflId === null) continue;
      const [cx, cy] = toCanvas(obj.x, obj.y);
      const dist = Math.hypot(cx - px, cy - py);
      if (dist < 14 && (!closest || dist < closest.dist)) {
        closest = { nflId: obj.nflId, dist };
      }
    }
    onSelectPlayer(closest ? closest.nflId : null);
  }

  useEffect(() => {
    resizeCanvas();
    draw();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentFrameIndex, frames, meta, showFullPath, selectedNflId, flags]);

  return (
    <div className="field-canvas-wrap" ref={containerRef}>
      <canvas ref={canvasRef} onClick={handleClick} />
    </div>
  );
}

function buildRingByPlayer(flags: Flag[]): Map<number, string> {
  const rank = { Confirmed: 3, Likely: 2, Possible: 1 };
  const map = new Map<number, { color: string; rank: number }>();
  for (const f of flags) {
    for (const id of f.involvedNflIds) {
      const existing = map.get(id);
      const r = rank[f.confidenceLevel];
      if (!existing || r > existing.rank) {
        map.set(id, { color: CONFIDENCE_RING[f.confidenceLevel], rank: r });
      }
    }
  }
  const out = new Map<number, string>();
  map.forEach((v, k) => out.set(k, v.color));
  return out;
}

function drawField(ctx: CanvasRenderingContext2D, w: number, h: number, meta: PlayMeta | null) {
  const grad = ctx.createLinearGradient(0, 0, w, 0);
  grad.addColorStop(0, "#164a2d");
  grad.addColorStop(0.5, "#1c5c3a");
  grad.addColorStop(1, "#164a2d");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, w, h);

  // End zones
  const endzoneW = (10 / FIELD_LENGTH) * w;
  ctx.fillStyle = "rgba(0,0,0,0.18)";
  ctx.fillRect(0, 0, endzoneW, h);
  ctx.fillRect(w - endzoneW, 0, endzoneW, h);

  // Yard lines every 5 yards
  ctx.strokeStyle = "rgba(255,255,255,0.35)";
  ctx.lineWidth = 1;
  for (let yard = 10; yard <= 110; yard += 5) {
    const x = (yard / FIELD_LENGTH) * w;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  ctx.strokeStyle = "rgba(255,255,255,0.6)";
  ctx.lineWidth = 1.5;
  for (let yard = 10; yard <= 110; yard += 10) {
    const x = (yard / FIELD_LENGTH) * w;
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }

  if (meta) {
    const losX = (meta.lineOfScrimmage / FIELD_LENGTH) * w;
    ctx.strokeStyle = "#5fa8ff";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(losX, 0);
    ctx.lineTo(losX, h);
    ctx.stroke();

    const fdX = (meta.firstDownX / FIELD_LENGTH) * w;
    ctx.strokeStyle = "#f0d250";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 5]);
    ctx.beginPath();
    ctx.moveTo(fdX, 0);
    ctx.lineTo(fdX, h);
    ctx.stroke();
    ctx.setLineDash([]);
  }
}

function drawTrails(
  ctx: CanvasRenderingContext2D,
  frames: Frame[],
  currentFrameIndex: number,
  showFullPath: boolean,
  toCanvas: (x: number, y: number) => [number, number],
) {
  const start = showFullPath ? 0 : Math.max(0, currentFrameIndex - TRAIL_FRAMES);
  const byPlayer = new Map<number, [number, number][]>();

  for (let i = start; i <= currentFrameIndex; i++) {
    const frame = frames[i];
    if (!frame) continue;
    for (const obj of frame.objects) {
      if (obj.isBall || obj.nflId === null) continue;
      const arr = byPlayer.get(obj.nflId) ?? [];
      arr.push(toCanvas(obj.x, obj.y));
      byPlayer.set(obj.nflId, arr);
    }
  }

  byPlayer.forEach((points) => {
    for (let i = 1; i < points.length; i++) {
      const alpha = showFullPath ? 0.15 : (i / points.length) * 0.5;
      ctx.beginPath();
      ctx.moveTo(points[i - 1][0], points[i - 1][1]);
      ctx.lineTo(points[i][0], points[i][1]);
      ctx.strokeStyle = `rgba(255,255,255,${alpha})`;
      ctx.lineWidth = 1.5;
      ctx.stroke();
    }
  });
}

function drawPocket(
  ctx: CanvasRenderingContext2D,
  frame: Frame,
  toCanvas: (x: number, y: number) => [number, number],
) {
  const pocketMembers = frame.objects.filter((o) => o.role === "Pass Block" || o.role === "Pass");
  if (pocketMembers.length < 3) return;
  const hull = convexHull(pocketMembers.map((o) => [o.x, o.y] as [number, number]));
  if (hull.length < 3) return;

  ctx.beginPath();
  hull.forEach(([x, y], i) => {
    const [cx, cy] = toCanvas(x, y);
    if (i === 0) ctx.moveTo(cx, cy);
    else ctx.lineTo(cx, cy);
  });
  ctx.closePath();
  ctx.fillStyle = "rgba(217, 182, 91, 0.08)";
  ctx.fill();
  ctx.strokeStyle = "rgba(217, 182, 91, 0.55)";
  ctx.lineWidth = 1.5;
  ctx.setLineDash([4, 3]);
  ctx.stroke();
  ctx.setLineDash([]);
}

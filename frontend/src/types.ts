export type ConfidenceLevel = "Confirmed" | "Likely" | "Possible";
export type Mode = "self" | "opponent";

export interface Flag {
  flagId: string;
  gameId: number;
  playId: number;
  errorFrameId: number;
  involvedNflIds: number[];
  team: string;
  errorType: string;
  confidenceLevel: ConfidenceLevel;
  explanation: string;
  epaCost: number | null;
  detail: Record<string, unknown>;
}

export interface PlayListItem {
  gameId: number;
  playId: number;
  down: number;
  yardsToGo: number;
  offense: string;
  defense: string;
  result: string;
  dropBackType: string;
  flagCount: number;
  playDescription: string;
  week: number;
}

export interface PlayObject {
  nflId: number | null;
  team: string;
  jersey: number | null;
  x: number;
  y: number;
  isBall: boolean;
  role: string | null;
}

export interface Frame {
  frameId: number;
  event: string;
  objects: PlayObject[];
}

export interface PlayHeaderData {
  homeTeam: string;
  awayTeam: string;
  quarter: number;
  clock: string;
  down: number;
  distance: number;
  result: string;
  coverage: string | null;
  playDescription: string;
  offense: string;
  defense: string;
}

export interface PlayMeta {
  snapFrameId: number;
  endOfDropbackFrameId: number;
  lineOfScrimmage: number;
  firstDownX: number;
}

export interface PlayDetail {
  header: PlayHeaderData;
  meta: PlayMeta;
  frames: Frame[];
  flags: Flag[];
  pocketByFrame: Record<string, number>;
}

export interface Pattern {
  patternId: string;
  label: string;
  team: string;
  nflId: number | null;
  errorType: string;
  situationKey: string;
  perspective: Mode;
  count: number;
  rate: number;
  rateLow90: number;
  rateHigh90: number;
  opportunities: number;
  sampleSize: number;
  avgCost: number | null;
  rankScore: number;
  playRefs: { gameId: number; playId: number }[];
}

export interface PlayerMetric {
  name: string;
  value: number | null;
  sampleSize: number;
}

export interface PlayerDetail {
  player: { nflId: number; name: string; position: string | null };
  metrics: PlayerMetric[];
  flags: Flag[];
  patterns: { patternId: string; errorType: string; situationKey: string; count: number; rate: number; rankScore: number }[];
}

export interface Limitations {
  title: string;
  bullets: string[];
}

export interface TeamScope {
  myTeam: string | null;
  opponent: string | null;
  mode: Mode;
}

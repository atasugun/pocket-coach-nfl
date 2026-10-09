import type {
  Flag,
  Limitations,
  Pattern,
  PlayDetail,
  PlayerDetail,
  PlayListItem,
  TeamScope,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

async function get<T>(path: string, params: Record<string, string | number | boolean | null | undefined> = {}): Promise<T> {
  const url = new URL(BASE_URL + path);
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }
  const resp = await fetch(url.toString());
  if (!resp.ok) {
    throw new Error(`${path} failed: ${resp.status}`);
  }
  return resp.json();
}

function scopeParams(scope: TeamScope, extra: Record<string, string | number | boolean | null | undefined> = {}) {
  return { myTeam: scope.myTeam, opponent: scope.opponent, mode: scope.mode, ...extra };
}

export const api = {
  teams: () => get<string[]>("/teams"),
  plays: (scope: TeamScope, extra: Record<string, string | number | boolean | null | undefined> = {}) =>
    get<PlayListItem[]>("/plays", scopeParams(scope, extra)),
  play: (gameId: number, playId: number) => get<PlayDetail>(`/plays/${gameId}/${playId}`),
  flags: (scope: TeamScope, extra: Record<string, string | number | boolean | null | undefined> = {}) =>
    get<Flag[]>("/flags", scopeParams(scope, extra)),
  patterns: (scope: TeamScope, extra: Record<string, string | number | boolean | null | undefined> = {}) =>
    get<Pattern[]>("/patterns", scopeParams(scope, extra)),
  player: (nflId: number, scope: TeamScope) => get<PlayerDetail>(`/players/${nflId}`, scopeParams(scope)),
  limitations: () => get<Limitations>("/limitations"),
};

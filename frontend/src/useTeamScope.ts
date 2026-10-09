import { useSearchParams } from "react-router-dom";
import type { Mode, TeamScope } from "./types";

/** Reads/writes myTeam, opponent, and mode from the URL query params so the
 * whole app stays scoped to the selected teams across navigation
 * (Requirement 10.1). */
export function useTeamScope(): [TeamScope, (next: Partial<TeamScope>) => void] {
  const [params, setParams] = useSearchParams();

  const scope: TeamScope = {
    myTeam: params.has("myTeam") ? params.get("myTeam") || null : "PHI",
    opponent: params.has("opponent") ? params.get("opponent") || null : "JAX",
    mode: (params.get("mode") as Mode) || "self",
  };

  const update = (next: Partial<TeamScope>) => {
    const merged = { ...scope, ...next };
    setParams(
      (prev) => {
        const p = new URLSearchParams(prev);
        if (merged.myTeam) p.set("myTeam", merged.myTeam);
        else p.delete("myTeam");
        if (merged.opponent) p.set("opponent", merged.opponent);
        else p.delete("opponent");
        p.set("mode", merged.mode);
        return p;
      },
      { replace: false },
    );
  };

  return [scope, update];
}

/** Builds a query string carrying the current scope, for links that
 * navigate to a different screen but must keep the same team selection. */
export function scopeQuery(scope: TeamScope): string {
  const p = new URLSearchParams();
  if (scope.myTeam) p.set("myTeam", scope.myTeam);
  if (scope.opponent) p.set("opponent", scope.opponent);
  p.set("mode", scope.mode);
  return p.toString();
}

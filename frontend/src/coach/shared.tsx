import { useEffect, useState } from "react";
import type { TeamScope } from "../types";
import { scopeQuery } from "../useTeamScope";
import "./coach.css";

/** Static JSON shipped in public/data (coaching advice, team names, weak links, player names). */
const cache = new Map<string, Promise<unknown>>();
export function loadStatic<T>(name: string): Promise<T> {
  if (!cache.has(name)) {
    cache.set(name, fetch(`/data/${name}.json`).then((r) => {
      if (!r.ok) throw new Error(`${name}.json failed: ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(name) as Promise<T>;
}

export function useStatic<T>(name: string): T | null {
  const [data, setData] = useState<T | null>(null);
  useEffect(() => {
    let live = true;
    loadStatic<T>(name).then((d) => live && setData(d)).catch(() => live && setData(null));
    return () => { live = false; };
  }, [name]);
  return data;
}

export type Teams = Record<string, { name: string }>;
export type Players = Record<string, [string, string | null]>;

/** The team being scouted: my team when self-scouting, the opponent otherwise. */
export const focusTeam = (scope: TeamScope) => (scope.mode === "self" ? scope.myTeam : scope.opponent) ?? "";

export const teamName = (teams: Teams | null, abbr: string) => teams?.[abbr]?.name ?? abbr;

export function Logo({ team, size = 22, teams }: { team: string; size?: number; teams?: Teams | null }) {
  if (!team) return null;
  return <img className="logo" src={`/logos/${team}.png`} alt={teamName(teams ?? null, team)} width={size} height={size} />;
}

export function Hint({ children }: { children: React.ReactNode }) {
  return (
    <p className="hint">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M8 5v14l11-7z" /></svg>
      {children}
    </p>
  );
}

/** Link target for the film viewer, keeping the team scope. */
export const filmUrl = (scope: TeamScope, gameId: number | string, playId: number | string, frame?: number | null) =>
  `/plays/${gameId}/${playId}?${scopeQuery(scope)}${frame != null ? `&frame=${frame}` : ""}`;

export const SNAP_DEF = "one pass play where this player stayed in to block for the quarterback instead of running a route";
export const SnapDefinition = () => (
  <p className="def"><b>Snap</b>: {SNAP_DEF}. Snaps count the chances a player had to give up pressure.</p>
);

const ERROR_LABELS: Record<string, string> = {
  sack_allowed: "Sack allowed",
  hit_allowed: "QB hit allowed",
  hurry_allowed: "Hurry allowed",
  beaten: "Beaten",
  beaten_by_defender: "Beaten by defender",
  penalty: "Penalty",
  free_rusher: "Free rusher",
  stunt_not_handled: "Stunt not handled",
  wasted_double_team: "Wasted double team",
  lost_escape_lane: "Lost escape lane",
  worse_than_expected: "Lost the snap",
  pressure_spike: "Pressure spike",
};
export const errorLabel = (t: string) => ERROR_LABELS[t] ?? t.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

export const DOWN = ["", "1st", "2nd", "3rd", "4th"];

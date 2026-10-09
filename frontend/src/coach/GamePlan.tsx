import { Link } from "react-router-dom";
import type { TeamScope } from "../types";
import { Hint, Logo, filmUrl, focusTeam, teamName, useStatic, type Teams } from "./shared";

interface Example { play: string; frame: number; who: string }
interface Item {
  dim: string; value: string; n: number; k: number; rate: number; league: number; lo: number; hi: number;
  strong: boolean; tell: string; tactic: string; attack: string; players: string[]; examples: Example[];
}
interface TeamPlan { dropbacks: number; rate: number; league: number; items: Item[]; strengths: string[] }
interface Coaching { teams: Record<string, TeamPlan> }

const pct = (x: number) => Math.round(100 * x);

/** Plain-English title and one-line fact for a coaching item. */
function plain(it: Item): [string, JSX.Element] {
  const r = <b>{pct(it.rate)}%</b>;
  const l = `league average ${pct(it.league)}%`;
  if (it.dim === "timing" && /fast/.test(it.value)) return ["Defenders get to the QB fast", <>{r} of breakdowns happen in under 2.5 seconds ({l})</>];
  if (it.dim === "timing") return ["The QB holds the ball too long", <>{r} of breakdowns come after 3.5 seconds ({l})</>];
  if (it.dim === "slot") return [`The ${it.value.toLowerCase()} keeps getting beaten`, <>Lets pressure through on {r} of the plays he blocks ({l})</>];
  if (it.dim === "pa") return ["Fake handoffs don't buy time", <>Pressure gets through on {r} of play-action passes ({l})</>];
  if (it.dim === "rush_grp") return [`Trouble against the ${it.value.toLowerCase()}`, <>Pressure gets through on {r} of these plays ({l})</>];
  return [`Trouble on ${it.value.replace("3rd/4th", "3rd or 4th down,").replace("&", "")}`, <>Pressure gets through on {r} of these plays ({l})</>];
}

const playParts = (key: string) => key.split("_");

export default function GamePlan({ scope }: { scope: TeamScope }) {
  const coach = useStatic<Coaching>("coaching");
  const teams = useStatic<Teams>("teams");
  const t = focusTeam(scope);
  const self = scope.mode === "self";

  if (!t) return <div className="coach"><div className="loading">Pick a team above.</div></div>;
  if (!coach) return <div className="coach"><div className="loading">Loading…</div></div>;
  const p = coach.teams[t];
  if (!p) return <div className="coach"><div className="empty">No game plan for {t}.</div></div>;

  const diff = pct(p.rate) - pct(p.league);
  const verdict: [string, string] = diff >= 3 ? ["worse", "Protection worse than average"]
    : diff <= -3 ? ["better", "Protection better than average"] : ["avg", "Protection about average"];
  const items = p.items.slice(0, 3);

  return (
    <div className="coach">
      <section className="hero">
        <div className="teamline">
          <Logo team={t} size={64} teams={teams} />
          <div>
            <h1>{teamName(teams, t)}</h1>
            <span className={`verdict ${verdict[0]}`}>{verdict[1]}</span>
          </div>
        </div>
        <p className="big">The quarterback was <b>sacked, hit or rushed</b> on <b>{pct(p.rate)}%</b> of pass plays.</p>
        <div className="bars">
          <div><span>{t}</span><i className={verdict[0]} style={{ ["--w" as string]: `${pct(p.rate)}%` }} /><b>{pct(p.rate)}%</b></div>
          <div><span>League</span><i style={{ ["--w" as string]: `${pct(p.league)}%` }} /><b>{pct(p.league)}%</b></div>
        </div>
        <p className="how">On every pass play, the blockers try to keep defenders away from the quarterback. Pocket Coach finds every time they fail and shows you the play. Lower is better.</p>
      </section>

      <h2>{self ? "What to fix" : "Where to attack"}</h2>
      {items.length ? items.map((it, i) => {
        const [title, fact] = plain(it);
        const ex = it.examples[0];
        return (
          <div className="problem" key={i}>
            <div className="num">{i + 1}</div>
            <div className="body">
              <h3>{title}</h3>
              <p className="fact">{fact}</p>
              <p className="todo"><b>{self ? "What to do" : "How to attack"}:</b> {self ? it.tell : it.attack}</p>
              {ex && <Link className="watch" to={filmUrl(scope, ...(playParts(ex.play) as [string, string]), ex.frame)}>▶ Watch it happen</Link>}
              <details>
                <summary>Coach details</summary>
                <p>Seen on {it.k} of {it.n} plays · 90% interval {pct(it.lo)} to {pct(it.hi)}% · {it.strong ? "Strong signal" : "Trend, small sample"}</p>
                {self && <p><b>Tactic:</b> {it.tactic}</p>}
                {it.players.length > 0 && <p><b>{self ? "Who to coach" : "Who to target"}:</b> {it.players.join(" · ")}</p>}
                <p><b>More film:</b>{" "}
                  {it.examples.map((e, k) => (
                    <Link key={k} className="play" to={filmUrl(scope, ...(playParts(e.play) as [string, string]), e.frame)}>Play {k + 1} ({e.who})</Link>
                  ))}
                </p>
              </details>
            </div>
          </div>
        );
      }) : (
        <div className="card"><div className="empty">Nothing stands out. This protection holds up as well as or better than the league in every situation we checked.</div></div>
      )}

      {p.strengths.length > 0 && (
        <>
          <h2>{self ? "What works" : "Don't bother attacking"}</h2>
          <ul className="good">
            {p.strengths.map((x, i) => {
              const m = x.match(/^(.*): (\d+)% vs league (\d+)%/);
              return <li key={i}>{m ? <><b>{m[1]}</b>: pressure on only {m[2]}% of plays (league average {m[3]}%)</> : x}</li>;
            })}
          </ul>
        </>
      )}

      <Hint>Click "Watch it happen" to open the play in the film room.</Hint>

      <details className="lessons">
        <summary>What's true across the whole league</summary>
        <ul>
          <li><b>3rd and long is hardest:</b> pressure on 55% of plays, vs 42% on early downs.</li>
          <li><b>Fake handoffs help:</b> 37% with play action, vs 47% without.</li>
          <li><b>Running backs are the weakest blockers:</b> beaten on 16% of plays, more than any lineman.</li>
          <li><b>Most failures are fast:</b> 43% happen in under 2.5 seconds, before receivers are open.</li>
        </ul>
      </details>
    </div>
  );
}

import { NavLink, Route, Routes } from "react-router-dom";
import TeamSelector from "./components/TeamSelector";
import LimitationsLink from "./components/LimitationsNote";
import PlaysList from "./pages/PlaysList";
import PlayViewerPage from "./pages/PlayViewerPage";
import PlayerPage from "./pages/PlayerPage";
import GamePlan from "./coach/GamePlan";
import CoachAlerts from "./coach/CoachAlerts";
import CoachPatterns from "./coach/CoachPatterns";
import WeakLinks from "./coach/WeakLinks";
import { scopeQuery, useTeamScope } from "./useTeamScope";
import "./App.css";

export default function App() {
  const [scope, setScope] = useTeamScope();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__brand">
          <svg className="app-header__mark" width="36" height="36" viewBox="0 0 40 40" aria-hidden="true">
            <g fill="none" strokeLinecap="round" strokeLinejoin="round">
              <path d="M27 10.5l2.6-3.4M31.4 13l4-1.6M23.4 9.4l.4-4.2" stroke="var(--gold)" strokeWidth="2.2" />
              <circle cx="9" cy="13.5" r="3" stroke="currentColor" strokeWidth="2" />
              <path d="M11.4 15.4l2.2 1.6" stroke="currentColor" strokeWidth="2" />
            </g>
            <path d="M16 14H34a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2H25.8A10 10 0 1 1 16 14Z" fill="var(--accent)" stroke="currentColor" strokeWidth="2.6" strokeLinejoin="round" />
            <path d="M21 14v3.4h4V14" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
            <circle cx="16" cy="24" r="4" fill="var(--gold)" />
          </svg>
          <span className="app-header__name">
            <span>Pocket<b>Coach</b></span>
            <small>Pass protection film finder</small>
          </span>
        </div>
        <TeamSelector scope={scope} onChange={setScope} />
        <nav className="app-nav">
          <NavLink end to={{ pathname: "/", search: `?${scopeQuery(scope)}` }}>Game plan</NavLink>
          <NavLink to={{ pathname: "/alerts", search: `?${scopeQuery(scope)}` }}>Alerts</NavLink>
          <NavLink to={{ pathname: "/patterns", search: `?${scopeQuery(scope)}` }}>Patterns</NavLink>
          <NavLink to={{ pathname: "/weak-links", search: `?${scopeQuery(scope)}` }}>Weak links</NavLink>
        </nav>
        <LimitationsLink />
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<GamePlan scope={scope} />} />
          <Route path="/alerts" element={<CoachAlerts scope={scope} />} />
          <Route path="/patterns" element={<CoachPatterns scope={scope} />} />
          <Route path="/weak-links" element={<WeakLinks scope={scope} />} />
          <Route path="/plays" element={<PlaysList scope={scope} />} />
          <Route path="/plays/:gameId/:playId" element={<PlayViewerPage scope={scope} />} />
          <Route path="/players/:nflId" element={<PlayerPage scope={scope} />} />
        </Routes>
      </main>
    </div>
  );
}

import { NavLink, Route, Routes } from "react-router-dom";
import TeamSelector from "./components/TeamSelector";
import LimitationsLink from "./components/LimitationsNote";
import AlertsList from "./pages/AlertsList";
import PlaysList from "./pages/PlaysList";
import PlayViewerPage from "./pages/PlayViewerPage";
import PatternsScreen from "./pages/PatternsScreen";
import PlayerPage from "./pages/PlayerPage";
import { useTeamScope } from "./useTeamScope";
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
          <NavLink to={{ pathname: "/", search: `?myTeam=${scope.myTeam ?? ""}&opponent=${scope.opponent ?? ""}&mode=${scope.mode}` }}>
            Alerts
          </NavLink>
          <NavLink to={{ pathname: "/plays", search: `?myTeam=${scope.myTeam ?? ""}&opponent=${scope.opponent ?? ""}&mode=${scope.mode}` }}>
            Film
          </NavLink>
          <NavLink to={{ pathname: "/patterns", search: `?myTeam=${scope.myTeam ?? ""}&opponent=${scope.opponent ?? ""}&mode=${scope.mode}` }}>
            Patterns
          </NavLink>
        </nav>
        <LimitationsLink />
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<AlertsList scope={scope} />} />
          <Route path="/plays" element={<PlaysList scope={scope} />} />
          <Route path="/plays/:gameId/:playId" element={<PlayViewerPage scope={scope} />} />
          <Route path="/patterns" element={<PatternsScreen scope={scope} />} />
          <Route path="/players/:nflId" element={<PlayerPage scope={scope} />} />
        </Routes>
      </main>
    </div>
  );
}

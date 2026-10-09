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
          <span className="app-header__mark">🏈</span>
          <span className="app-header__name">Pocket Watch</span>
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

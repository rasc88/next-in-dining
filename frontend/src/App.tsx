import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import { GuestStatusPage } from './pages/GuestStatusPage';
import { HostBoardPage } from './pages/HostBoardPage';
import { JoinWaitlistPage } from './pages/JoinWaitlistPage';
import { LandingPage } from './pages/LandingPage';
import { LoginPage } from './pages/LoginPage';

function RequireHost({ children }: { children: React.ReactNode }) {
  const { host } = useAuth();
  if (!host) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export function App() {
  const { host, logout } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Waitlist</h1>
        {host ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span className="tag">{host.email}</span>
            <button type="button" className="btn-quiet btn" onClick={() => logout()}>
              Sign out
            </button>
          </div>
        ) : (
          <span className="tag">Front-of-house queue</span>
        )}
      </header>

      <main className="app-main">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/join" element={<JoinWaitlistPage />} />
          <Route path="/status/:token" element={<GuestStatusPage />} />
          <Route
            path="/host"
            element={
              <RequireHost>
                <HostBoardPage />
              </RequireHost>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}

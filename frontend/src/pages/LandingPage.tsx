import { Link } from 'react-router-dom';

export function LandingPage() {
  return (
    <div className="card" style={{ maxWidth: 480, margin: '2rem auto' }}>
      <h1>Restaurant Waitlist Manager</h1>
      <p className="help-text" style={{ marginTop: '0.75rem' }}>
        Guests join the line and track their table from their phone. Hosts manage the floor from one board.
      </p>
      <div className="landing-links">
        <Link to="/join" className="btn btn-primary">
          Join a waitlist
        </Link>
        <Link to="/login" className="btn">
          Host sign in
        </Link>
      </div>
    </div>
  );
}

import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { useWaitlistService } from '../services';
import { SEATING_CATEGORIES } from '../services/types';

export function JoinWaitlistPage() {
  const service = useWaitlistService();
  const navigate = useNavigate();
  const [guestName, setGuestName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [partySize, setPartySize] = useState(2);
  const [seatingCategory, setSeatingCategory] = useState<string>(SEATING_CATEGORIES[0]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const { guestToken } = await service.joinWaitlist({
        guestName,
        phoneNumber,
        partySize,
        seatingCategory,
      });
      navigate(`/status/${guestToken}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not join the waitlist.');
      setSubmitting(false);
    }
  }

  return (
    <div className="card guest-page">
      <h1 style={{ marginBottom: '1.25rem' }}>Join the waitlist</h1>
      <form onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="guestName">Name</label>
          <input id="guestName" value={guestName} onChange={(e) => setGuestName(e.target.value)} required />
        </div>
        <div className="field">
          <label htmlFor="phoneNumber">Phone number</label>
          <input
            id="phoneNumber"
            type="tel"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="partySize">Party size</label>
          <input
            id="partySize"
            type="number"
            min={1}
            max={20}
            value={partySize}
            onChange={(e) => setPartySize(Number(e.target.value))}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="seatingCategory">Seating preference</label>
          <select id="seatingCategory" value={seatingCategory} onChange={(e) => setSeatingCategory(e.target.value)}>
            {SEATING_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </div>
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        <button type="submit" className="btn btn-primary" disabled={submitting} style={{ width: '100%' }}>
          {submitting ? 'Joining…' : 'Join waitlist'}
        </button>
      </form>
    </div>
  );
}

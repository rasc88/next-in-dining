import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { MockWaitlistService } from '../../services/mockWaitlistService';
import { renderRoute } from '../../test/testUtils';
import { GuestStatusPage } from '../GuestStatusPage';

describe('GuestStatusPage', () => {
  it('shows the guest\'s live queue position', async () => {
    const service = new MockWaitlistService(false);
    const { guestToken } = await service.joinWaitlist({
      guestName: 'Wei Zhang',
      phoneNumber: '555-0300',
      partySize: 2,
      seatingCategory: 'Indoor',
    });

    renderRoute('/status/:token', <GuestStatusPage />, {
      initialEntries: [`/status/${guestToken}`],
      service,
    });

    expect(await screen.findByText('Wei Zhang')).toBeInTheDocument();
    expect(screen.getByText("You're next in line")).toBeInTheDocument();
  });

  it('reacts live when the host marks the party as notified', async () => {
    const service = new MockWaitlistService(false);
    const { party, guestToken } = await service.joinWaitlist({
      guestName: 'Fatima Al-Sayed',
      phoneNumber: '555-0301',
      partySize: 2,
      seatingCategory: 'Bar',
    });

    renderRoute('/status/:token', <GuestStatusPage />, {
      initialEntries: [`/status/${guestToken}`],
      service,
    });

    await screen.findByText('Fatima Al-Sayed');

    // Simulate the host taking the "Notify" action from the host board —
    // the guest page should update via its subscription, no reload needed.
    await service.updatePartyState(party.id, 'NOTIFY');

    expect(await screen.findByText('Your table is ready')).toBeInTheDocument();
  });

  it('lets the guest cancel their own spot after confirming', async () => {
    const user = userEvent.setup();
    const service = new MockWaitlistService(false);
    const { guestToken } = await service.joinWaitlist({
      guestName: 'Tomás Herrera',
      phoneNumber: '555-0302',
      partySize: 4,
      seatingCategory: 'High-top',
    });

    renderRoute('/status/:token', <GuestStatusPage />, {
      initialEntries: [`/status/${guestToken}`],
      service,
    });

    await user.click(await screen.findByRole('button', { name: 'Cancel my spot' }));
    await user.click(await screen.findByRole('button', { name: 'Yes, cancel' }));

    await waitFor(() => {
      expect(screen.getByText('Spot cancelled')).toBeInTheDocument();
    });
  });
});

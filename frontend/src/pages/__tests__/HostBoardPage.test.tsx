import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import { MockWaitlistService } from '../../services/mockWaitlistService';
import { renderRoute } from '../../test/testUtils';
import { HostBoardPage } from '../HostBoardPage';

afterEach(() => {
  sessionStorage.clear();
});

describe('HostBoardPage', () => {
  it('lists parties from the service and shows queue metrics', async () => {
    const service = new MockWaitlistService(false);
    await service.joinWaitlist({
      guestName: 'Priya Nair',
      phoneNumber: '555-0200',
      partySize: 2,
      seatingCategory: 'Indoor',
    });

    const { container } = renderRoute('/host', <HostBoardPage />, { service });

    expect(await screen.findByText(/Priya Nair/)).toBeInTheDocument();
    const metricValues = container.querySelectorAll('.metric-value');
    expect(metricValues[0]).toHaveTextContent('1'); // parties waiting now
  });

  it('moves a party to Notified when the host clicks Notify', async () => {
    const user = userEvent.setup();
    const service = new MockWaitlistService(false);
    await service.joinWaitlist({
      guestName: 'Sana Iqbal',
      phoneNumber: '555-0201',
      partySize: 3,
      seatingCategory: 'Outdoor',
    });

    renderRoute('/host', <HostBoardPage />, { service });

    const notifyButton = await screen.findByRole('button', { name: 'Notify' });
    await user.click(notifyButton);

    await waitFor(() => {
      expect(screen.getByText('Notified')).toBeInTheDocument();
    });
  });

  it('filters the board by seating category', async () => {
    const user = userEvent.setup();
    const service = new MockWaitlistService(false);
    await service.joinWaitlist({
      guestName: 'Indoor Guest',
      phoneNumber: '1',
      partySize: 2,
      seatingCategory: 'Indoor',
    });
    await service.joinWaitlist({
      guestName: 'Bar Guest',
      phoneNumber: '2',
      partySize: 1,
      seatingCategory: 'Bar',
    });

    renderRoute('/host', <HostBoardPage />, { service });

    await screen.findByText(/Indoor Guest/);
    expect(screen.getByText(/Bar Guest/)).toBeInTheDocument();

    await user.click(screen.getByRole('tab', { name: 'Bar' }));

    expect(screen.queryByText(/Indoor Guest/)).not.toBeInTheDocument();
    expect(screen.getByText(/Bar Guest/)).toBeInTheDocument();
  });
});

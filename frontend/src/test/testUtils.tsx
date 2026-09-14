import { render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '../hooks/useAuth';
import { MockWaitlistService } from '../services/mockWaitlistService';
import { ServiceProvider } from '../services/ServiceProvider';

/** Renders a single route with a fresh, isolated mock service instance. */
export function renderRoute(
  path: string,
  element: ReactElement,
  { initialEntries = [path], service = new MockWaitlistService(false) }: { initialEntries?: string[]; service?: MockWaitlistService } = {},
) {
  const utils = render(
    <ServiceProvider service={service}>
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>
          <Routes>
            <Route path={path} element={element} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </ServiceProvider>,
  );
  return { ...utils, service };
}

export function markHostLoggedIn() {
  sessionStorage.setItem(
    'waitlist.session',
    JSON.stringify({ token: 'test-token', host: { id: 'host-1', email: 'host@waitlist.test' } }),
  );
}

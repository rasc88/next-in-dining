import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { App } from './App';
import './index.css';
import { AuthProvider } from './hooks/useAuth';
import { ServiceProvider } from './services';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ServiceProvider>
      <AuthProvider>
        <BrowserRouter>
          <App />
        </BrowserRouter>
      </AuthProvider>
    </ServiceProvider>
  </StrictMode>,
);

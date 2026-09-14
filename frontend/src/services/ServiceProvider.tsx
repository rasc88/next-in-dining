import { createContext, useContext, type ReactNode } from 'react';
import type { IWaitlistService } from './IWaitlistService';
import { restWaitlistService } from './restWaitlistService';

const ServiceContext = createContext<IWaitlistService | null>(null);

export function ServiceProvider({
  service = restWaitlistService,
  children,
}: {
  service?: IWaitlistService;
  children: ReactNode;
}) {
  return <ServiceContext.Provider value={service}>{children}</ServiceContext.Provider>;
}

/** The only way components should obtain a service instance. */
export function useWaitlistService(): IWaitlistService {
  const service = useContext(ServiceContext);
  if (!service) throw new Error('useWaitlistService must be used within a <ServiceProvider>.');
  return service;
}

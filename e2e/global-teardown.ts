import { execSync } from 'node:child_process';
import path from 'node:path';

const COMPOSE_ROOT = path.resolve(__dirname, '..');

function dockerAvailable(): boolean {
  try {
    execSync('docker info', { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

export default function globalTeardown(): void {
  // globalSetup already errored out (and never ran `up`) if Docker isn't
  // reachable - nothing to tear down, so skip instead of failing again here.
  if (!dockerAvailable()) return;

  execSync('docker compose down -v', { cwd: COMPOSE_ROOT, stdio: 'inherit' });
}

import { execSync } from 'node:child_process';
import path from 'node:path';

const COMPOSE_ROOT = path.resolve(__dirname, '..');
const BASE_URL = 'http://localhost:8000';

function dockerAvailable(): boolean {
  try {
    execSync('docker info', { stdio: 'ignore' });
    return true;
  } catch {
    return false;
  }
}

async function waitUntilUp(url: string, timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let lastError: unknown;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch (err) {
      lastError = err;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`${url} never came up within ${timeoutMs}ms: ${lastError}`);
}

export default async function globalSetup(): Promise<void> {
  if (!dockerAvailable()) {
    throw new Error(
      'Docker is not available (daemon unreachable or permission denied) - ' +
        'these tests drive a real `docker compose up` stack.',
    );
  }

  execSync('docker compose up --build -d', { cwd: COMPOSE_ROOT, stdio: 'inherit' });
  await waitUntilUp(`${BASE_URL}/`, 90_000);
}

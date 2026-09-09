import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Preparación de entorno para las corridas E2E de UI:
 *   1. PostgreSQL descartable (postgres-test, puerto 5434)
 *   2. Migraciones (alembic upgrade head)
 *   3. Seed E2E (admin admin@turnos.com, catálogos, 3 médicos)
 *
 * Se usa `test-db.sh reset` (down + up) en lugar de `up` para que cada
 * corrida parta de una base vacía: el journey crea el calendario del mes
 * actual y el backend rechaza duplicados (calendar_already_exists).
 */
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "..", "..");
const PYTHON = path.join(REPO_ROOT, ".venv", "bin", "python");
const ALEMBIC = path.join(REPO_ROOT, ".venv", "bin", "alembic");

const TEST_DB_URL =
  "postgresql+psycopg://postgres:postgres@127.0.0.1:5434/medical_shifts_test";

function run(
  command: string,
  args: string[],
  cwd: string,
  extraEnv: Record<string, string> = {},
): void {
  // spawnSync (no shell) para que la ruta del repo con espacios funcione tal cual.
  const result = spawnSync(command, args, {
    cwd,
    env: { ...process.env, ...extraEnv },
    stdio: "inherit",
    timeout: 180_000,
  });
  if (result.status !== 0) {
    throw new Error(
      `Global setup falló: ${command} ${args.join(" ")} (status ${result.status})`,
    );
  }
}

export default function globalSetup(): void {
  run("bash", ["scripts/test-db.sh", "reset"], REPO_ROOT);
  run(ALEMBIC, ["upgrade", "head"], REPO_ROOT, {
    DATABASE_URL: TEST_DB_URL,
  });
  run(PYTHON, ["-m", "backend.scripts.seed_e2e"], REPO_ROOT, {
    DATABASE_URL: TEST_DB_URL,
  });
}

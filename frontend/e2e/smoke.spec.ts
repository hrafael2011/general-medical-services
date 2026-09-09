import { test, expect } from "@playwright/test";

/**
 * Smoke E2E de UI del journey crítico del modo manual:
 *   login → crear calendario (mes actual) → asignación con advertencia
 *   justificada (médico mensual sin disponibilidad) → aprobar la semana.
 *
 * Datos del seed (backend/scripts/seed_e2e.py, SSOT):
 *   admin@turnos.com / AdminTest2026!
 *   "Dr. Carlos E2E" — médico en modo mensual SIN disponibilidad del mes
 *   actual: candidato "no disponible" con código no_availability (no-dura),
 *   que obliga a marcar la advertencia y escribir justificación.
 */

const ADMIN_EMAIL = "admin@turnos.com";
const ADMIN_PASSWORD = "AdminTest2026!";
const MONTHLY_DOCTOR_NAME = "Dr. Carlos E2E";
const JUSTIFICATION =
  "Cobertura de emergencia: disponibilidad pendiente (E2E).";

const MONTHS = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

/** Primer lunes del mes actual (misma lógica que buildCalendarDays/compute_weeks). */
function firstMondayOfCurrentMonth(): {
  iso: string;
  monthName: string;
  year: number;
} {
  const now = new Date();
  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
  const daysUntilMonday = (8 - firstDay.getDay()) % 7;
  const monday = new Date(firstDay);
  monday.setDate(firstDay.getDate() + daysUntilMonday);
  const pad = (n: number) => String(n).padStart(2, "0");
  return {
    iso: `${monday.getFullYear()}-${pad(monday.getMonth() + 1)}-${pad(monday.getDate())}`,
    monthName: MONTHS[monday.getMonth()],
    year: monday.getFullYear(),
  };
}

test("smoke: login → calendario → asignación justificada → aprobar semana", async ({
  page,
}) => {
  const slot = firstMondayOfCurrentMonth();

  // ── 1. Login ───────────────────────────────────────────────────────────
  await page.goto("/login");
  await page.getByLabel("Correo").fill(ADMIN_EMAIL);
  // El label "Contraseña" contiene también el botón de mostrar/ocultar,
  // por lo que getByLabel resuelve a 2 elementos: usar el input por tipo.
  await page.locator('input[type="password"]').fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Entrar" }).click();
  await page.waitForURL("**/dashboard");
  await expect(page.getByRole("link", { name: "Calendarios" })).toBeVisible();
  // El toast de bienvenida (fixed, top-right) puede tapar el botón
  // "Nuevo calendario": esperar a que desaparezca (~5.6s).
  await expect(page.locator(".welcome-toast")).toHaveCount(0, {
    timeout: 15_000,
  });

  // ── 2. Calendarios → crear calendario (mes/año actual, modo manual) ────
  await page.getByRole("link", { name: "Calendarios" }).click();
  await page.waitForURL("**/calendars");
  await page.getByRole("button", { name: "Nuevo calendario" }).click();
  await page.getByRole("button", { name: "Habilitar calendario" }).click();
  // La creación exitosa navega directo al grid (/calendars/<uuid>).
  await page.waitForURL(/\/calendars\/[0-9a-f-]{36}$/);
  await expect(
    page.getByText(`Calendario ${slot.monthName} ${slot.year} — Versión 1`),
  ).toBeVisible();
  await expect(page.locator(".calendar-grid")).toBeVisible();

  // ── 3. Asignación con advertencia + justificación ──────────────────────
  // Primer lunes del mes → fila Emergencia (primera área).
  const firstCell = page.locator(".calendar-cell").first();
  await firstCell.locator(".calendar-area-row").first().click();

  // El médico mensual aparece como "no disponible" (razón no-dura).
  await expect(page.getByText("No disponibles")).toBeVisible();
  const carlosRow = page
    .locator("div")
    .filter({ has: page.getByText(MONTHLY_DOCTOR_NAME, { exact: false }) })
    .filter({
      has: page.getByRole("button", { name: "Evaluar de todas formas" }),
    })
    .last();
  await carlosRow
    .getByRole("button", { name: "Evaluar de todas formas" })
    .click();

  // Paso de revisión de advertencias: marcar todas + justificación.
  await expect(page.getByText("Advertencias de reglas")).toBeVisible();
  const checkboxes = page.locator('.modal-panel input[type="checkbox"]');
  for (let i = 0; i < await checkboxes.count(); i++) {
    await checkboxes.nth(i).check();
  }
  // El label "Justificación (obligatoria)" es hermano del textarea (no lo
  // envuelve ni usa `for`): localizar por placeholder.
  await page
    .getByPlaceholder(
      "Ej. Necesidad operativa: es el único disponible para cubrir el servicio.",
    )
    .fill(JUSTIFICATION);
  await page.getByRole("button", { name: "Asignar con advertencias" }).click();

  // La asignación persiste y el grid muestra el chip con el nombre.
  await expect(page.getByText("Médico asignado.")).toBeVisible();
  await expect(firstCell.getByText(MONTHLY_DOCTOR_NAME)).toBeVisible();

  // ── 4. Aprobar la semana del slot ──────────────────────────────────────
  const weekRow = page.locator("tr", { hasText: slot.iso });
  await weekRow.getByRole("button", { name: "Aprobar" }).click();
  await expect(page.getByText("Semana aprobada.")).toBeVisible();
  await expect(weekRow.getByText("Aprobada")).toBeVisible();
  // El calendario pasa a estado "Parcial" (badge del encabezado).
  await expect(page.getByText("Parcial", { exact: true })).toBeVisible();
});

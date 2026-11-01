/**
 * Cuánto falta para que salga un aviso, en palabras: `23 h 41 min`.
 *
 * Se redondea hacia arriba: a falta de 30 segundos todavía «falta 1 min», y
 * no «faltan 0 min», que se lee como si ya hubiera salido.
 */
export function formatCountdown(millisecondsLeft: number): string {
  const totalMinutes = Math.ceil(millisecondsLeft / 60_000);
  if (totalMinutes <= 0) return "";

  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  return hours > 0 ? `${hours} h ${minutes} min` : `${minutes} min`;
}

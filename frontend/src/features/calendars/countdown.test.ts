import { describe, expect, it } from "vitest";
import { formatCountdown } from "./countdown";

const MINUTE = 60_000;

describe("formatCountdown", () => {
  it("dice horas y minutos cuando falta más de una hora", () => {
    expect(formatCountdown(23 * 60 * MINUTE + 41 * MINUTE)).toBe("23 h 41 min");
  });

  it("omite las horas cuando falta menos de una", () => {
    expect(formatCountdown(45 * MINUTE)).toBe("45 min");
  });

  it("redondea hacia arriba: medio minuto ya cuenta como uno", () => {
    expect(formatCountdown(30_000)).toBe("1 min");
  });

  it("no cuenta en negativo: sin tiempo restante devuelve vacío", () => {
    expect(formatCountdown(0)).toBe("");
    expect(formatCountdown(-5 * MINUTE)).toBe("");
  });
});

import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ToastProvider, useToast } from "./Toast";

function Trigger() {
  const { addToast } = useToast();
  return (
    <>
      <button onClick={() => addToast("success", "Guardado correctamente")}>ok</button>
      <button onClick={() => addToast("error", "Error al guardar")}>err</button>
    </>
  );
}

describe("Toast", () => {
  beforeEach(() => {
    vi.clearAllTimers();
  });

  it("muestra un toast de éxito al hacer click", async () => {
    const userEvent = await import("@testing-library/user-event");
    const user = userEvent.default.setup();
    render(<ToastProvider><Trigger /></ToastProvider>);
    await user.click(screen.getByText("ok"));
    expect(await screen.findByText("Guardado correctamente")).toBeInTheDocument();
  });

  it("muestra un toast de error", async () => {
    const userEvent = await import("@testing-library/user-event");
    const user = userEvent.default.setup();
    render(<ToastProvider><Trigger /></ToastProvider>);
    await user.click(screen.getByText("err"));
    expect(await screen.findByText("Error al guardar")).toBeInTheDocument();
  });
});

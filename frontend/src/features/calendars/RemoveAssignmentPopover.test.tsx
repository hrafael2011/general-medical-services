import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { RemoveAssignmentPopover } from "./RemoveAssignmentPopover";

describe("RemoveAssignmentPopover", () => {
  it("muestra el nombre del médico y la fecha", () => {
    render(<RemoveAssignmentPopover doctorName="Dr. García" date="2026-05-03" areaName="Emergencia" source="generated" onConfirm={vi.fn()} onClose={vi.fn()} isLoading={false} />);
    expect(screen.getByText("Dr. García")).toBeInTheDocument();
    expect(screen.getByText(/3 de mayo.*emergencia/i)).toBeInTheDocument();
  });

  it("llama onConfirm al confirmar", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(<RemoveAssignmentPopover doctorName="Dr. García" date="2026-05-03" areaName="Emergencia" source="generated" onConfirm={onConfirm} onClose={vi.fn()} isLoading={false} />);
    await user.click(screen.getByRole("button", { name: /quitar/i }));
    expect(onConfirm).toHaveBeenCalled();
  });

  it("llama onClose al cancelar", async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<RemoveAssignmentPopover doctorName="Dr. García" date="2026-05-03" areaName="Emergencia" source="generated" onConfirm={vi.fn()} onClose={onClose} isLoading={false} />);
    await user.click(screen.getByRole("button", { name: /cancelar/i }));
    expect(onClose).toHaveBeenCalled();
  });
});

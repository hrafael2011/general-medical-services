import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WorkloadReport } from "./WorkloadReport";

vi.mock("../../components/Toast", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

vi.mock("../../api/reports", () => ({
  reportsApi: {
    getWorkload: vi.fn().mockResolvedValue({
      period_label: "Mayo 2026",
      total_services: 2,
      active_doctors: 1,
      avg_per_doctor: 2,
      most_load: { name: "Dr. Prueba", total: 2 },
      least_load: { name: "Dr. Prueba", total: 2 },
      entries: [
        {
          doctor_id: "d1",
          name: "Dr. Prueba",
          rank: "Cabo",
          sex: "male",
          department: "Recursos Humanos",
          emergencia: 1,
          pista: 1,
          disponible: 0,
          total: 2,
          details: [],
        },
        {
          doctor_id: "d2",
          name: "Dra. Prueba",
          rank: "Sargento",
          sex: "female",
          department: null,
          emergencia: 0,
          pista: 0,
          disponible: 1,
          total: 1,
          details: [],
        },
      ],
    }),
    getWorkloadPdf: vi.fn(),
  },
}));

describe("WorkloadReport", () => {
  it("muestra el sexo en español", async () => {
    render(<WorkloadReport />);
    fireEvent.click(screen.getByRole("button", { name: /aplicar/i }));

    expect(await screen.findByText("Masculino")).toBeInTheDocument();
    expect(screen.getByText("Femenino")).toBeInTheDocument();
    expect(screen.queryByText("male")).not.toBeInTheDocument();
    expect(screen.queryByText("female")).not.toBeInTheDocument();
  });
});

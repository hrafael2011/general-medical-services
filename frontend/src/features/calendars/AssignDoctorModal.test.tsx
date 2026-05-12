import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { AssignDoctorModal } from "./AssignDoctorModal";
import { DoctorRead } from "../../api/doctors";

const DOCTORS: DoctorRead[] = [
  { id: "d1", name: "Dr. García Martínez", sex: "male", service_active: true, allowed_area_ids: [], active: true, participa_misiones: true, monthly_service_target: 4, monthly_service_max: 6, monthly_service_limit_mode: "warn_only", availability_mode: "weekly", rank_id: null, department_id: null, phone: null, notes: null, service_inactive_reason_id: null, service_inactive_detail: null, whatsapp_phone: null },
  { id: "d2", name: "Dr. López Ruiz",     sex: "male", service_active: true, allowed_area_ids: [], active: true, participa_misiones: true, monthly_service_target: 4, monthly_service_max: 6, monthly_service_limit_mode: "warn_only", availability_mode: "weekly", rank_id: null, department_id: null, phone: null, notes: null, service_inactive_reason_id: null, service_inactive_detail: null, whatsapp_phone: null },
  { id: "d3", name: "Dra. Torres",        sex: "female", service_active: false, allowed_area_ids: [], active: false, participa_misiones: false, monthly_service_target: 4, monthly_service_max: 6, monthly_service_limit_mode: "warn_only", availability_mode: "weekly", rank_id: null, department_id: null, phone: null, notes: null, service_inactive_reason_id: null, service_inactive_detail: null, whatsapp_phone: null },
];

describe("AssignDoctorModal", () => {
  it("muestra la fecha y área en el título", () => {
    render(<AssignDoctorModal date="2026-05-03" areaName="Emergencia" doctors={DOCTORS} onConfirm={vi.fn()} onClose={vi.fn()} isLoading={false} />);
    expect(screen.getByText(/3 de mayo.*emergencia/i)).toBeInTheDocument();
  });

  it("lista los médicos activos e inactivos", () => {
    render(<AssignDoctorModal date="2026-05-03" areaName="Emergencia" doctors={DOCTORS} onConfirm={vi.fn()} onClose={vi.fn()} isLoading={false} />);
    expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    expect(screen.getByText("Dr. López Ruiz")).toBeInTheDocument();
    expect(screen.getByText("Dra. Torres")).toBeInTheDocument();
  });

  it("filtra por nombre al escribir en el buscador", async () => {
    const user = userEvent.setup();
    render(<AssignDoctorModal date="2026-05-03" areaName="Emergencia" doctors={DOCTORS} onConfirm={vi.fn()} onClose={vi.fn()} isLoading={false} />);
    await user.type(screen.getByPlaceholderText(/buscar/i), "García");
    expect(screen.getByText("Dr. García Martínez")).toBeInTheDocument();
    expect(screen.queryByText("Dr. López Ruiz")).not.toBeInTheDocument();
  });

  it("llama onConfirm con el id del médico seleccionado", async () => {
    const onConfirm = vi.fn();
    const user = userEvent.setup();
    render(<AssignDoctorModal date="2026-05-03" areaName="Emergencia" doctors={DOCTORS} onConfirm={onConfirm} onClose={vi.fn()} isLoading={false} />);
    await user.click(screen.getByText("Dr. García Martínez"));
    await user.click(screen.getByRole("button", { name: /asignar/i }));
    expect(onConfirm).toHaveBeenCalledWith("d1", null);
  });

  it("el botón Asignar está deshabilitado sin selección", () => {
    render(<AssignDoctorModal date="2026-05-03" areaName="Emergencia" doctors={DOCTORS} onConfirm={vi.fn()} onClose={vi.fn()} isLoading={false} />);
    expect(screen.getByRole("button", { name: /asignar/i })).toBeDisabled();
  });
});

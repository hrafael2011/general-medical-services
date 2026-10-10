import { CalendarDays, CheckCircle2, Edit, PlusCircle, Search, Trash2, Users, X, XCircle } from "lucide-react";
import { QuickAvailabilityModal } from "./QuickAvailabilityModal";
import { AbsenceSection } from "./AbsenceSection";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ConfirmDialog } from "../../components/ConfirmDialog";
import {
  availabilityApi,
  AvailabilityRead,
  DeactivationReasonRead,
  doctorsApi,
  DoctorRead,
  ServiceAreaRead,
} from "../../api/doctors";

interface Props {
  onAdd: () => void;
  onEdit: (doctor: DoctorRead) => void;
}

export function DoctorList({ onAdd, onEdit }: Props) {
  const qc = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [monthlyFilter, setMonthlyFilter] = useState(false);
  const [selectedDoctor, setSelectedDoctor] = useState<DoctorRead | null>(null);
  const [actionError, setActionError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [avModalDoctor, setAvModalDoctor] = useState<{ id: string; name: string } | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["doctors", statusFilter, monthlyFilter],
    queryFn: () => doctorsApi.list(statusFilter, monthlyFilter ? "monthly" : undefined),
  });

  const { data: ranks } = useQuery({
    queryKey: ["ranks"],
    queryFn: doctorsApi.listRanks,
  });

  const { data: serviceAreas } = useQuery({
    queryKey: ["service-areas"],
    queryFn: doctorsApi.listServiceAreas,
  });

  const { data: departments } = useQuery({
    queryKey: ["departments"],
    queryFn: doctorsApi.listDepartments,
  });

  const { data: deactivationReasons } = useQuery({
    queryKey: ["deactivation-reasons"],
    queryFn: () => doctorsApi.listDeactivationReasons(),
  });

  const { data: availability } = useQuery({
    queryKey: ["doctor-availability", selectedDoctor?.id],
    queryFn: () => availabilityApi.list(selectedDoctor!.id),
    enabled: !!selectedDoctor,
  });

  const rankMap = Object.fromEntries((ranks ?? []).map(r => [r.id, r.name]));
  const departmentMap = Object.fromEntries((departments ?? []).map(d => [d.id, d.name]));
  const areaMap = Object.fromEntries(
    (serviceAreas ?? []).map((a: ServiceAreaRead) => [a.id, a.display_name])
  );
  const reasonMap = Object.fromEntries((deactivationReasons ?? []).map(r => [r.id, r.display_name]));

  const [deleteTarget, setDeleteTarget] = useState<DoctorRead | null>(null);

  const deleteMutation = useMutation({
    mutationFn: (id: string) => doctorsApi.delete(id),
    onSuccess: () => {
      setDeleteTarget(null);
      setSelectedDoctor(null);
      qc.invalidateQueries({ queryKey: ["doctors"] });
    },
    onError: (err: Error) => setActionError(err.message),
  });

  if (isLoading) return <p className="loading-text">Cargando medicos…</p>;
  if (error) return <p className="error-text">Error al cargar medicos.</p>;

  const doctors = data?.items ?? [];
  const normalizedSearch = normalizeText(searchTerm);
  const filteredDoctors = normalizedSearch
    ? doctors.filter(doc => normalizeText(doc.name).includes(normalizedSearch))
    : doctors;
  function handleOpenProfile(doctor: DoctorRead) {
    setSelectedDoctor(doctor);
    setActionError("");
  }

  return (
    <div className="feature-panel">
      <div className="feature-header">
        <div className="feature-title">
          <Users size={20} />
          <h2>Medicos</h2>
          <span className="count-badge">{data?.total ?? 0}</span>
        </div>
        <div className="feature-actions">
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={statusFilter === "active"}
              onChange={e => setStatusFilter(e.target.checked ? "active" : "all")}
            />
            Solo activos
          </label>
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={statusFilter === "inactive"}
              onChange={e => setStatusFilter(e.target.checked ? "inactive" : "all")}
            />
            Solo inactivos
          </label>
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={monthlyFilter}
              onChange={e => setMonthlyFilter(e.target.checked)}
            />
            Solo disponibilidad mensual
          </label>
          <button className="btn-primary" onClick={onAdd}>
            <PlusCircle size={16} />
            Agregar
          </button>
        </div>
      </div>

      <div className="doctor-list-toolbar">
        <div className="search-field">
          <Search size={16} />
          <input
            value={searchTerm}
            onChange={event => setSearchTerm(event.target.value)}
            placeholder="Buscar por nombre o apellido"
            aria-label="Buscar médico por nombre o apellido"
          />
        </div>
      </div>

      {doctors.length === 0 ? (
        <p className="empty-text">No hay medicos registrados.</p>
      ) : filteredDoctors.length === 0 ? (
        <p className="empty-text">No hay medicos que coincidan con la busqueda.</p>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Rango</th>
                <th>Departamento</th>
                <th>Estado servicio</th>
                <th>Áreas</th>
                <th>Disponibilidad</th>
                <th>Misiones</th>
              </tr>
            </thead>
            <tbody>
              {filteredDoctors.map(doc => (
                <tr
                  key={doc.id}
                  className={`clickable-row${!doc.service_active ? " row-inactive" : ""}`}
                  onClick={() => handleOpenProfile(doc)}
                  onKeyDown={event => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      handleOpenProfile(doc);
                    }
                  }}
                  tabIndex={0}
                  role="button"
                >
                  <td className="cell-name">{doc.name}</td>
                  <td>{doc.rank_id ? rankMap[doc.rank_id] ?? "—" : "—"}</td>
                  <td>{doc.department_id ? departmentMap[doc.department_id] ?? "—" : "—"}</td>
                  <td>
                    <span
                      className={`service-status-pill${doc.service_active ? " service-status-pill--active" : " service-status-pill--inactive"}`}
                      title={!doc.service_active
                        ? `${reasonMap[doc.service_inactive_reason_id ?? ""] || "Sin razón"}${doc.service_inactive_detail ? ` — ${doc.service_inactive_detail}` : ""}`
                        : undefined}
                      style={!doc.service_active ? { cursor: "help" } : undefined}
                    >
                      <span className="service-status-pill__track">
                        <span className="service-status-pill__knob" />
                      </span>
                      {doc.service_active ? "Activo" : "Inactivo"}
                    </span>
                  </td>
                  <td className="cell-areas">
                    {doc.allowed_area_ids.length === 0
                      ? <span className="no-areas">—</span>
                      : (
                        <div className="area-tooltip-wrapper">
                          <span className="area-count">{doc.allowed_area_ids.length} área(s)</span>
                          <span className="area-tooltip">
                            {doc.allowed_area_ids.map(id => areaMap[id] ?? id).join(", ")}
                          </span>
                        </div>
                      )}
                  </td>
                  <td>
                    {doc.availability_mode === "monthly" && doc.service_active ? (
                      <button
                        className="btn-ghost"
                        style={{ fontSize: "0.8rem", padding: "2px 8px", whiteSpace: "nowrap" }}
                        onClick={(e) => { e.stopPropagation(); setAvModalDoctor({ id: doc.id, name: doc.name }); }}
                      >
                        <CalendarDays size={14} /> Asignar días
                      </button>
                    ) : "—"}
                  </td>
                  <td>{doc.service_active && doc.participa_misiones ? "Sí" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedDoctor && (
        <DoctorProfileModal
          doctor={selectedDoctor}
          rankName={selectedDoctor.rank_id ? rankMap[selectedDoctor.rank_id] : undefined}
          departmentName={selectedDoctor.department_id ? departmentMap[selectedDoctor.department_id] : undefined}
          areaNames={selectedDoctor.allowed_area_ids.map(id => areaMap[id] ?? id)}
          availability={availability ?? []}
          inactiveReasonName={
            selectedDoctor.service_inactive_reason_id
              ? reasonMap[selectedDoctor.service_inactive_reason_id]
              : undefined
          }
          reasons={deactivationReasons ?? []}
          onDelete={() => setDeleteTarget(selectedDoctor)}
          onClose={() => setSelectedDoctor(null)}
          onEdit={() => {
            onEdit(selectedDoctor);
            setSelectedDoctor(null);
          }}
        />
      )}

      {avModalDoctor && (
        <QuickAvailabilityModal
          doctorId={avModalDoctor.id}
          doctorName={avModalDoctor.name}
          onClose={() => setAvModalDoctor(null)}
          onSaved={() => {
            setAvModalDoctor(null);
            qc.invalidateQueries({ queryKey: ["doctors"] });
            qc.invalidateQueries({ queryKey: ["doctor-availability"] });
          }}
        />
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Eliminar médico"
        message={`¿Estás seguro de eliminar a ${deleteTarget?.name}?`}
        confirmLabel="Sí, eliminar"
        variant="danger"
        onConfirm={() => {
          if (deleteTarget) deleteMutation.mutate(deleteTarget.id);
        }}
        onCancel={() => setDeleteTarget(null)}
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}

interface DoctorProfileModalProps {
  doctor: DoctorRead;
  rankName?: string;
  departmentName?: string;
  areaNames: string[];
  availability: AvailabilityRead[];
  inactiveReasonName?: string;
  reasons: DeactivationReasonRead[];
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
}

function DoctorProfileModal({
  doctor,
  rankName,
  departmentName,
  areaNames,
  availability,
  inactiveReasonName,
  reasons,
  onClose,
  onEdit,
  onDelete,
}: DoctorProfileModalProps) {
  const availabilityLabels = normalizeAvailability(availability, doctor.availability_mode);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-panel doctor-profile-panel" onClick={event => event.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h2>{doctor.name}</h2>
            <p className="profile-subtitle">{rankName ?? "Sin rango"}</p>
          </div>
          <button className="btn-icon" onClick={onClose} aria-label="Cerrar perfil">
            <X size={20} />
          </button>
        </div>

        <div className="profile-status-row">
          <span className={doctor.active ? "status-active" : "status-inactive"}>
            {doctor.active ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
            {doctor.active ? "Activo en sistema" : "Inactivo en sistema"}
          </span>
          <span className={doctor.service_active ? "status-active" : "status-inactive"}>
            {doctor.service_active ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
            {doctor.service_active ? "Activo para servicio" : "Inactivo para servicio"}
          </span>
        </div>

        <section className="profile-section">
          <h3>Información</h3>
          <div className="profile-grid">
            <ProfileItem label="Sexo" value={doctor.sex === "male" ? "Masculino" : "Femenino"} />
            <ProfileItem label="Departamento" value={departmentName ?? "Sin departamento"} />
            <ProfileItem label="WhatsApp" value={doctor.whatsapp_phone ?? "No registrado"} />
            <ProfileItem
              label="Misiones"
              value={doctor.service_active && doctor.participa_misiones ? "Participa" : "No participa"}
            />
            <ProfileItem label="Áreas" value={areaNames.length > 0 ? areaNames.join(", ") : "Sin áreas asignadas"} />
            <ProfileItem
              label="Disponibilidad"
              value={availabilityLabels.length > 0 ? availabilityLabels.join(" · ") : "Sin disponibilidad registrada"}
            />
          </div>
        </section>

        {/* Eje 2 completo: la ausencia con fechas y la que no tiene fecha, juntas. */}
        <AbsenceSection
          doctorId={doctor.id}
          reasons={reasons}
          serviceActive={doctor.service_active}
          inactiveReasonName={inactiveReasonName ?? null}
          inactiveDetail={doctor.service_inactive_detail ?? null}
        />

        <section className="profile-section">
          <h3>Acciones</h3>
          <div className="profile-actions">
            <button className="btn-secondary" onClick={onEdit}>
              <Edit size={16} />
              Editar médico
            </button>
            <button className="btn-ghost btn-danger" onClick={onDelete}>
              <Trash2 size={16} />
              Eliminar médico
            </button>
            {/* El estado de servicio no se pone a mano: se registra una ausencia arriba y
                el sistema la aplica (y la levanta) por fecha. Ver la extensión v1.3.0 del
                spec de licencias. */}
          </div>
        </section>
      </div>
    </div>
  );
}

function ProfileItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="profile-item">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function normalizeText(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .trim();
}

function normalizeAvailability(availability: AvailabilityRead[], availabilityMode?: string) {
  const dayNames = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
  const weekOrder = ["Primer", "Segundo", "Tercer", "Cuarto"];

  // Monthly mode: avisa sus días cada mes
  if (availabilityMode === "monthly") {
    const monthNames = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
    const monthly = availability
      .filter(item => item.availability_type === "monthly_variable" && (item.available_dates?.length ?? 0) > 0)
      .sort((a, b) => (b.year ?? 0) - (a.year ?? 0) || (b.month ?? 0) - (a.month ?? 0));
    if (monthly.length === 0) return ["Mensual: avisa sus días cada mes"];
    return monthly.map(item => {
      const month = item.month ?? 0;
      const period = item.year && month >= 1 && month <= 12
        ? `${monthNames[month - 1]} ${item.year}`
        : "";
      return `Mensual${period ? ` (${period})` : ""}: días ${(item.available_dates ?? []).join(", ")}`;
    });
  }

  return availability.map(item => {
    if (item.availability_type === "weekly_fixed" && item.days_of_week?.length) {
      const shortDays = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
      return `Semanal: ${item.days_of_week.map(day => shortDays[day] ?? String(day)).join(", ")}`;
    }
    if (item.availability_type === "monthly_variable" && item.available_dates?.length) {
      return `Mensual: días ${item.available_dates.join(", ")}`;
    }
    if (item.availability_type === "recurring" && item.weekday !== null) {
      const prefix = item.week_number === -1 ? "Último" : (weekOrder[item.week_number ?? 0] ?? `${(item.week_number ?? 0) + 1}º`);
      return `${prefix} ${dayNames[item.weekday] ?? "día"} de cada mes`;
    }
    return "Disponibilidad registrada";
  });
}

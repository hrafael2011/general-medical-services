import { Ban, CheckCircle2, Edit, PlusCircle, RefreshCw, Search, Trash2, Users, X, XCircle } from "lucide-react";
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
  const [activeOnly, setActiveOnly] = useState(false);
  const [selectedDoctor, setSelectedDoctor] = useState<DoctorRead | null>(null);
  const [reasonId, setReasonId] = useState("");
  const [detail, setDetail] = useState("");
  const [actionError, setActionError] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const { data, isLoading, error } = useQuery({
    queryKey: ["doctors", activeOnly],
    queryFn: () => doctorsApi.list(activeOnly),
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
    queryKey: ["deactivation-reasons", selectedDoctor?.sex],
    queryFn: () => doctorsApi.listDeactivationReasons(selectedDoctor?.sex),
    enabled: !!selectedDoctor,
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

  const reactivate = useMutation({
    mutationFn: (id: string) => doctorsApi.reactivateService(id),
    onSuccess: (updated) => {
      setSelectedDoctor(updated);
      setReasonId("");
      setDetail("");
      setActionError("");
      qc.invalidateQueries({ queryKey: ["doctors"] });
    },
    onError: (err: Error) => setActionError(err.message),
  });

  const deactivate = useMutation({
    mutationFn: ({ id, reasonId, detail }: { id: string; reasonId: string; detail?: string }) =>
      doctorsApi.deactivateService(id, reasonId, detail),
    onSuccess: (updated) => {
      setSelectedDoctor(updated);
      setReasonId("");
      setDetail("");
      setActionError("");
      qc.invalidateQueries({ queryKey: ["doctors"] });
    },
    onError: (err: Error) => setActionError(err.message),
  });

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
  const selectedReason = (deactivationReasons ?? []).find(reason => reason.id === reasonId);

  function handleOpenProfile(doctor: DoctorRead) {
    setSelectedDoctor(doctor);
    setReasonId("");
    setDetail("");
    setActionError("");
  }

  function submitDeactivation() {
    if (!selectedDoctor) return;
    if (!reasonId) {
      setActionError("Selecciona una razón para desactivar el servicio.");
      return;
    }
    if (selectedReason?.requires_detail && detail.trim().length === 0) {
      setActionError("Especifica el detalle de la razón seleccionada.");
      return;
    }
    deactivate.mutate({
      id: selectedDoctor.id,
      reasonId,
      detail: detail.trim() || undefined,
    });
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
            <input type="checkbox" checked={activeOnly} onChange={e => setActiveOnly(e.target.checked)} />
            Solo activos para servicio
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
                <th>Status servicio</th>
                <th>Áreas</th>
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
          selectedReasonId={reasonId}
          detail={detail}
          actionError={actionError}
          isDeactivating={deactivate.isPending}
          isReactivating={reactivate.isPending}
          onDelete={() => setDeleteTarget(selectedDoctor)}
          onClose={() => setSelectedDoctor(null)}
          onEdit={() => {
            onEdit(selectedDoctor);
            setSelectedDoctor(null);
          }}
          onReasonChange={(nextReasonId) => {
            setReasonId(nextReasonId);
            setActionError("");
          }}
          onDetailChange={setDetail}
          onDeactivate={submitDeactivation}
          onReactivate={() => reactivate.mutate(selectedDoctor.id)}
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
  selectedReasonId: string;
  detail: string;
  actionError: string;
  isDeactivating: boolean;
  isReactivating: boolean;
  onClose: () => void;
  onEdit: () => void;
  onDelete: () => void;
  onReasonChange: (reasonId: string) => void;
  onDetailChange: (detail: string) => void;
  onDeactivate: () => void;
  onReactivate: () => void;
}

function DoctorProfileModal({
  doctor,
  rankName,
  departmentName,
  areaNames,
  availability,
  inactiveReasonName,
  reasons,
  selectedReasonId,
  detail,
  actionError,
  isDeactivating,
  isReactivating,
  onClose,
  onEdit,
  onDelete,
  onReasonChange,
  onDetailChange,
  onDeactivate,
  onReactivate,
}: DoctorProfileModalProps) {
  const selectedReason = reasons.find(reason => reason.id === selectedReasonId);
  const availabilityLabels = normalizeAvailability(availability);

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
            <ProfileItem label="Teléfono" value={doctor.phone ?? "No registrado"} />
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

        {!doctor.service_active && (
          <section className="profile-section">
            <h3>Estado de servicio</h3>
            <div className="profile-grid">
              <ProfileItem label="Razón" value={inactiveReasonName ?? "No especificada"} />
              <ProfileItem label="Detalle" value={doctor.service_inactive_detail ?? "Sin detalle"} />
            </div>
          </section>
        )}

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
            {doctor.service_active ? (
              <div className="deactivation-box">
                <label>
                  Razón para desactivar servicio
                  <select value={selectedReasonId} onChange={event => onReasonChange(event.target.value)}>
                    <option value="">Seleccionar razón</option>
                    {reasons.filter(reason => reason.active).map(reason => (
                      <option key={reason.id} value={reason.id}>{reason.display_name}</option>
                    ))}
                  </select>
                </label>
                {selectedReason?.requires_detail && (
                  <label>
                    Detalle
                    <textarea
                      value={detail}
                      onChange={event => onDetailChange(event.target.value)}
                      placeholder="Especifica la razón"
                    />
                  </label>
                )}
                {actionError && <p className="form-error">{actionError}</p>}
                <button className="btn-ghost btn-danger" onClick={onDeactivate} disabled={isDeactivating}>
                  <Ban size={16} />
                  {isDeactivating ? "Desactivando…" : "Desactivar para servicio"}
                </button>
              </div>
            ) : (
              <div className="deactivation-box">
                {actionError && <p className="form-error">{actionError}</p>}
                <button className="btn-ghost btn-green" onClick={onReactivate} disabled={isReactivating}>
                  <RefreshCw size={16} />
                  {isReactivating ? "Reactivando…" : "Reactivar servicio"}
                </button>
              </div>
            )}
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

function normalizeAvailability(availability: AvailabilityRead[]) {
  const dayNames = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
  return availability.map(item => {
    if (item.availability_type === "weekly_fixed" && item.days_of_week?.length) {
      return `Semanal: ${item.days_of_week.map(day => dayNames[day] ?? String(day)).join(", ")}`;
    }
    if (item.availability_type === "monthly_variable" && item.available_dates?.length) {
      return `Mensual: días ${item.available_dates.join(", ")}`;
    }
    if (item.availability_type === "recurring" && item.weekday !== null) {
      const weekLabel = item.week_number === -1 ? "última" : `${(item.week_number ?? 0) + 1}ª`;
      return `Fijo: ${weekLabel} semana, ${dayNames[item.weekday] ?? item.weekday}`;
    }
    return "Disponibilidad registrada";
  });
}

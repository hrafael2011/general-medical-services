import { Users, PlusCircle, CheckCircle2, XCircle, RefreshCw } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { doctorsApi, DoctorRead } from "../../api/doctors";

interface Props {
  onAdd: () => void;
  onEdit: (doctor: DoctorRead) => void;
}

export function DoctorList({ onAdd, onEdit }: Props) {
  const qc = useQueryClient();
  const [activeOnly, setActiveOnly] = useState(false);

  const { data, isLoading, error } = useQuery({
    queryKey: ["doctors", activeOnly],
    queryFn: () => doctorsApi.list(activeOnly),
  });

  const { data: ranks } = useQuery({
    queryKey: ["ranks"],
    queryFn: doctorsApi.listRanks,
  });

  const rankMap = Object.fromEntries((ranks ?? []).map(r => [r.id, r.name]));

  const reactivate = useMutation({
    mutationFn: (id: string) => doctorsApi.reactivateService(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["doctors"] }),
  });

  if (isLoading) return <p className="loading-text">Cargando medicos…</p>;
  if (error) return <p className="error-text">Error al cargar medicos.</p>;

  const doctors = data?.items ?? [];

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
            Solo activos
          </label>
          <button className="btn-primary" onClick={onAdd}>
            <PlusCircle size={16} />
            Agregar
          </button>
        </div>
      </div>

      {doctors.length === 0 ? (
        <p className="empty-text">No hay medicos registrados.</p>
      ) : (
        <div className="table-wrapper">
          <table className="data-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Rango</th>
                <th>Sexo</th>
                <th>Servicio</th>
                <th>Áreas</th>
                <th>Misiones</th>
                <th>Meta/mes</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {doctors.map(doc => (
                <tr key={doc.id} className={!doc.service_active ? "row-inactive" : ""}>
                  <td className="cell-name">{doc.name}</td>
                  <td>{doc.rank_id ? rankMap[doc.rank_id] ?? "—" : "—"}</td>
                  <td>
                    <span className={`sex-badge sex-${doc.sex}`}>
                      {doc.sex === "male" ? "M" : "F"}
                    </span>
                  </td>
                  <td>
                    {doc.service_active
                      ? <span className="status-active"><CheckCircle2 size={14} /> Activo</span>
                      : <span className="status-inactive"><XCircle size={14} /> Inactivo</span>}
                  </td>
                  <td className="cell-areas">
                    {doc.allowed_area_ids.length === 0
                      ? <span className="no-areas">—</span>
                      : <span className="area-count">{doc.allowed_area_ids.length} area(s)</span>}
                  </td>
                  <td>{doc.participa_misiones ? "Sí" : "No"}</td>
                  <td>{doc.monthly_service_target}/{doc.monthly_service_max}</td>
                  <td className="cell-actions">
                    <button className="btn-ghost" onClick={() => onEdit(doc)}>Editar</button>
                    {!doc.service_active && (
                      <button
                        className="btn-ghost btn-green"
                        onClick={() => reactivate.mutate(doc.id)}
                        disabled={reactivate.isPending}
                      >
                        <RefreshCw size={14} />
                        Reactivar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

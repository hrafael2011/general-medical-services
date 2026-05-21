interface CardDef {
  label: string;
  value: string | number;
}

export function ReportSummaryCards({ cards }: { cards: CardDef[] }) {
  if (cards.length === 0) return null;
  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
        gap: "12px",
        marginBottom: "20px",
      }}
    >
      {cards.map(c => (
        <div
          key={c.label}
          style={{
            background: "#f9fafb",
            borderRadius: "8px",
            padding: "12px 16px",
            border: "1px solid #e5e7eb",
          }}
        >
          <div style={{ fontSize: "0.75rem", color: "#6b7280", marginBottom: "4px" }}>{c.label}</div>
          <div style={{ fontSize: "1.25rem", fontWeight: 700, color: "#111827" }}>{c.value}</div>
        </div>
      ))}
    </div>
  );
}

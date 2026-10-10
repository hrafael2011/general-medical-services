import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TelegramLinks } from "./TelegramLinks";
import type { UserRead } from "../../api/admin";
import type { DoctorRead } from "../../api/doctors";

vi.mock("../../api/telegram", () => ({
  telegramApi: {
    listLinks: vi.fn(),
    listLinkTokens: vi.fn(),
    createLink: vi.fn(),
    deleteLink: vi.fn(),
    generateLinkToken: vi.fn(),
  },
}));

vi.mock("../../api/admin", () => ({
  adminApi: {
    listUsers: vi.fn(),
  },
}));

vi.mock("../../api/doctors", () => ({
  doctorsApi: {
    list: vi.fn(),
  },
}));

vi.mock("../../components/Toast", () => ({
  useToast: () => ({ addToast: vi.fn() }),
}));

function renderComponent() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TelegramLinks />
    </QueryClientProvider>
  );
}

// --- Fixtures -------------------------------------------------------------

const ADMIN_LINKED: UserRead = {
  id: "u-admin",
  name: "Admin Vinculado",
  email: "admin@example.com",
  role: "admin",
  active: true,
  must_change_password: false,
  is_superadmin: false,
  permissions: [],
  telegram_chat_id: "555000111",
};

const ENCARGADO_UNLINKED: UserRead = {
  ...ADMIN_LINKED,
  id: "u-enc",
  name: "Encargado Sin Telegram",
  email: "encargado@example.com",
  role: "encargado",
  telegram_chat_id: null,
};

function doctor(id: string, name: string, hasTelegram: boolean): DoctorRead {
  return {
    id,
    name,
    sex: "male",
    rank_id: null,
    department_id: null,
    notes: null,
    active: true,
    service_active: true,
    service_inactive_reason_id: null,
    service_inactive_detail: null,
    participa_misiones: true,
    whatsapp_phone: null,
    has_telegram: hasTelegram,
    monthly_service_target: 3,
    monthly_service_max: 3,
    monthly_service_limit_mode: "hard",
    availability_mode: "monthly",
    allowed_area_ids: [],
  };
}

/** Wires every query the component fires, so no test reaches the network. */
async function setupMocks(options: {
  admins?: UserRead[];
  encargados?: UserRead[];
  doctors?: DoctorRead[];
  links?: Awaited<ReturnType<typeof import("../../api/telegram").telegramApi.listLinks>>;
} = {}) {
  const { telegramApi } = await import("../../api/telegram");
  const { adminApi } = await import("../../api/admin");
  const { doctorsApi } = await import("../../api/doctors");

  vi.mocked(telegramApi.listLinks).mockResolvedValue(options.links ?? []);
  vi.mocked(telegramApi.listLinkTokens).mockResolvedValue([]);
  vi.mocked(adminApi.listUsers).mockImplementation(async (role?: string) => {
    if (role === "admin") return options.admins ?? [];
    if (role === "encargado") return options.encargados ?? [];
    return [...(options.admins ?? []), ...(options.encargados ?? [])];
  });
  vi.mocked(doctorsApi.list).mockResolvedValue({
    items: options.doctors ?? [],
    total: (options.doctors ?? []).length,
  });
}

/** The row that owns a given name, so queries stay scoped to one table row. */
function rowOf(name: string): HTMLTableRowElement {
  return screen.getByText(name).closest("tr") as HTMLTableRowElement;
}

describe("TelegramLinks", () => {
  it("muestra el título de la sección", async () => {
    await setupMocks();

    renderComponent();

    const heading = await screen.findByRole("heading", { name: /telegram/i });
    expect(heading).toBeInTheDocument();
  });

  it("muestra estado vacío cuando no hay vínculos", async () => {
    await setupMocks();

    renderComponent();

    const emptyText = await screen.findByText(/no hay vinculos/i);
    expect(emptyText).toBeInTheDocument();
  });

  it("muestra la tabla cuando hay vínculos", async () => {
    await setupMocks({
      links: [
        {
          id: "l1",
          telegram_user_id: "123456",
          telegram_username: "@test",
          user_id: "u1",
          linked_at: "2026-01-01T00:00:00",
          linked_by: null,
          last_used_at: null,
          active: true,
        },
      ],
    });

    renderComponent();

    const telegramUserId = await screen.findByText("123456");
    expect(telegramUserId).toBeInTheDocument();
  });

  // --- ¿Quién puede recibir avisos? ---------------------------------------

  it("marca con ✅ a los usuarios vinculados y con ❌ a los que no", async () => {
    await setupMocks({
      admins: [ADMIN_LINKED],
      encargados: [ENCARGADO_UNLINKED],
    });

    renderComponent();

    const linkedRow = (await screen.findByText("Admin Vinculado")).closest("tr")!;
    expect(within(linkedRow).getByText("✅ Sí")).toBeInTheDocument();

    const unlinkedRow = rowOf("Encargado Sin Telegram");
    expect(within(unlinkedRow).getByText("❌ No")).toBeInTheDocument();
  });

  it("solo ofrece 'Generar link' a los usuarios que NO reciben", async () => {
    await setupMocks({
      admins: [ADMIN_LINKED],
      encargados: [ENCARGADO_UNLINKED],
    });

    renderComponent();

    await screen.findByText("Admin Vinculado");

    expect(
      within(rowOf("Admin Vinculado")).queryByRole("button", { name: /generar link/i })
    ).toBeNull();
    expect(
      within(rowOf("Encargado Sin Telegram")).getByRole("button", { name: /generar link/i })
    ).toBeInTheDocument();
  });

  it("genera el link de invitación desde la fila del usuario sin Telegram", async () => {
    const { telegramApi } = await import("../../api/telegram");
    await setupMocks({
      admins: [ADMIN_LINKED],
      encargados: [ENCARGADO_UNLINKED],
    });
    vi.mocked(telegramApi.generateLinkToken).mockResolvedValue({
      link_token: "tok-123",
      deep_link_url: "https://t.me/BotDeAvisos?start=tok-123",
      expires_at: "2026-01-02T00:00:00",
    });

    renderComponent();

    fireEvent.click(
      within((await screen.findByText("Encargado Sin Telegram")).closest("tr")!)
        .getByRole("button", { name: /generar link/i })
    );

    await waitFor(() => expect(telegramApi.generateLinkToken).toHaveBeenCalledWith("u-enc"));
    const url = await screen.findByText("https://t.me/BotDeAvisos?start=tok-123");
    expect(url).toBeInTheDocument();
  });

  it("resume cuántos usuarios y médicos pueden recibir avisos", async () => {
    await setupMocks({
      admins: [ADMIN_LINKED],
      encargados: [ENCARGADO_UNLINKED],
      doctors: [doctor("d1", "Dr. Con Telegram", true), doctor("d2", "Dr. Sin Telegram", false)],
    });

    renderComponent();

    const summary = await screen.findByText(/Usuarios:/);
    await waitFor(() => expect(summary).toHaveTextContent(/Usuarios: 1 de 2/));
    expect(summary).toHaveTextContent(/Médicos: 1 de 2/);
  });

  it("el filtro 'Ver solo los que NO reciben' oculta a los que sí reciben", async () => {
    await setupMocks({
      admins: [ADMIN_LINKED],
      encargados: [ENCARGADO_UNLINKED],
      doctors: [doctor("d1", "Dr. Con Telegram", true), doctor("d2", "Dr. Sin Telegram", false)],
    });

    renderComponent();

    const checkbox = await screen.findByRole("checkbox", {
      name: /ver solo los que no reciben/i,
    });
    fireEvent.click(checkbox);

    await waitFor(() => expect(screen.queryByText("Admin Vinculado")).toBeNull());
    expect(screen.queryByText("Dr. Con Telegram")).toBeNull();
    expect(screen.getByText("Encargado Sin Telegram")).toBeInTheDocument();
    expect(screen.getByText("Dr. Sin Telegram")).toBeInTheDocument();
  });

  it("ofrece instrucciones solo a los médicos sin Telegram, y las copia", async () => {
    const writeText = vi.fn();
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    await setupMocks({
      doctors: [doctor("d1", "Dr. Con Telegram", true), doctor("d2", "Dr. Sin Telegram", false)],
    });

    renderComponent();

    const linkedRow = (await screen.findByText("Dr. Con Telegram")).closest("tr")!;
    expect(within(linkedRow).getByText("✅ Sí")).toBeInTheDocument();
    expect(within(linkedRow).queryByRole("button", { name: /instrucciones/i })).toBeNull();

    const unlinkedRow = rowOf("Dr. Sin Telegram");
    expect(within(unlinkedRow).getByText("❌ No")).toBeInTheDocument();
    fireEvent.click(within(unlinkedRow).getByRole("button", { name: /instrucciones/i }));

    expect(writeText).toHaveBeenCalledTimes(1);
    const copied = writeText.mock.calls[0][0] as string;
    expect(copied).toContain("/start");
    expect(copied).toContain("8091234567");
  });
});

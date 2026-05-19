import { render, screen, act, waitFor } from "@testing-library/react";
import { beforeEach, describe, it, expect, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";
import { authApi } from "../api/auth";
import { setToken } from "../api/client";

vi.mock("../api/auth", () => ({
  login: vi.fn().mockResolvedValue({
    access_token: "tok",
    user: { id: "1", name: "Admin", email: "a@b.com", role: "admin", active: true, must_change_password: false },
  }),
  authApi: {
    me: vi.fn(),
  },
}));

function Consumer() {
  const { currentUser, isAuthLoading, logout } = useAuth();
  return (
    <div>
      <span data-testid="loading">{isAuthLoading ? "loading" : "ready"}</span>
      <span data-testid="user">{currentUser?.name ?? "none"}</span>
      <button onClick={logout}>logout</button>
    </div>
  );
}

describe("AuthContext", () => {
  beforeEach(() => {
    localStorage.clear();
    setToken(null);
    vi.clearAllMocks();
  });

  it("starts with no user", () => {
    render(<AuthProvider><Consumer /></AuthProvider>);
    expect(screen.getByTestId("user").textContent).toBe("none");
  });

  it("restores current user from stored token on reload", async () => {
    localStorage.setItem("auth_token", "saved-token");
    vi.mocked(authApi.me).mockResolvedValueOnce({
      id: "1",
      name: "Admin",
      email: "a@b.com",
      role: "admin",
      active: true,
      must_change_password: false,
    });

    render(<AuthProvider><Consumer /></AuthProvider>);

    expect(screen.getByTestId("loading").textContent).toBe("loading");
    await waitFor(() => {
      expect(screen.getByTestId("user").textContent).toBe("Admin");
      expect(screen.getByTestId("loading").textContent).toBe("ready");
    });
    expect(authApi.me).toHaveBeenCalledOnce();
  });

  it("logout clears user", async () => {
    const { getByRole } = render(<AuthProvider><Consumer /></AuthProvider>);
    await act(async () => getByRole("button").click());
    expect(screen.getByTestId("user").textContent).toBe("none");
  });
});

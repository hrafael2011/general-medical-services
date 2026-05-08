import { render, screen, act } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { AuthProvider, useAuth } from "./AuthContext";

vi.mock("../api/auth", () => ({
  login: vi.fn().mockResolvedValue({
    access_token: "tok",
    user: { id: "1", name: "Admin", email: "a@b.com", role: "admin", must_change_password: false },
  }),
}));

function Consumer() {
  const { currentUser, logout } = useAuth();
  return (
    <div>
      <span data-testid="user">{currentUser?.name ?? "none"}</span>
      <button onClick={logout}>logout</button>
    </div>
  );
}

describe("AuthContext", () => {
  it("starts with no user", () => {
    render(<AuthProvider><Consumer /></AuthProvider>);
    expect(screen.getByTestId("user").textContent).toBe("none");
  });

  it("logout clears user", async () => {
    const { getByRole } = render(<AuthProvider><Consumer /></AuthProvider>);
    await act(async () => getByRole("button").click());
    expect(screen.getByTestId("user").textContent).toBe("none");
  });
});

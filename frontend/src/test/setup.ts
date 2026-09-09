import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";
import { vi } from "vitest";

// Esperas async de testing-library más tolerantes: los findBy fallaban por
// contención entre workers paralelos con el default de 1s.
configure({ asyncUtilTimeout: 5000 });

vi.stubGlobal("open", vi.fn());

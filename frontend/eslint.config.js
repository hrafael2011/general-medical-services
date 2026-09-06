import js from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    // Los specs de Playwright tienen su propio runner/transpilador.
    ignores: ["dist", "e2e/**", "playwright.config.ts"],
  },
);


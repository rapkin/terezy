import { useEffect, useState } from "react";

/**
 * FR-042: the theme follows the operating system's setting and is switchable.
 *
 * It changes no value, no mark and no ordering -- nothing below this line reads it, which is why
 * the whole switch is one attribute on the document element.
 */
export type Theme = "system" | "light" | "dark";

function resolved(theme: Theme): "light" | "dark" | null {
  if (theme === "system") return null;
  return theme;
}

export function applyTheme(theme: Theme, root: HTMLElement): void {
  const chosen = resolved(theme);
  if (chosen === null) root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", chosen);
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("system");
  useEffect(() => {
    applyTheme(theme, document.documentElement);
  }, [theme]);
  return (
    <label className="text-xs">
      theme{" "}
      <select
        value={theme}
        onChange={(event) => {
          const chosen = event.target.value;
          setTheme(chosen === "light" || chosen === "dark" ? chosen : "system");
        }}
        className="rounded border border-[var(--border)] bg-[var(--surface-raised)] px-1 py-0.5"
      >
        <option value="system">follow the system</option>
        <option value="light">light</option>
        <option value="dark">dark</option>
      </select>
    </label>
  );
}

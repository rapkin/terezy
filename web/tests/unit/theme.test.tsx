import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { applyTheme } from "@/components/shell/ThemeToggle";
import { RecordCard } from "@/components/record/RecordCard";
import { instrumentRead } from "../fixtures";

/**
 * FR-042: the theme is a display concern. It changes no value, no mark and no ordering, which
 * is asserted here by rendering the same card under both and comparing the text.
 */
function textUnder(theme: "light" | "dark"): string {
  applyTheme(theme, document.documentElement);
  const view = render(<RecordCard read={instrumentRead()} />);
  const text = view.container.textContent ?? "";
  const marks = [...view.container.querySelectorAll("[data-mark]")].map((held) =>
    held.getAttribute("data-mark"),
  );
  const fields = [...view.container.querySelectorAll("[data-field]")].map((held) =>
    held.getAttribute("data-field"),
  );
  view.unmount();
  return JSON.stringify({ text, marks, fields });
}

describe("the theme", () => {
  it("follows an explicit choice by stamping the document element", () => {
    applyTheme("dark", document.documentElement);
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    applyTheme("system", document.documentElement);
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });

  it("leaves every figure, mark and ordering identical across the two themes", () => {
    expect(textUnder("light")).toBe(textUnder("dark"));
  });
});

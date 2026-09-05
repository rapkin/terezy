import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { AsOfControl } from "@/components/shell/AsOfControl";

describe("AsOfControl", () => {
  it("displays the as_of the URL carries", () => {
    render(<AsOfControl asOf="2026-09-05" onChange={() => undefined} />);
    expect(document.querySelector("[data-as-of='2026-09-05']")).not.toBeNull();
  });

  it("hands the edited value up so the URL changes, and computes nothing itself", async () => {
    const changed = vi.fn();
    const user = userEvent.setup();
    render(<AsOfControl asOf="2026-09-05" onChange={changed} />);
    const field = screen.getByLabelText("as_of");
    await user.clear(field);
    await user.type(field, "2026-01-31");
    await user.click(screen.getByRole("button"));
    expect(changed).toHaveBeenCalledExactlyOnceWith("2026-01-31");
    expect(document.querySelector("[data-as-of='2026-09-05']")).not.toBeNull();
  });
});

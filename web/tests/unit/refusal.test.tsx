import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Refusal } from "@/components/figure/Refusal";

describe("Refusal", () => {
  it("renders the engine's reason verbatim", () => {
    const reason =
      "the category instruments declares no 'UA999'. This is a well-formed question about an id that does not exist, not a broken data root.";
    render(
      <Refusal
        refusal={{
          tag: "envelopes.CategoryHasNoSuchId",
          category: "instruments",
          wanted_id: "UA999",
          declared_ids: ["UA1", "UA2"],
          reason,
        }}
      />,
    );
    expect(screen.getByText(reason)).toBeInTheDocument();
  });

  it("renders the member's own fields beside the reason, so it says which thing refused", () => {
    render(
      <Refusal
        refusal={{
          tag: "envelopes.WindowOutsideCoverage",
          series_id: "ua_cpi_monthly",
          asked: ["1991-08", "2030-01"],
          covers: ["1991-08", "2025-10"],
          missing: ["2025-11", "2025-12"],
          reason: "the series declares no observation for 2 of the periods asked for.",
        }}
      />,
    );
    const text = document.body.textContent ?? "";
    expect(text).toContain("ua_cpi_monthly");
    expect(text).toContain("2025-11, 2025-12");
    expect(text).toContain("1991-08 .. 2025-10");
  });

  it("names its tag, so a refusal without a distinguishing reason is still identified", () => {
    render(
      <Refusal
        refusal={{
          tag: "middleware.NotOnLoopback",
          client_address: null,
          reason: "this service answers requests from loopback only.",
        }}
      />,
    );
    expect(document.querySelector("[data-refusal='middleware.NotOnLoopback']")).not.toBeNull();
    expect(document.body.textContent).toContain("not recorded");
  });
});

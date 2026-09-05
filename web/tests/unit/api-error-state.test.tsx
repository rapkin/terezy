import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ApiErrorState } from "@/components/shell/ApiErrorState";

/**
 * FR-006: a transport failure and a non-2xx response are each a named state, and neither
 * presents as an empty list, an empty chart or an unresolved loading state.
 */
describe("ApiErrorState", () => {
  it("names a transport failure", () => {
    render(<ApiErrorState answered={{ tag: "unreachable", detail: "connect ECONNREFUSED" }} what="the registry" />);
    expect(screen.getByRole("alert").textContent).toContain("connect ECONNREFUSED");
    expect(document.querySelector("[data-api-error='unreachable']")).not.toBeNull();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("names a non-2xx response and renders the API's own refusal in it", () => {
    render(
      <ApiErrorState
        answered={{
          tag: "body",
          status: 404,
          body: {
            tag: "service.PathNotServed",
            path: "/api/nope",
            reason: "this application serves no route at that path.",
          },
        }}
        what="a record"
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("status 404");
    expect(alert.textContent).toContain("serves no route at that path");
  });

  it("names an HTML answer to an API path rather than calling a healthy API unreachable", () => {
    render(
      <ApiErrorState
        answered={{ tag: "not-json", status: 200, contentType: "text/html" }}
        what="a record"
      />,
    );
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("text/html");
    expect(alert.textContent).not.toContain("unreachable");
  });
});

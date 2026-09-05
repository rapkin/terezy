import { describe, expect, it } from "vitest";
import { request, url } from "@/api/client";
import { registryQuery, observationsQuery } from "@/api/queries";
import { answersWith, answersWithText, ORIGIN, refusesToConnect } from "../msw/handlers";
import { server } from "../msw/server";
import { keyedSummary, registry } from "../fixtures";

describe("the request", () => {
  it("puts every parameter in the URL, so a screen states the date it was read at", () => {
    expect(url("/api/registry", { as_of: "2026-09-05" })).toBe("/api/registry?as_of=2026-09-05");
  });

  it("describes each read once, with the parameters that are in the URL", () => {
    expect(registryQuery("2026-09-05").queryKey).toEqual(["registry", "2026-09-05"]);
    expect(
      observationsQuery("cpi", "ua_cpi_monthly", "2026-09-05", { from: "1991-08", to: "2025-10" })
        .queryKey,
    ).toEqual(["observations", "cpi", "ua_cpi_monthly", "2026-09-05", "1991-08", "2025-10"]);
  });

  it("sends no scenario, because the response names the one it resolved under", () => {
    const asked = url("/api/instruments", { as_of: "2026-09-05" });
    expect(asked).not.toContain("scenario");
    expect(asked).not.toContain("display");
  });

  it("returns the body of a 200", async () => {
    server.use(answersWith("/api/registry", registry([keyedSummary()])));
    const answered = await request(`${ORIGIN}/api/registry`, { as_of: "2026-09-05" });
    expect(answered.tag).toBe("body");
    if (answered.tag !== "body") throw new Error("expected a body");
    expect(answered.status).toBe(200);
  });

  it("names a transport failure rather than returning an empty body (FR-006)", async () => {
    server.use(refusesToConnect("/api/registry"));
    const answered = await request(`${ORIGIN}/api/registry`, { as_of: "2026-09-05" });
    expect(answered.tag).toBe("unreachable");
  });

  it("names an HTML answer, so the SPA fallback is not read as a parse error (FR-006)", async () => {
    server.use(answersWithText("/api/nope", "<!doctype html><html></html>", "text/html"));
    const answered = await request(`${ORIGIN}/api/nope`, { as_of: "2026-09-05" });
    expect(answered.tag).toBe("not-json");
    if (answered.tag !== "not-json") throw new Error("expected a non-JSON answer");
    expect(answered.contentType).toContain("text/html");
  });

  it("names a body that says it is JSON and is not, rather than calling the API down", async () => {
    server.use(answersWithText("/api/registry", "{not json", "application/json"));
    const answered = await request(`${ORIGIN}/api/registry`, { as_of: "2026-09-05" });
    expect(answered.tag).toBe("not-json");
  });

  it("keeps a non-2xx JSON refusal as a body, so the refusal can be rendered", async () => {
    server.use(
      answersWith(
        "/api/instruments/UA999",
        {
          tag: "service.PathNotServed",
          path: "/api/instruments/UA999",
          reason: "this application serves no route at that path.",
        },
        404,
      ),
    );
    const answered = await request(`${ORIGIN}/api/instruments/UA999`, { as_of: "2026-09-05" });
    expect(answered.tag).toBe("body");
    if (answered.tag !== "body") throw new Error("expected a body");
    expect(answered.status).toBe(404);
  });
});

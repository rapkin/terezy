import { describe, expect, it } from "vitest";
import { today } from "@/clock";

describe("the one clock read", () => {
  it("produces a date in the shape the search parameter is validated against", () => {
    expect(today()).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

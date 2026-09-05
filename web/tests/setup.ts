import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./msw/server";

// jsdom implements no scrolling, and the router calls it on every navigation.
window.scrollTo = () => undefined;

beforeAll(() => {
  // FR-044's teeth at run time: a request no handler describes fails the test rather than
  // reaching a network the suite is not allowed to have.
  server.listen({ onUnhandledRequest: "error" });
});
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => {
  server.close();
});

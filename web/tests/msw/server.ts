import { setupServer } from "msw/node";
import { handlers } from "./handlers";

/** The in-process API every unit test talks to. Nothing here reaches a socket. */
export const server = setupServer(...handlers);

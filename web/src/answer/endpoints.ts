/**
 * The two category ids the answer screen names, and the only place in `web/src` that names them.
 *
 * A module of its own so that the exception 021 FR-015's scan needs — and the reason for it —
 * covers these two literals rather than every query the client makes
 * (`tools/category-scan-exceptions.txt`).
 */
export const QUESTIONS = "questions";

export const INSTRUMENTS = "instruments";

/**
 * The two category ids the answer screen names, and the only place in `web/src` that names them.
 *
 * 021 FR-015 forbids a category id in the client because the browser is generic over categories
 * — a branch on one there is a screen that stops working when `data/` grows. This screen is not
 * generic: it answers **the** declared question and reads **the** instrument behind each member,
 * which are two endpoints rather than two categories. Kept in a module of its own so the
 * exception (`tools/category-scan-exceptions.txt`) covers six lines instead of every query the
 * client makes.
 */
export const QUESTIONS = "questions";

export const INSTRUMENTS = "instruments";

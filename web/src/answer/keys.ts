/**
 * FR-009's join: a `non_dominated` key is matched to its outcome by **key equality**.
 *
 * Structural rather than by a serialisation, because a serialisation is an ordering of fields
 * and two encoders that order them differently would silently stop matching — which on this
 * screen is a card with no figures rather than an error.
 */
import type { Tuple } from "@/api/shapes";
import { isRecord } from "@/lib/narrow";

function equal(left: unknown, right: unknown): boolean {
  if (Array.isArray(left) || Array.isArray(right)) {
    if (!Array.isArray(left) || !Array.isArray(right) || left.length !== right.length) return false;
    return left.every((held: unknown, at) => equal(held, right[at]));
  }
  if (isRecord(left) && isRecord(right)) {
    const keys = Object.keys(left);
    if (keys.length !== Object.keys(right).length) return false;
    return keys.every((key) => Object.hasOwn(right, key) && equal(left[key], right[key]));
  }
  return left === right;
}

export function sameTuple(left: Tuple, right: Tuple): boolean {
  return equal(left, right);
}

/**
 * A list key, and nothing a reader sees.
 *
 * The **whole** record, because identity is all five terms and `candidates.py::_ordered` is a
 * cross product over ways in, ways out and plans: a key built from three of them gives two rows
 * one React key the day a second route lands at a venue, which is a data-only change, and React
 * then carries one row's open disclosure onto the other.
 */
export function listKey(key: Tuple): string {
  return JSON.stringify(key);
}

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
 * A key rendered as a React list key, and as nothing else.
 *
 * Not an identity: two keys that differ only in a field left out here would collide, which is
 * why `sameTuple` and not this is what the join compares on.
 */
export function keyLabel(key: Tuple): string {
  return [key.instrument_id, key.stream_id, key.route_in.destination_id].join(" · ");
}

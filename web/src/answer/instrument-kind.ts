/**
 * FR-006: an instrument's drawn kind comes from its own read, and from two fields rather than
 * one — only the read's **tag** is closed.
 *
 * FR-005 forbids inferring a kind from an id, a name or a path, which is why this takes a
 * response body and never a string.
 */
import type { InstrumentDeclared } from "@/api/shapes";
import { INSTRUMENT_KIND, classWord, declaredClass, type Kind } from "@/design/kinds";
import { isRecordRead, tagOf } from "@/lib/narrow";

export type KindReading =
  | { readonly tag: "read"; readonly kind: Kind; readonly declaredClass: string | null }
  | { readonly tag: "reading" }
  | { readonly tag: "not-read"; readonly why: string };

const DECLARED_TAGS: { readonly [Tag in InstrumentDeclared["tag"]]: true } = {
  "interface.InstrumentDeclaration": true,
  "fund.FundDeclaration": true,
  "cash.CashDeclaration": true,
};

function isDeclared(value: unknown): value is InstrumentDeclared {
  const tag = tagOf(value);
  return tag !== null && Object.hasOwn(DECLARED_TAGS, tag);
}

export function kindOf(body: unknown): KindReading {
  if (!isRecordRead(body)) {
    return { tag: "not-read", why: "the instruments read did not answer with a record" };
  }
  const result = body.result;
  if (!isDeclared(result)) {
    return { tag: "not-read", why: `the instruments read answered ${tagOf(result) ?? "no tag"}` };
  }
  return {
    tag: "read",
    kind: INSTRUMENT_KIND[result.tag],
    declaredClass: declaredClass(result),
  };
}

/** The class in this client's words where it has one, and raw where it does not (FR-006). */
export function classLabel(reading: KindReading): string | null {
  if (reading.tag !== "read" || reading.declaredClass === null) return null;
  return classWord(reading.declaredClass);
}

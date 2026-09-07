import type { ReactNode } from "react";
import type { Refusal as RefusalValue } from "@/api/shapes";
import type { Mark as MarkValue } from "@/lib/provenance";
import { assertNever } from "@/lib/exhaustive";
import { Marks } from "./Mark";
import { Refusal, RefusalChrome } from "./Refusal";

/**
 * FR-007: the three states any place a figure appears can be in.
 *
 * A rendering discriminant rather than a wire shape -- the API sends an amount with its
 * provenance, or a tagged refusal, and this is how one component decides between them.
 */
export type FigureState =
  | { readonly kind: "value"; readonly figure: ReactNode }
  | { readonly kind: "marked"; readonly figure: ReactNode; readonly marks: readonly MarkValue[] }
  | { readonly kind: "refused"; readonly refusal: RefusalValue }
  /**
   * A refusal the **answer** carries in a figure's place, rather than one of the envelope's.
   * `RefusalChrome` says why the two cannot be one union.
   */
  | {
      readonly kind: "refused-in-answer";
      readonly tag: string;
      readonly reason: string;
      readonly detail?: ReactNode;
    };

export function FigureSlot({ state }: { state: FigureState }) {
  switch (state.kind) {
    case "value":
      return <span data-figure="value">{state.figure}</span>;
    case "marked":
      return (
        <span data-figure="marked">
          {state.figure}
          <Marks marks={state.marks} />
        </span>
      );
    case "refused":
      return <Refusal refusal={state.refusal} />;
    case "refused-in-answer":
      return (
        <RefusalChrome tag={state.tag} reason={state.reason}>
          {state.detail}
        </RefusalChrome>
      );
  }
  assertNever(state);
}

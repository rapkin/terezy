/**
 * FR-010: a field the response does not carry is a named state saying **which** field.
 *
 * Never a blank, a zero, a dash or an empty slot (021 FR-008). The obligation it names is what
 * turns a gap into something a reader can ask the API for.
 */
export type FieldNotServed = {
  readonly tag: "field-not-served";
  readonly field: string;
  readonly obligation: string;
};

export function notServed(field: string, obligation: string): FieldNotServed {
  return { tag: "field-not-served", field, obligation };
}

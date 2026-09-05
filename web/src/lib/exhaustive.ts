/**
 * FR-004's mechanism: the arm a closed union's last case falls into.
 *
 * Reached only where a member exists that no case handles, which the typecheck has already
 * refused -- so the throw is for a body that arrived without the type it was generated from.
 */
export function assertNever(value: never): never {
  throw new Error(`unhandled member: ${JSON.stringify(value)}`);
}

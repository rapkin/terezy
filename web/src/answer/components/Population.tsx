import type { ReactNode } from "react";
import { count } from "@/design/format";
import { Disclosure } from "./Disclosure";

/**
 * FR-012: a population the API reported, its count, and the members that count counted.
 *
 * Every count is one interaction from its members, because a number with nothing behind it is a
 * claim a reader cannot check — and a population dropped because it was empty is the silent
 * exclusion 010 refuses, which is why zero renders too.
 */
export function Population<Member>({
  name,
  members,
  render,
}: {
  name: string;
  members: readonly Member[];
  render: (member: Member, at: number) => ReactNode;
}) {
  if (members.length === 0) {
    return (
      <p className="text-xs text-[var(--ink-muted)]" data-population={name} data-count="0">
        {name}: none
      </p>
    );
  }
  return (
    <div data-population={name} data-count={count(members.length)}>
      <Disclosure name={name} count={members.length} summary={name}>
        <ul className="ml-4 list-disc space-y-2" data-population-members={name}>
          {members.map((member, at) => (
            <li key={at}>{render(member, at)}</li>
          ))}
        </ul>
      </Disclosure>
    </div>
  );
}

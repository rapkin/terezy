import type { ReactNode } from "react";
import type { Group } from "@/answer/grouping";
import { count } from "@/design/format";
import { Disclosure } from "./Disclosure";

/**
 * FR-022 and FR-023: one line carrying the group's typed reason and its count, expandable to
 * each member's own fields and full reason.
 *
 * Never a count alone — a number with nothing behind it is the silent exclusion 010 refuses —
 * and never a blank.
 */
export function RefusalGroup<Member>({
  group,
  render,
}: {
  group: Group<Member>;
  render: (member: Member) => ReactNode;
}) {
  return (
    <div data-group={group.id}>
      <Disclosure
        name="refusal-group"
        count={group.members.length}
        summary={
          <span>
            {group.on.map((held) => `${held.field}: ${held.value}`).join(" · ")}
          </span>
        }
      >
        <p className="text-[var(--ink-muted)]" data-group-count>
          {count(group.members.length)} of them
        </p>
        <ul className="ml-4 list-disc space-y-2" data-group-members>
          {group.members.map((member, at) => (
            <li key={at}>{render(member)}</li>
          ))}
        </ul>
      </Disclosure>
    </div>
  );
}

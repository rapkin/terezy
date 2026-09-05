import type { ReactNode } from "react";

export function Table({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <caption className="pb-2 text-left text-sm text-[var(--ink-muted)]">{caption}</caption>
        {children}
      </table>
    </div>
  );
}

export function Th({ children }: { children: ReactNode }) {
  return (
    <th scope="col" className="border-b border-[var(--border)] px-2 py-1 text-left font-medium">
      {children}
    </th>
  );
}

export function Td({ children }: { children: ReactNode }) {
  return <td className="border-b border-[var(--border)] px-2 py-1 align-top">{children}</td>;
}

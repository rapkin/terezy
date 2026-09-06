import { cva, type VariantProps } from "class-variance-authority";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

const badge = cva("inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs", {
  variants: {
    tone: {
      neutral: "border-[var(--border)] text-[var(--ink-muted)]",
      warn: "border-[var(--warn-border)] bg-[var(--warn-surface)] text-[var(--warn-ink)]",
      refuse:
        "border-[var(--refuse-border)] bg-[var(--refuse-surface)] text-[var(--refuse-ink)]",
      // 026 FR-003: the fourth tone. An assumption is not a warning -- `warn` says a figure's
      // source is unverified or stale, and reusing it for "this is what the member rests on"
      // would put two different claims behind one colour.
      assume:
        "border-[var(--assume-border)] bg-[var(--assume-surface)] text-[var(--assume-ink)]",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export function Badge({
  tone,
  children,
  ...rest
}: VariantProps<typeof badge> & { children: ReactNode } & Record<`data-${string}`, string>) {
  return (
    <span className={cn(badge({ tone }))} {...rest}>
      {children}
    </span>
  );
}

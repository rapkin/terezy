import type { Answer, Subject } from "@/api/shapes";
import { remedyFor } from "@/answer/remedies";
import { day, money } from "@/design/format";
import { assertNever } from "@/lib/exhaustive";
import { marksOf } from "@/lib/provenance";
import { Badge } from "@/components/ui/badge";
import { FigureSlot } from "@/components/figure/FigureSlot";

/**
 * FR-011: the question as a template over typed fields, with **every** amount and the stream it
 * leaves.
 *
 * Measured 2026-09-06 there are two — 50 000 UAH from `salary_uah` and 1.00 USD from
 * `contract_usd` — and the second is the stream every one of the folded no-candidate refusals
 * names, so a header showing one amount hides the reason for the largest refusal group on the
 * screen. It states **no** standing: where the benchmark stands is a section-level fact
 * (FR-012), and one claim across three sections would be false in at least two of them.
 */
export function AnswerHeader({ answer }: { answer: Answer }) {
  const question = answer.question;
  const amounts = Object.entries(question.amounts);
  return (
    <section className="space-y-2" data-answer-header>
      <h2 className="text-base font-semibold">
        what to do with{" "}
        {amounts.map(([stream, amount], at) => (
          <span key={stream}>
            {at === 0 ? "" : " and "}
            <FigureSlot
              state={{
                kind: "marked",
                figure: money(amount),
                marks: marksOf(amount.provenance, answer.staleness),
              }}
            />{" "}
            <span className="text-sm font-normal text-[var(--ink-muted)]">from {stream}</span>
          </span>
        ))}
      </h2>
      <p className="text-xs text-[var(--ink-muted)]">
        asked {day(question.asked_on)}, answered as of {day(answer.as_of)}, over{" "}
        {question.horizons.map((horizon) => `${day(horizon.start)} – ${day(horizon.end)}`).join(", ")}.
        The benchmark is <span className="font-mono">{question.benchmark_instrument_id}</span>; the
        continuation assumption is {question.continuation}.
      </p>
      {answer.subjects.length === 0 ? (
        <p className="text-xs text-[var(--ink-muted)]" data-subjects="none">
          the question names no subject, so nothing was assessed.
        </p>
      ) : (
        <ul className="flex flex-wrap gap-2" data-subjects={String(answer.subjects.length)}>
          {answer.subjects.map((subject) => (
            <li key={subject.named}>
              <SubjectState subject={subject} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** FR-021: a subject the registry declares nothing by is a refusal carrying its remedy. */
function SubjectState({ subject }: { subject: Subject }) {
  switch (subject.tag) {
    case "answer.DeclaredSubject":
      return (
        <Badge tone="neutral" data-subject={subject.named}>
          {subject.named} — {subject.ids.length} declared
        </Badge>
      );
    case "answer.UndeclaredSubject": {
      const remedy = remedyFor(subject.named);
      return (
        <Badge tone="refuse" data-undeclared-subject={subject.named}>
          {subject.named}: nothing is declared, so it was not assessed. The remedy is{" "}
          {remedy.remedy}
          {remedy.suppliedBy === null ? (
            <span data-remedy-feature="unrecorded">
              , and which feature supplies it is not recorded here
            </span>
          ) : (
            <span data-remedy-feature={remedy.suppliedBy}>, supplied by {remedy.suppliedBy}</span>
          )}
        </Badge>
      );
    }
  }
  assertNever(subject);
}

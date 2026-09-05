/**
 * A value that is itself a long, multi-sentence citation is shown in full (*Edge Cases*).
 *
 * No clamp and no ellipsis: eliding a citation to a fixed length with no way to see the rest
 * removes exactly the part that makes it checkable.
 */
export function LongValue({ text }: { text: string }) {
  return <p className="break-words whitespace-pre-wrap">{text}</p>;
}

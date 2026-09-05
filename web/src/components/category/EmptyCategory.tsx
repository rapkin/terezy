/**
 * *Edge Cases*: a category with no records renders as a category with none.
 *
 * An empty list and an absent category must not look the same -- the absent one is a refusal
 * carrying the API's reason, and this is the other half of that distinction on screen.
 */
export function EmptyCategory({ category }: { category: string }) {
  return (
    <p data-records="0" className="text-sm">
      the category {category} is declared and holds no record
    </p>
  );
}

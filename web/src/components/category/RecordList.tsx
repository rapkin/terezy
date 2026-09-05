import { Link } from "@tanstack/react-router";
import type { Listing } from "@/api/shapes";
import { EmptyCategory } from "./EmptyCategory";

/** The records of one category, ordered as the API returned them (FR-002). */
export function RecordList({ listing }: { listing: Listing }) {
  if (listing.ids.length === 0) return <EmptyCategory category={listing.category} />;
  return (
    <ul data-records={String(listing.ids.length)} className="space-y-1">
      {listing.ids.map((id) => (
        <li key={id}>
          <Link
            to="/data/$category/$recordId"
            params={{ category: listing.category, recordId: id }}
            search={{ as_of: listing.as_of }}
            className="underline"
          >
            {id}
          </Link>
        </li>
      ))}
    </ul>
  );
}

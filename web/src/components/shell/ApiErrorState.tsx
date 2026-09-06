import { API_PREFIX, START_COMMAND, type Answered } from "@/api/client";
import { assertNever } from "@/lib/exhaustive";
import { isRecord } from "@/lib/narrow";
import { isRefusal } from "@/lib/provenance";
import { Refusal } from "@/components/figure/Refusal";

/**
 * FR-006: a transport failure and a non-2xx response are each a named state.
 *
 * Neither may present as an empty list, an empty chart or an unresolved loading state -- so an
 * answer that is not a body this route can read ends here rather than as an absence.
 */
export function ApiErrorState({ answered, what }: { answered: Answered; what: string }) {
  return (
    <div
      role="alert"
      data-api-error={answered.tag}
      className="space-y-2 rounded border border-[var(--refuse-border)] bg-[var(--refuse-surface)] p-3 text-[var(--refuse-ink)]"
    >
      <p className="font-semibold">{what} could not be read</p>
      <Detail answered={answered} />
    </div>
  );
}

function Detail({ answered }: { answered: Answered }) {
  switch (answered.tag) {
    case "unreachable":
      return (
        <p>
          the request never reached the API: {answered.detail}. Every request goes to{" "}
          {API_PREFIX} on the origin that served this page, so there is no host to check: the
          service is not answering. In development, start it with <code>{START_COMMAND}</code>.
        </p>
      );
    case "not-answered":
      return (
        <p>
          no route of the API produced this: status {answered.status} with content-type{" "}
          {answered.contentType ?? "none"}, and every outcome a route has is a tagged JSON body.
          So either the service is up and this request failed inside it, which its own log
          records, or nothing is listening at all — in development, start it with{" "}
          <code>{START_COMMAND}</code>.
        </p>
      );
    case "not-json":
      return (
        <p>
          the answer was status {answered.status} with content-type{" "}
          {answered.contentType ?? "none"}, which is not a body generated from the API's
          document — either something other than this service is answering {API_PREFIX}, or it
          said JSON and sent something else.
        </p>
      );
    case "body":
      return <BodyDetail status={answered.status} body={answered.body} />;
  }
  assertNever(answered);
}

function BodyDetail({ status, body }: { status: number; body: unknown }) {
  if (isRefusal(body)) {
    return (
      <>
        <p>the API answered status {status} with a refusal:</p>
        <Refusal refusal={body} />
      </>
    );
  }
  return (
    <>
      <p>the API answered status {status} with a body this route does not read:</p>
      <pre className="overflow-x-auto text-xs">
        {JSON.stringify(isRecord(body) || Array.isArray(body) ? body : { body }, null, 1)}
      </pre>
    </>
  );
}

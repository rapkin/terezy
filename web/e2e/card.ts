import { expect, type Page } from "@playwright/test";
import { AS_OF } from "./offline";

/**
 * One candidate's served projection, read in the browser rather than pinned in the test.
 *
 * `data/` moves, and a figure copied out of it would make this a test of the registry
 * (021 FR-047). What is asserted is the **relation**: the card's bars are the API's flows.
 */
export type ServedCard = {
  readonly key: string;
  readonly reaches: number;
  readonly bars: readonly { readonly id: string; readonly amount: number }[];
  readonly dates: readonly string[];
  readonly window: { readonly start: string; readonly end: string };
  readonly latencies: readonly number[];
};

/** Open the answer, then the first card any ranked row offers, and return what the API sent. */
export async function openFirstCard(page: Page): Promise<ServedCard> {
  await page.goto(`/?as_of=${AS_OF}`);
  await expect(page.locator("[data-answer]")).toBeVisible({ timeout: 120_000 });
  const link = page.locator("[data-open-card]").first();
  await expect(link).toBeVisible();
  const key = (await link.getAttribute("data-open-card")) ?? "";
  const served = await servedCard(page, key);
  await link.click();
  await expect(page.locator(`[data-card]`)).toBeVisible({ timeout: 120_000 });
  return served;
}

async function servedCard(page: Page, key: string): Promise<ServedCard> {
  return await page.evaluate(
    async ([asOf, candidateKey]: readonly string[]) => {
      const declared: { ids: string[] } = await (
        await fetch(`/api/questions?as_of=${String(asOf)}`)
      ).json();
      const [questionId] = declared.ids;
      const body: {
        result: {
          projection: {
            projection_key: string;
            flows: {
          sequence: number;
          occurred_on: string;
          kind: string;
          gross: { amount: number };
        }[];
            purchase: { purchased_on: string; paid: { amount: number } };
            way_in: { latency_days: number; one_way: { arrived: { amount: number } } };
            releases: {
              released_on: string;
              arrived_on: string;
              way_out: { latency_days: number };
            }[];
            remainder_way_out: { tag: string; latency_days?: number };
          };
        };
      } = await (
        await fetch(
          `/api/questions/${String(questionId)}/candidates/${encodeURIComponent(
            String(candidateKey),
          )}?as_of=${String(asOf)}`,
        )
      ).json();
      const answer: {
        result: {
          answer: {
            sections: {
              horizon: { start: string; end: string };
              outcome: {
                comparison: {
                  ranked?: {
                    projection_key: string;
                    reaches: { amount: number };
                    undeployed: { journey: { tag: string; arrived_on?: string } } | null;
                  }[];
                };
              };
            }[];
          };
        };
      } = await (
        await fetch(`/api/questions/${String(questionId)}/answer?as_of=${String(asOf)}`)
      ).json();
      const sections = answer.result.answer.sections;
      const section = sections.find((held) =>
        (held.outcome.comparison.ranked ?? []).some(
          (one) => one.projection_key === String(candidateKey),
        ),
      );
      const outcome = (section?.outcome.comparison.ranked ?? []).find(
        (one) => one.projection_key === String(candidateKey),
      );
      const projection = body.result.projection;
      return {
        key: projection.projection_key,
        reaches: outcome?.reaches.amount ?? 0,
        bars: [
          { id: "arrived", amount: projection.way_in.one_way.arrived.amount },
          { id: "purchase", amount: projection.purchase.paid.amount },
          // Keyed by the **ledger sequence**, which is what `bars.ts` builds the id from. Keyed
          // by the array index instead, every released bar missed its match and the loop that
          // compares them skipped all of them — green whatever amount the card drew.
          ...projection.flows
            .filter((flow) => flow.kind !== "purchase")
            .map((flow) => ({
              id: `released:${String(flow.sequence)}`,
              amount: flow.gross.amount,
            })),
        ],
        dates: [
          projection.purchase.purchased_on,
          ...projection.flows.map((flow) => flow.occurred_on),
          ...projection.releases.map((release) => release.arrived_on),
          ...(outcome?.undeployed?.journey.arrived_on === undefined
            ? []
            : [outcome.undeployed.journey.arrived_on]),
        ],
        window: section?.horizon ?? { start: "", end: "" },
        // The remainder's own leg is one more declared wait, on its own dates: it leaves on the
        // purchase date with no position behind it, so it is on none of the releases above.
        latencies: [
          projection.way_in.latency_days,
          ...projection.releases.map((release) => release.way_out.latency_days),
          ...(outcome?.undeployed?.journey.tag === "tuple.RemainderCameHome" &&
          projection.remainder_way_out.latency_days !== undefined
            ? [projection.remainder_way_out.latency_days]
            : []),
        ],
      };
    },
    [AS_OF, key] as const,
  );
}

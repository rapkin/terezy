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

export async function servedCard(page: Page, key: string): Promise<ServedCard> {
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
            flows: { occurred_on: string; kind: string; gross: { amount: number } }[];
            purchase: { purchased_on: string; paid: { amount: number } };
            way_in: { latency_days: number; one_way: { arrived: { amount: number } } };
            releases: {
              released_on: string;
              arrived_on: string;
              way_out: { latency_days: number };
            }[];
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
                  ranked?: { projection_key: string; reaches: { amount: number } }[];
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
          ...projection.flows
            .filter((flow) => flow.kind !== "purchase")
            .map((flow, at) => ({ id: `released:${String(at)}`, amount: flow.gross.amount })),
        ],
        dates: [
          projection.purchase.purchased_on,
          ...projection.flows.map((flow) => flow.occurred_on),
          ...projection.releases.map((release) => release.arrived_on),
        ],
        window: section?.horizon ?? { start: "", end: "" },
        latencies: [
          projection.way_in.latency_days,
          ...projection.releases.map((release) => release.way_out.latency_days),
        ],
      };
    },
    [AS_OF, key] as const,
  );
}

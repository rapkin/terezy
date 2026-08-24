# Feature Specification: The ФОП group 3 regime

**Feature Directory**: `specs/012-fop-group-3`

**Feature Branch**: `spec/011-012-rev` (spec-writing worktree; squash-lands per `specs/README.md`)

**Created**: 2026-08-23

**Status**: Ready for planning — clarifications resolved 2026-08-23, source attributions
corrected against the primary texts 2026-08-24, and the quotations restored to their full
provisions against the consolidated Податковий кодекс 2026-08-25, which is when the levy's
**sunset** (FR-008a) and a **third amending law**, № 4835-IX від 07.04.2026, entered this
specification. **Six owner verification tasks** remain, each naming the value that closes
it; tasks 5 and 6 change what the engine does and say so, and tasks 1 and 4 shrank to a
reading when their texts were found. **Four crediting destinations are UNSETTLED** in
feature 009's sense — an international payment system, a personal non-ФОП account, a
crypto exchange and a bank account outside Ukraine — and each is modelled as a labelled
scenario switch rather than carried as a marker. Verdicts have moved as the criteria below
were written down and applied to them; the **register beside the destination table** is the
one place that history is kept.

**Legal grounding**: the verdict levels used below — **SETTLED**, **INTERPRETED**,
**UNSETTLED** — are feature 009's, defined in `specs/009-tax-depth/spec.md` under "Legal
grounding" and used here with the same meaning, including the індивідуальна податкова
консультація (ст. 52 ПКУ) as an UNSETTLED question's real resolution path.

**Three lines decide what a question gets, and they are stated here once and nowhere
else** — two that fix the verdict and one that fixes what the verdict contains. They are
stated here because this specification reaches five named destinations plus a residual and
the reader is entitled to know what separated them. They are written as mechanical tests
rather than judgements, so that applying them can overturn an answer already written — and
applying them has repeatedly done exactly that — the register beside the table below says
when and to what.

**Line 1 — INTERPRETED, or below it.** *Does the source attach its proposition to a
**numbered document a reader can go and check** — a statutory provision, an ІПК, a ЗІР
answer, or a letter with a number?* If it does, the reading can be **INTERPRETED**: the
inference is checkable at its source. If it rests on an administrative position with no
number attached to it, it cannot, because there is nothing to go and check, and agreement
between practitioners restating it is not a substitute — exactly as 011's FR-011 says of a
paraphrase. FR-025's own-account guidance cites п. 292.5, п. 292.6 and п. 291.4 and
passes. The ДПС position on a payment-system account is reported as living in
*«роз'ясненнях та індивідуальних податкових консультаціях (ІПК)»* with **no number given
for any of them**, and fails.

  **A number is necessary and not sufficient. It carries INTERPRETED only where the numbered
  document speaks beyond its own addressee, and only where no other numbered administrative
  position points the other way without revoking it.** Two grounds, and the first is the
  stronger:

  - **An ІПК binds nobody but the taxpayer who asked for it.** Its own closing paragraph
    says so — *«індивідуальна податкова консультація має індивідуальний характер і може
    використовуватися виключно платником податків, якому надано таку консультацію»* (п. 52.2
    ст. 52 ПКУ, quoted from ІПК № 100/ІПК/99-00-04-03-03-06, retrieved 2026-08-27). So an ІПК
    addressed to someone else is **evidence of the authority's position** and not an answer
    binding this owner. It makes a reading computable and citable; it cannot make it the tax
    owed. ⚙ **This is an inference and it is marked as one**: generalising from individual
    consultations to *«ДПС's position»* is a step the practitioner sources take silently and
    this specification took from them for a day. It is also exactly why owner verification
    task 6's remedy is an ІПК **of the owner's own** — nothing else would bind him.
  - **Numbered on both sides is not settled either.** Where two numbered administrative
    positions point different ways and neither revokes the other, there is no authoritative
    answer, which is 009's definition of UNSETTLED.

  ⚙ A numbered *administrative* document counts at all, which is what makes task 6 closeable
  — an ІПК is not a statutory provision, and under a statute-only reading of this line
  nothing the owner could obtain would ever close it. ⚙ Neither ground touches FR-025, whose
  guidance rests on **statutory provisions** rather than on consultations, which is why that
  row is the only INTERPRETED one.

  ⚙ **No row is decided by the second ground alone.** At FR-026d, the only row where two
  numbered positions meet, the first ground already refuses INTERPRETED because both
  documents answer one taxpayer. The second ground is reachable in principle by a document
  that speaks beyond its addressee — a ЗІР answer, a узагальнююча податкова консультація —
  and no such document is cited in this feature as of 2026-08-27. It stays for the same
  reason the unexercised clauses of **candidate** stay: a rule that is right and currently
  unused is not a rule that cannot fire.

**Line 2 — UNSETTLED, or refused.** 009 has no *refuse* level: everything with no
authoritative answer is UNSETTLED and gets a labelled scenario switch. FR-027's refusal is
this specification's own addition, and it fires in one case only, on one test: *does
anything attach a treatment to this destination?* Where something does, the destination is
**UNSETTLED** and gets a switch. Where **nothing at all** reaches the destination, every
figure on that switch would be a guess wearing a label — FR-026's *"each figure MUST carry
that reading's own citations"* would be unsatisfiable — and the honest output is a refusal
naming the destination.

⚙ **Line 2 is not the only thing that reaches FR-027, and the sentence above says it is.**
FR-027 names three states and Line 2 sees one of them; the other two are a destination the
table has no row for, and a destination where Line 3 leaves no computable candidate — the
case stated three paragraphs below. Read *fires in one case only* as scoped to Line 2's own
test; FR-027 is the requirement and it governs. Recorded 2026-08-27; closed by rewriting the
sentence to *Line 2 produces one of FR-027's three states* next time this section is edited.

The test is deliberately weaker than *a source must name the candidate readings*: a source
saying *money withdrawn to a personal card is taxed as personal income* attaches a treatment
to that destination and passes, whether or not it names the reading a switch ends up
computing.

**Line 3 — what a switch contains.** Line 3 decides no verdict; it decides the contents of
a switch Line 2 has already called for:

> **Every candidate treatment that is a declared scheme gets a computed, labelled figure.
> Every candidate that is not gets named on the switch as uncomputed, with the reason it
> cannot be computed.**

A treatment needing a rate nobody declared — another jurisdiction's regime, the загальна
система, the 15% penalty rate — is not computable here and MUST NOT be computed; it is
also not thereby invisible, because an omitted reading is how a switch comes to look
complete when it is not. There is no fixed number of figures: a switch holds one per
computable reading, and the count is an output of this rule rather than an input to it.

**Where no candidate is computable there is no switch.** A switch of zero figures is not a
switch; the destination refuses under FR-027, and the uncomputable candidates are named in
the refusal instead of on a switch that holds nothing. ⚙ Stated because Line 3 otherwise
implies a switch exists wherever Line 2 passed, and an empty one would be a refusal
wearing a switch's clothes.

**Candidate**, since Line 3 is a MUST-shaped rule and the word carries it:

> A treatment is a **candidate** at a destination when it is **proposed** for that
> destination — by a source that reaches the destination, or by an inference this
> specification states on the record — **and no source that reaches the destination
excludes
> it**. Exclusion beats proposal: where a source on the destination says a treatment does
not
> apply there, it is not a candidate however plausible it looks and however well its rates
> are declared.

*Exclusion* is what makes the personal-card row come out as it does: the ФОП scheme is
**not** a candidate there although it is the best-declared scheme in the feature, because
yankiv says *«Категорично ні»* about that destination. A definition admitting every
declared scheme would lose that row.

⚙ **Which clauses of the definition no current row exercises, said plainly**, because an
  unexercised clause is how the previous version of this rule went unnoticed for a round.
  No row today has a candidate that is **not** a declared scheme, so Line 3's second
  sentence — name it uncomputed — is reachable but unillustrated; the one candidate that
  used to illustrate it, the загальна система at a crypto exchange, was withdrawn on
  2026-08-27 when that row's verdict moved again (register). Nor does any row rest on the
  *inference this specification states* half of **proposal**: every reading now computed
  is proposed by a source that reaches its destination. Both clauses stay, because a rule
  that is right and currently unused is not the same defect as a rule that cannot fire —
  but nothing here should be read as evidence that they have been tested.

⚙ **One judgement survives the definition, and the table is where it is recorded.**
  Deciding whether a source's proposition *reaches* a destination is not mechanical — it
  is the same judgement Line 2 makes, and it is the whole of what separates the
  personal-card row from the crypto-exchange row. **The table below is therefore
  normative, not illustrative.** It records that judgement once per destination, with the
  source that supports it. A destination not in the table cannot be resolved by applying
  these lines to it: the honest move is to add a row with its reasoning, and until someone
  does, the destination refuses under FR-027 — which is a different refusal from the
  no-source one, and FR-027 says so.

⚙ **This was a verdict test until 2026-08-26 and it could not fail.** Its headline
  demanded that *every* candidate be a declared scheme; its body then defined the
  candidate set as the declared schemes and excluded anything else from being a candidate
  at all. So the failure clause could never obtain, crypto's own third reading
  contradicted the headline, and a success criterion asked for a refusal nothing in the
  specification could produce. The rule above is what the test was reaching for, cast as
  what it actually governs.

⚙ **Line 3 is a test on the data, Line 1 on the sources, and neither is the other.**
  Source quality attaches to the **confidence** of a figure — whether it may ever be
  labelled the tax owed — never to whether a figure may be computed. ⚙ 009's UNSETTLED
  carries **no** general requirement of a pair of source-backed competing readings: the
  definition in its "Legal grounding" states none, and its FR-024 keeps four disposal
  methods computable of which two are not source-backed. The switch 009 actually *builds*
  is a pair of source-backed readings, so it is a weaker precedent than "009 does this
  routinely" would suggest — the ground here is that nothing in 009 **requires** a pair,
  not that 009 has already dispensed with one.

**Applied, once, to every destination this specification reaches:**

| Crediting destination | Line 1 | Line 2 | Verdict | Line 3 — what the switch holds |
|---|---|---|---|---|
| The ФОП's own foreign-currency account at a bank in Ukraine | passes — п. 292.5, п. 292.6, п. 291.4 | — | **INTERPRETED**, FR-025 | no switch: one charge |
| A crypto-exchange account | fails — the destination proposition carries no number | passes — 7eminar's **question is this destination** | **UNSETTLED**, FR-026c | computed: personal income — one. The ФОП scheme is excluded, not contested |
| An international payment system (Payoneer) | fails — ІПК referred to, none numbered | passes — yankiv is on this destination | **UNSETTLED**, FR-026a | computed: the ДПС reading, the НБУ reading, the non-repatriation reading — three |
| A personal, non-ФОП account or card | fails — no numbered document | passes — yankiv attaches a treatment to it, and alone | **UNSETTLED**, FR-026b | computed: personal income — one. The ФОП scheme is excluded, not contested |
| A bank account outside Ukraine | numbered, but stopped by both of Line 1's qualifications — ІПК № 100/ІПК against лист № 5064/Г, each answering one taxpayer and pointing the other way | passes — two ДПС documents retrieved, plus two practitioner articles | **UNSETTLED**, FR-026d | computed: personal income, the ФОП scheme at the credit date — two, the only pair here resting on documents this spec has read rather than seen reported |
| Anything else | — | **fails** | **Refused**, FR-027 | — |

**And the register of how each verdict got there.** This is the **only** place the history
of a verdict is written; every other mention of a destination points here rather than
narrating. ⚙ Five rounds of review found stale verdict history in five different places
each time, because a verdict that moved needed five edits. It needs one row now.

⚙ **What a move actually costs, so the claim above is not read as more than it is.** The
register is the only place a verdict's *history* is tabulated, and that much is true. A
verdict that moves still changes: the Status header's count and its list of UNSETTLED
destinations, the table row above, the row here, the Edge Cases bullet, the
FR-026a…FR-026d requirement, SC-017's per-destination counts, the "Clarifications resolved"
row, and both the preamble and the item of owner verification task 6 — nine sites as of
2026-08-27, not three. Closing this means the table becomes the only place a verdict or a
count is written and every other site points at it; nothing on this branch has done that.

| Destination | Verdict history | Why it moved |
|---|---|---|
| ФОП's own FX account | INTERPRETED throughout | narrowed 08-26 to *at a bank in Ukraine*: a marked narrowing, not an inference from the source's silence |
| Crypto exchange | UNSETTLED (2) → **08-27** Refused → **08-27** UNSETTLED (1) | the two propositions read as reaching it do not (FR-027); then 7eminar was found, which does |
| Payment system | Refused → **08-25** UNSETTLED (2) → **08-26** UNSETTLED (3) | Line 2 applied honestly; then «Стратегія 2» recognised as a computable reading, not background |
| Personal account or card | (unnamed, residual) → **08-26** UNSETTLED (1) | the best-attached destination in the table was sitting in FR-027's residual row |
| Bank account outside Ukraine | (inside FR-026a) → **08-25** Refused → **08-27** UNSETTLED (2) | split from the payment system on scope; then its own ДПС documents were retrieved |
| Anything else | Refused throughout | — |

⚙ Two of those moves were the same mistake: *nothing reaches this destination* concluded
from re-reading the sources already cited rather than from looking for one. Both were
reversed by a search that took minutes.

> **These verdicts are the least settled thing in this feature, and they are expected to
> move.** They rest on **administrative positions rather than statute** — practitioner
> reports of ДПС consultations, and consultations that bind only the taxpayer who asked for
> them (п. 52.2 ст. 52 ПКУ). Three of them moved during specification, each time because a
> better source turned up rather than because the reasoning changed, which is the shape of a
> question that does not close by searching. **What closes one is an індивідуальна податкова
> консультація of the owner's own** — task 6 — and that is his action, not a research task.
>
> ⚙ **The count above is looser than the register.** Four destinations moved between
> 2026-08-25 and 08-27, and the register's *Why it moved* column attributes only two of those
> moves to a source that turned up — 7eminar at the crypto exchange, the two ДПС documents at
> the foreign bank account. The rest moved because a criterion was applied to a row already
> written. Recorded 2026-08-27 rather than rewritten, because what the sentence is claiming —
> that this question does not close by searching — survives the correction; the same sentence
> is mirrored in `specs/features.toml`'s `crediting-destination-verdicts` entry and must move
> with it.
>
> Moving one is deliberately cheap, and the machinery for that is the point of everything
> above. A verdict is **declared data** behind the normative table, not a branch in the
> engine: no component name is hard-coded (FR-001), the switch is general (FR-026), and every
> reading computes from declared, cited rates. So a verdict change is **a row in the table, a
> row in this register, and a line in task 6** — never a redesign, and never a source-code
> change. A planner should build for the verdicts moving rather than for these particular
> ones being right.

⚙ **The first row and the bank-account-outside-Ukraine row are made exclusive by a
  narrowing this specification owns, and marks.** Neither cited source states where the
  bank is: factor.academy's **own-account article** says *«валютний рахунок ФОП»* and
  nothing more, and reading "Ukrainian" into that silence is the unmarked inference deleted
  from this specification on 2026-08-25. (Two factor.academy articles are cited; the other
  is FR-026d's, on exactly the foreign-account case.) The rows are separated instead by
  confining the **INTERPRETED verdict** to the case the guidance is known to reach. That is
  a narrowing, not an inference: it makes the confident claim smaller rather than larger,
  and everything the guidance may or may not cover falls to FR-026d, where the answer is a
  switch rather than a charge.

**Input**: The taxation scheme the owner's contract income actually lands in. Contract
income arrives through Deel and is directed to a **ФОП account in USD**; Ukrainian
currency restrictions mean the dollars must be sold for hryvnia to be spent; and the tax
is assessed at the official rate on the **credit** date, not the sale date. Model the
scheme — a declared set of components, of which єдиний податок and військовий збір are two
charged as rates on dated schedules and ЄСВ is a third this scheme charges nothing for —
and retire `IncomeStream.income_tax_rate`.

---

## Why this feature exists

The owner's largest single cash flow is his contract income, and the system currently
models its tax with a `float | None` on the income stream.

That scalar was honest for what feature 002 needed. `core/streams/streams.py` argues its
one genuinely load-bearing decision carefully — an omitted rate means *the owner has not
stated one*, which is not zero, so `deployable` returns `IncomeTaxRateUndeclared` with no
net field for a caller to mistake for a figure. That reasoning is correct and this feature
keeps it. What it cannot survive is the actual shape of the regime the money lands in:

- **Two components with different commencement dates.** A scalar is one number. The regime
  charges єдиний податок and військовий збір, and the levy commenced on a date a second
  law set, a month after the date its own law named.
- **A fixed-amount obligation that is not a percentage of anything.** ЄСВ is a statutory
  monthly sum, triggered by a month elapsing rather than by income arriving.
- **A choice between whole schemes.** Which scheme applies — ФОП group 3, ФОП group 2, a
  legal entity — decides the entire set of components charged, not one rate inside it. A
  scalar on the stream cannot name a scheme, and the system has to be able to apply a
  different one.
- **A base in a different currency from the amount.** The base is the credited dollars at
  the official rate on the credit date; the hryvnia actually received comes from a market
  rate on a different date. One number cannot be both.

Feature 006 already solved the general form of the first problem: it gave **instruments**
tax classes with dated rate schedules, and made adding a legislated change one entry in a
data file. It left the income stream behind with its scalar. **This feature closes that
inconsistency**: a stream names a tax treatment, exactly as an instrument does, and the
rates live in curated, cited tax data rather than as a bare number in per-owner data.

That relocation is worth stating on its own, because it repairs a boundary rather than
just moving a field. `data/README.md` exempts per-owner streams from the citation
requirement with a good argument: *an owner's own salary is not an observation needing a
citation but a statement of fact by the only person who can make it.* The argument holds
for an amount and a cadence. It never held for a **tax rate**, which is a public legal
fact about the Republic and not a statement about the owner — and the current schema lets
one be written into per-owner data uncited. After this feature, the owner declares *which
regime he is in* (a fact about him, uncited, correctly) and the regime's rates live in
`data/tax/` with their sources (public facts, cited, correctly). Principle VII's boundary
comes out sharper than it went in.

### One rate, three laws, and an end nobody can put a date on

The clearest justification in this repository for why rates had to become dated schedules
with provenance is sitting in the owner's own tax position, and three statutes have moved
it so far.

**Закон України № 4015-IX від 10.10.2024** rewrote підпункти 1.1–1.3 of пункт 16-1
підрозділу 10 розділу XX ПКУ. It made ФОП of the third group payers of the військовий збір
at 1% — *«для платників, зазначених у підпункті 3 підпункту 1.1 цього пункту, - 1 відсоток
від доходу, визначеного згідно із статтею 292 цього Кодексу»* — and set **both ends of the
charging window in a single sentence**, абзац п'ятий підпункту 1.1, quoted here in full
because the second half of it is the fact this specification lost until 2026-08-25:

> Військовий збір для платників збору, зазначених у підпунктах 2 та 3 цього підпункту,
> встановлюється **з 1 жовтня 2024 року** **по 31 грудня року, у якому буде припинено або
> скасовано воєнний стан**, введений Указом Президента України "Про введення воєнного
стану
> в Україні" від 24 лютого 2022 року № 64/2022, затвердженим Законом України "Про
> затвердження Указу Президента України "Про введення воєнного стану в Україні" від 24
> лютого 2022 року № 2102-IX".

The **same law** set the levy on ordinary personal income at 5% — *«для платників,
зазначених у підпункті 1 підпункту 1.1 цього пункту, - 5 відсотків від об'єкта
оподаткування, визначеного підпунктом 1 підпункту 1.2 цього пункту»* — which applies from
that law's own набрання чинності, **1 грудня 2024**.

Then **Закон України № 4113-IX від 04.12.2024** moved the *start* before anything was ever
charged under it. Its розділ I, пункт 6 — *«У розділі XX …»* — підпункт 2 reads *«у пункті
16-1: … у підпункті 1.1 … в абзаці п'ятому слова і цифри "з 1 жовтня 2024 року" замінити
словами і цифрами "з 1 січня 2025 року"»*, and its commencement clause singles that
підпункт out: *«Цей Закон набирає чинності з першого числа місяця, наступного за місяцем
його опублікування, крім підпункту 2 пункту 6 розділу I цього Закону, який набирає
чинності з дня, наступного за днем опублікування цього Закону»*. So the ФОП levy commenced
on **1 січня 2025** and never on the date its own law named.

Then **Закон України № 4835-IX від 07.04.2026** moved the *end*. Its розділ I reads, in
full for the two items that bear on this scheme:

> 1. В абзаці п'ятому підпункту 1.1 слова і цифри "по 31 грудня року, у якому" замінити
> словами і цифрами "по 31 грудня третього календарного року, наступного за роком, у
якому".
>
> 2. В абзаці шостому підпункту 1.3 слова "за роком, у якому" замінити словами "за третім
> календарним роком після року, у якому".

and it commences *«з дня, наступного за днем його опублікування»* (Голос України,
14.04.2026). Read at `4835-IX/print` on 2026-08-25.

The consolidated Code, read at `2755-17/print` the same day and marked *станом на
24.08.2026*, therefore now carries абзац п'ятий підпункту 1.1 as: *«… встановлюється з 1
січня 2025 року по 31 грудня третього календарного року, наступного за роком, у якому буде
припинено або скасовано воєнний стан …»* — and the amendment history block underneath it
names both amending laws, quoted here entire so that nothing rests on where an ellipsis
fell: *«{Абзац п'ятий підпункту 1.1 пункту 16-1 підрозділу 10 розділу ХХ із змінами,
внесеними згідно із Законом № 4113-IX від 04.12.2024 - щодо застосування див. абзац другий
пункту 1 розділу II, і з змінами, внесеними згідно із Законом № 4835-IX від 07.04.2026}»*
— the page's own wording, *«із змінами»* the first time and *«, і з змінами»* the second.

⚙ **The marker's own cross-reference, followed.** *«щодо застосування див. абзац другий
  пункту 1 розділу II»* points at 4113-IX's own transitional clause, which reads: *«Зміни
  до пунктів 16-1 і 25 підрозділу 10 розділу XX "Перехідні положення" Податкового кодексу
  України застосовуються з дня набрання чинності Законом України … від 10 жовтня 2024 року
  № 4015-IX.»* So 4113-IX's substitution applies **from 4015-IX's own commencement, 1
  December 2024** — retroactively, since the підпункт carrying it took effect only on **26
  December 2024** under the carve-out quoted above (4113-IX was published in Голос України
  on 25.12.2024; the Law as a whole commenced on 1 January 2025, and it is the підпункт,
  not the Law, that came earlier). The practical consequence is stronger than the date
  alone: *«з 1 жовтня 2024 року»* was **never operative for any period** — not October,
  not November, and not the 1–25 December window the substitution's own commencement would
  otherwise have left open — for any of the payers абзац п'ятий names. Those are
  *«платники, зазначені у підпунктах 2 та 3»*, and read as **підпункти** rather than as
  ФОП groups they are all four groups: підпункт 2 is *«фізичні особи - підприємці -
  платники єдиного податку першої, другої та четвертої груп»* and підпункт 3 is group
  three. So the schedule's earliest entry of 1 January 2025 is not merely current but the
  only start date that ever applied, and it applied to every ФОП group at once. ⚙ Read on
  2026-08-26 because an unfollowed reference inside a quotation is the shape three earlier
  rounds' defects took.

**The window has an end, and it is not a date.** That termination is a legal fact of
exactly the same standing as the 1 January 2025 commencement, and this specification
recorded the commencement and dropped the termination — a quotation cut mid-provision,
closed with a guillemet, and reading as if the sentence ended there. **FR-008a is where it
lives now**, and what a declaration must do with it is that requirement's business, not
this section's.

⚙ **What ends, and for whom.** The ФОП levy has **no reversion rate**: for платники of
  підпункти 2 and 3 the charge stops at the end of the window and nothing replaces it. The
  1,5% that абзац шостий підпункту 1.3 restores is a different charge on a different payer
  — *«ставка збору для платників, зазначених у підпункті 1 підпункту 1.1 цього пункту,
  становить 1,5 відсотка …»*, i.e. the ordinary-personal-income levy that 4015-IX had
  raised to 5%. Both hang off the same event and 4835-IX moved both by the same three
  years; they are not the same schedule, and conflating them would put a 1,5% floor under
  a charge that simply ceases.

⚙ **Both ends are conditioned on an event, not on a date**, and this repository already
  knows that is unmodelled: `specs/features.toml` carries the `[[future]]` entry
  `martial-law-ends-one-belief-two-places`, which records that the same event is already a
  declared belief in `data/scenarios/war_end.toml` and that a schedule keyed by a scenario
  is no longer a pure fold over dates. That entry is where the modelling question lives;
  this specification states the fact and points at it rather than restating it.

⚙ That is also why the citation and the value have to travel together. A system holding
  *1% from 1 January 2025* under a citation to 4015-IX holds a rate whose own cited source
  contradicts its date, and nothing downstream can detect it — which is exactly what this
  specification did until 2026-08-24. The rate is 4015-IX's, the start date is 4113-IX's,
  the end is 4835-IX's, and a dated schedule entry carries a provenance per entry rather
  than one per rate.

A system carrying a scalar per stream cannot express any of this. A system carrying dated
schedules (feature 006's E10) expresses the rate, its commencement and the amendment that
moved it as data entries with their own citations, and would have taken the amendment as
one more entry rather than as a code change. This feature is where that machinery meets
the money.

⚙ The two facts do not enter on equal footing. The ФОП levy is this scheme's own rate. The
  1,5% → 5% personal-income change is cited here as the *argument* for dated schedules,
  and enters as a value only where a declaration names it — the levy component of the
  personal-income reading (FR-010), beside its ПДФО (FR-010a). No income stream is charged
  at either.

## The verified legal facts

Every value below is entered as data with the citation shown and an **empty**
`verified_on`, in the repository's standing sense: retrieved and cited is not verified,
and the mark propagates to every figure derived from it (`SIMULATOR_SPEC.md` §11 item 2,
constitution Principle I). Nothing here originates from an implementer's or an agent's
memory.

| Fact | Value | Source | State |
|---|---|---|---|
| Єдиний податок, ФОП group 3, not a VAT payer | **5% of income** | Підпункт 2 пункту 293.3 статті 293 ПКУ — *«5 відсотків доходу - у разі включення податку на додану вартість до складу єдиного податку»*; that wording set by Закон № 909-VIII від 24.12.2015, розділ I пункт 81 підпункт 1. Read in the consolidated Code at `2755-17/print`. zaxid.net's *«єдиний податок в сумі 5% від доходу»* agrees and is no longer what the value rests on | Primary text read 2026-08-25, unverified. № 909-VIII commences *«з дня набрання чинності Законом України "Про Державний бюджет України на 2016 рік", але не раніше 1 січня 2016 року»*, so the exact effective date needs that budget law read — owner verification task 1, no longer load-bearing |
| Військовий збір, ФОП group 3 | **1% of income**, **from 1 January 2025**, **until 31 December of the third calendar year after the year martial law ends** | Rate: Закон України № 4015-IX від 10.10.2024, підпункт 3 підпункту 1.3 — *«для платників, зазначених у підпункті 3 підпункту 1.1 цього пункту, - 1 відсоток від доходу, визначеного згідно із статтею 292 цього Кодексу»*. Start date: Закон України № 4113-IX від 04.12.2024, підпункт 2 пункту 6 розділу I — *«в абзаці п'ятому слова і цифри "з 1 жовтня 2024 року" замінити словами і цифрами "з 1 січня 2025 року"»*. End: Закон України № 4835-IX від 07.04.2026, пункт 1 розділу I, over 4015-IX's own wording — both quoted in "One rate, three laws, and an end nobody can put a date on" and required by FR-008a. Consolidated ПКУ `2755-17/print`, станом на 24.08.2026, carries all three | Primary texts read 2026-08-24, № 4835-IX and the consolidated Code 2026-08-25; unverified. **4015-IX may not be cited for either date**: its own text says *«з 1 жовтня 2024 року»* and *«по 31 грудня року, у якому»*, and 4113-IX and 4835-IX are what replaced them. The end is conditioned on an event, not a date — `features.toml`'s `martial-law-ends-one-belief-two-places` |
| Reporting and payment cadence, group 3 | **Quarterly** | zaxid.net — group 3 pay *«за підсумками першого кварталу»* | Retrieved 2026-08-23, unverified. Context, not a modelled figure — see FR-004 |
| ЄСВ, in the scheme the owner declares | **Zero**, declared explicitly rather than omitted | The owner, stating his own position (2026-08-23) | The one value here sourced to the owner rather than to a public text, and marked as such wherever it appears. The legal ground for a group-3 scheme carrying no ЄСВ is owner verification task 2 |
| ЄСВ second-employment exemption | **Recorded context, not modelled** | частина шоста статті 4 Закону України № 2464-VI — *«Особи, зазначені у пунктах 4 і 5 частини першої цієї статті, звільняються від сплати за себе єдиного внеску за місяці звітного періоду, за які роботодавцем, зокрема резидентом Дія Сіті, сплачено страховий внесок за таких осіб у розмірі не менше мінімального страхового внеску.»* | Text read 2026-08-24 at `zakon.rada.gov.ua/laws/show/2464-17/print`, unverified. Recorded so whoever later declares a scheme that needs it starts from the text rather than a search; nothing here models it (FR-021) |
| Військовий збір on ordinary personal income | **5% of income**, from **1 December 2024**, reverting to **1,5%** on an event-conditioned date | Закон України № 4015-IX від 10.10.2024, підпункт 1 підпункту 1.3 — *«для платників, зазначених у підпункті 1 підпункту 1.1 цього пункту, - 5 відсотків від об'єкта оподаткування, визначеного підпунктом 1 підпункту 1.2 цього пункту»* (the consolidated Code adds a tail 4113-IX inserted, *«, крім доходів, які оподатковуються за ставкою, визначеною підпунктом 4 цього підпункту»* — the military-service rate, which no reading here touches). The reversion is абзац шостий підпункту 1.3, currently *«Починаючи з 1 січня року, наступного за третім календарним роком після року, у якому буде припинено або скасовано воєнний стан, … ставка збору для платників, зазначених у підпункті 1 підпункту 1.1 цього пункту, становить 1,5 відсотка …»* (as amended by Закон № 4835-IX від 07.04.2026, пункт 2 розділу I) | Rate read in the primary text 2026-08-24, unverified. The **date is one derivation**, stated in full because 4015-IX's text does not name it: розділ II п. 1 commences the law *«з дня, наступного за днем його опублікування»* with a closed list of exceptions (*«крім пунктів 3, 4, 9-13 … пункту 6 … підпункту 1 пункту 8 … розділу І цього Закону та підпункту 2 пункту 4 розділу II … які набирають чинності з 1 січня 2025 року»*); the п. 16-1 rewrite is розділ I **пункт 18, підпункт 3**, which is not on that list; and the page's own publication record gives Голос України від 30.11.2024. Day after publication ⇒ **1 December 2024**. розділ II п. 2 confirms it for **this payer class specifically** and is quoted in full because the middle used to be cut: *«Доходи платників військового збору - осіб, визначених пунктом 162.1 статті 162 Податкового кодексу України, нараховані за наслідками податкових періодів до набрання чинності цим Законом, оподатковуються за ставкою військового збору, що діяла до набрання чинності цим Законом, незалежно від дати їх фактичної виплати (надання), крім випадків, прямо передбачених Податковим кодексом України.»* ⚙ The words once cut without an ellipsis — *«- осіб, визначених пунктом 162.1 статті 162 …»* — are the payer-class limiter, and п. 162.1 is exactly підпункт 1 підпункту 1.1, the class this 5% applies to. Visible, they make the clause **narrower and more on point**, not weaker: it is a transitional rule for this rate and it says nothing about ФОП groups 2 and 3, whose own commencement is stated separately in абзац п'ятий підпункту 1.1. Truncated, it read as a general transitional rule, which it is not. The practitioner source that names this levy (biz.ligazakon.net, 19.09.2022) states **1,5%** — the rate in force when it was written, superseded by 4015-IX; that supersession, not the article's silence, is why the statute's rate is the one used. Entered **only** as the levy component of a personal-income reading (FR-010) |
| ПДФО, in every personal-income reading (FR-010a) | **18% of income** | biz.ligazakon.net (19.09.2022) — *«Дохід фізичної особи (не ФОП), який отриманий від операцій з криптовалютою, оподатковуються заставкою 18%+ військовим збором 1,5 %»* | Retrieved 2026-08-24, unverified, and the article states this rate for a фізична особа **не ФОП**, in explicit contrast to a ФОП — of whom it says *«ФОП на єдиному податку І-ІІІ групи використовувати криптовалюти в розрахунках не можна»*, with *«примусове переведення на загальну систему оподаткування та сплата єдиного податку за штрафною ставкою - 15 %»*. Reading it as the rate of a personal-income reading is **one inference, stated**: such a reading is precisely *not the ФОП's єдиний-податок income*. taxer.ua served only a JavaScript shell on 2026-08-24, so this is the single article the 18% rests on. Owner verification task 5 covers the primary article, the effective date, **and the inference** |
| VAT-payer status | The owner states he is not one | The owner | A fact about him, not a legal value: per-owner data, uncited, like his salary |

**Sources.** The primary texts were read on 2026-08-24 and re-read on 2026-08-25 at
<https://zakon.rada.gov.ua/laws/show/4015-IX/print>,
<https://zakon.rada.gov.ua/laws/show/4113-IX/print>,
<https://zakon.rada.gov.ua/laws/show/4835-IX/print>,
<https://zakon.rada.gov.ua/laws/show/2464-17/print> and — for the consolidated Code —
<https://zakon.rada.gov.ua/laws/show/2755-17/print>; the quotes above are from them.

⚙ **How to retrieve a statute from `zakon.rada.gov.ua`, for whoever needs the next one.**
  Always `https://zakon.rada.gov.ua/laws/show/<id>/print`, and always with `curl
  --compressed`: the consolidated Податковий кодекс (`2755-17/print`) arrives gzip-encoded
  and is unreadable without the flag. Two claims this specification made before 2026-08-25
  were **wrong and were re-tested that day**. `/go/<id>` is not a table-of-contents view —
  it is an HTTP **302 redirect to `/laws/show/<id>`**, so the two forms return
  byte-identical responses. And the *«Відбувається форматування тексту!»* shell that plain
  `/laws/show/` sometimes returns is **not** a long-document effect: НБУ Постанова № 148
  is ~33k characters and gets the shell, while № 4015-IX is ~54k and serves in full.
  Length does not predict it, so the rule is *always* `/print` and never a judgement call.

Secondary sources, accessed 2026-08-23:
<https://business.diia.gov.ua/news/viiskovyi-zbir-dlia-fop-ta-iurydychnykh-osib-zaprovadzhuietsia-z-1-sichnia-2025-roku>
(title retrieved; body not returned to automated retrieval),
<https://zaxid.net/viyskoviy_zbir_fop_3_grupa_2025_koli_platiti_skilki_kudi_instruktsiya_termini_n1607266>
(retrieved in full; the єдиний-податок and cadence quotes above are from it),
<https://www.oschadbank.ua/blog/vijskovij-zbir-2025-stavka-stroki-splati-j-pilgi>
(owner-supplied; automated retrieval hit a redirect loop).

**Sources for the ФОП's own foreign-currency account, and for the crypto material
generally** (FR-025; the lineage note at FR-026), accessed 2026-08-23 and re-read
2026-08-24:
<https://id-legalgroup.com/blog/vidobrazhennia-dokhodu-fopom-3-hrupy-otrymanoho-vid-nerezydenta-v-inozemnij-valiuti-viacheslav-komornyj-podatkovyj-konsultant-id-legal-group/>
(ФОП group 3 income from a non-resident in foreign currency; cites п. 292.5, п. 292.6 and
п. 291.4 ст. 291 ПКУ, and references no ДПС consultation),
<https://factor.academy/blog/deklaraciya-fop-3-grupi-za-1-kvartal-2025-inozemnij-valyutnij-doxid/>
(the same recognition, on the same two provisions — *«дата отримання доходу платника ЄП =
дата надходження коштів такому платнику у грошовій (готівковій або безготівковій) формі»*
and *«дохід в іноземній валюті перераховується у гривні за офіційним курсом гривні до
інвалюти, встановленим НБУ на дату отримання такого доходу»*. The account it describes is
a **валютний рахунок ФОП** — *«курс, що діяв на дату зарахування коштів на валютний
рахунок ФОП»*, *«потрібна сума у гривні буде вказана у банківській виписці по валютному
рахунку»*. ⚙ It does **not** say the bank is Ukrainian; this specification said so until
2026-08-25, which was an unmarked inference inside a source annotation — the exact defect
the annotation exists to prevent. Re-read 2026-08-24 and 2026-08-25: the article names no
foreign-located account and no payment system either, and the words *Payoneer*, *Wise*,
*Veem*, *платіжн*, *українськ* and *закордонн* do not appear in it),
<https://forbes.ua/inside/v-ukraine-prinyali-zakon-kotoryy-dolzhen-vyvesti-kriptoaktivy-iz-teni-kak-budet-rabotat-rynok-i-kakie-budut-nalogi-17022022-3741>
and <https://yankiv.com/opodatkuvannya-kryptovalyuty/> (the virtual-assets law of
17.02.2022 produced no operative tax framework; draft 10225-д followed, proposing *«18%
податок на доходи фізичних осіб»* plus *«5% військовий збір»* — a pairing that coincides
numerically with the personal-income readings declared here without being their source,
which is why FR-026 pins the lineage),
<https://biz.ligazakon.net/analitycs/214027_fop-ta-kriptovalyuta-operats-rozrakhunki-ta-podatki-v-ukran>
(19.09.2022; states 18% + 1,5% for a фізична особа **не ФОП** and, separately, that a ФОП
on the єдиний податок may not settle in crypto — see the ПДФО row for what it does and
does not support), and <https://taxer.ua/uk/kb/kryptovalyuta-u-fop-na-ep> (listed as
accessed 2026-08-23 with no record of what came back; on 2026-08-24 it returned only a
JavaScript loading shell, so nothing in this specification rests on it).

**Sources for the payment-system and personal-card destinations** (FR-026a and FR-026b —
one article carries both, and owner verification task 6 covers both), accessed 2026-08-24
and re-fetched 2026-08-25: <https://yankiv.com/dps-protiv-nbu-payoneer-fop-2025/>
(29.09.2025), which is **about Payoneer and nothing wider** — *закордонн*, *Wise*, *за
кордоном* and *рахунок за межами* appear zero times, and its argument turns on ДПС
*«визнає Payoneer небанківською установою»* — and which reports a **conditional** ДПС
position, held *«у своїх роз'ясненнях та індивідуальних податкових консультаціях (ІПК)»*
with no number given for any: *«датою отримання доходу ФОП є дата зарахування коштів на
рахунок у системі Payoneer, а не на банківський рахунок в Україні»*, but *«щоб ці кошти
вважалися доходом підприємця, їх необхідно перерахувати на український банківський рахунок
ФОП (у форматі IBAN) до кінця звітного періоду»*, failing which *«вони оподатковуються як
дохід фізичної особи за значно вищими ставками: 18% ПДФО та 5% військового збору»* — and
cites no ІПК, letter or ЗІР number for any of it — though it **does** cite a numbered
document, *«Положення … №5»*, for the **НБУ counter-reading** that Payoneer receipts are
not yet the entrepreneur's income. **This is the source FR-026a's readings are readings
of**, since 2026-08-25: it addresses this destination, which is why Line 2 calls for a
switch at all, and it numbers nothing on the side a charge would rest on, which is why
Line 1 refuses every one of them the INTERPRETED level. Before that date this
specification recorded it as a starting point that nothing rested on, and refused the
destination outright.

**Source for the crypto-exchange destination** (FR-026c), retrieved 2026-08-27:
<https://7eminar.ua/news/4193-ci-je-doxodom-fopa-kosti-u-viglyadi-kriptovalyuti>
(23.01.2025), an editorial Q&A whose **question is this destination in as many words** —
*«Чи включається до доходу ФОП кошти отримані підприємцем за надані послуги на рахунок
відкритий на платформі Binance?»* — answered *«Ні, не включаються. Binance – це сервіс
обміну криптовалют. ФОП може отримувати оплату за надані послуги лише у грошовій формі і
лише на рахунки відкриті в українському банку. А оплата за послуги у криптовалюті не є
доходом ФОП, а є доходом фізособи.»*, concluding *«Тому, такий ФОП повинен включити такі
кошти до оподаткованого доходу фізособи і сплатити з такого доходу ПДФО та ВЗ.»* It cites
ЗІР 107.01.02, ЗІР 104.08 and п. 168.2.1 ПКУ / ЗІР 103.02 — **none of them on the
destination proposition**: the first two are about selling crypto and about the general
system's crypto bookkeeping, the third about the general declare-and-pay duty for
non-agent and foreign income.

**Sources for a bank account outside Ukraine** (FR-026d). **Two ДПС documents were
retrieved in full on 2026-08-27** from the public ІПК register at <https://ipk.vobu.ua/>
and the companion document archive, so this row's readings rest on primary text rather than
on a practitioner's report of it:

- **Лист ДПСУ від 04.07.2022 № 5064/Г/99-00-24-03-03-09** *«Щодо оподаткування зарубіжних
  доходів ФОП»* (<https://document.vobu.ua/doc/14135>): *«якщо кошти, отримані від
  нерезидента на рахунок, підкритий у іноземному банку, не зараховані на рахунок для
  здійснення підприємницької діяльності у банку в Україні, то такі кошти не включаються до
  доходу фізичної особи – підприємця платника єдиного податку»*, and *«дохід, отриманий
  фізичною особою – резидентом з джерел за межами України, включається до загального
  річного оподатковуваного доходу як іноземний дохід та оподатковується податком на доходи
  фізичних осіб [та] військовим збором на загальних підставах»* (п. 170.11 ст. 170,
  п. 164.4 ст. 164, п. 16-1 підрозділу 10 розділу ХХ ПКУ). The *«підкритий»* is the
  document's own typo.
- **ІПК від 21.01.2022 № 100/ІПК/99-00-04-03-03-06**
  (<https://ipk.vobu.ua/view/25359-100-IPK-99-00-04-03-03-06>), answering *«фізична особа –
  підприємець – платник єдиного податку третьої групи, який планує для отримання доходу від
  своєї діяльності за договором про надання послуг, укладеним з нерезидентом, відкрити
  рахунок в іноземному банку»* — the owner's own shape of question. On Q1: *«чинним
  законодавством не заборонено фізичним особам відкривати рахунки у фінансових установах
  інших країн. Водночас, кошти за операціями суб'єктів господарювання - резидентів, зокрема,
  з експорту товарів (послуг), підлягають зарахуванню на рахунки резидентів у банках
  України»* (Положення № 5, пп. 16 і 23). On Q2 and Q3, which asked whether such income
  bears ПДФО, ВЗ and ЄСВ, it recites the єдиний-податок machinery and concludes only that a
  ФОП *«можуть здійснювати зовнішньоекономічну діяльність за умови дотримання вимог розділу
  XIV Кодексу»*. It closes *«індивідуальна податкова консультація має індивідуальний
  характер і може використовуватися виключно платником податків, якому надано таку
  консультацію»*.
- **ІПК від 27.01.2023 № 177/ІПК/99-00-04-01-04-06** was cited by factor.academy for the
  personal-income position and **does not support it**: retrieved at
  <https://ipk.vobu.ua/view/26440-177-IPK-99-00-04-01-04-06>, that number and date are a
  consultation for a Товариство *«щодо сплати земельного податку»*. Recorded rather than
  silently dropped, because the whole reason to retrieve was to find out.

The practitioner articles that led to those documents, both retrieved 2026-08-27:
<https://factor.academy/blog/fop-otrimu-koshti-na-rahunok-v-inozemnomu-banku/> (10.03.2024),
which argues for the ФОП reading — *«кошти, отримані у валюті на рахунок, відкритий за
кордоном, слід оподатковувати за тими правилами, що і доходи, отримані на рахунки, відкриті
в українських банках у валюті… на дату надходження валюти слід кількість отриманої валюти
помножити на курс НБУ… сплатити податок (2/3/5 %)»*, notes *«в законодавстві України не
існує і прямої заборони на отримання ФОП доходів на іноземний банківський рахунок, навіть
для єдиноподатників»*, and calls the fiscal approach *«неправомірний»*; and
<https://bip.net.ua/articles/fop-otrimuye-dohid-na-rahunok-v-inozemnomu-banku/>, which
states the ДПС conditional the same way and cites no ІПК of its own. ⚙ The ДПС's own page on
the question (`zp.tax.gov.ua/media-ark/news-ark/708956.html`) returns **HTTP 403** to
automated retrieval, as `bank.gov.ua` does for feature 011; its title is known and its text
is not, so nothing rests on it and it is not counted among this row's sources.

The 3% rate that applies to a VAT payer is **not** entered: the owner is not one, no
citation for it was retrieved, and a legal value nothing consumes is a value nobody
checks. The regime declaration names which variant applies (FR-002) so the second variant
is a data-only addition when it is ever cited.

## Design positions this specification is built on

Four decisions were taken before the requirements were written. Each is argued rather than
asserted, because each rules out a shape that would otherwise look reasonable.

**1. ЄСВ is not a tax on income and must not be modelled as a rate.** Two things disagree,
not one. Its *trigger* is a period elapsing, not income arriving — it is owed in a month
with no income at all. Its *base* is a statutory fixed amount, not a percentage of
anything. Folding it into an income-tax rate would misclassify it even in the cases where
the arithmetic happened to come out right, and it would come out wrong the first month
income is zero. So a scheme declares **periodic components** alongside its rate
components, and that is the shape whatever charges ЄСВ will need.

**2. A taxation scheme is the declared entity, and one of its components can be nothing.**
*(Owner decision, 2026-08-23, replacing an earlier design in which ЄСВ was a periodic
obligation with a per-month conditional exemption bolted onto one regime.)* What the
system needs is to apply **different taxation schemes** — ФОП group 3, ФОП group 2, a
legal entity — each a declared set of components. The owner's scheme is one of them and it
charges no ЄСВ. That nil is a property of the declared scheme, not the output of an
exemption the engine evaluated.

⚙ This is Principle II working rather than a convenience. Which scheme applies is a
**declaration**, and the alternative was an engine that knew what an exemption was,
evaluated its condition period by period, and would still have needed the scheme concept
the first time a scheme charged ЄСВ unconditionally — a branch bought and then paid for
twice. The exemption's citation survives as recorded context for whoever declares a scheme
that needs it; nothing here models it.

**3. `IncomeStream.income_tax_rate: float | None` is retired.** It cannot carry two
components with different commencement dates, a fixed-amount obligation, or the choice of
a whole scheme. The stream names a **tax treatment** instead — exactly what feature 006
did for instruments, and the inconsistency 006 left behind.

**4. The tax base and the money received are two different numbers.** The base is the
credited dollars at the official rate on the **credit** date (feature 011). The hryvnia
the owner ends up with comes from a market channel on the **sale** date. Different rate,
different date, different number. Keeping them apart is not a presentational nicety — it
is the difference between what he owes and what he has.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Contract income taxed under the regime it lands in (Priority: P1)

The owner declares that his contract income arrives in a ФОП account in dollars. A month's
income is then charged єдиний податок and військовий збір as two separately named lines on
a hryvnia base — the dollars credited, at the official rate on the credit date — and the
output shows both charges, the base, the rate that struck it and the date that rate
belongs to.

**Why this priority**: This is the feature, and it is the first time the system taxes the
owner's actual largest cash flow with anything but a placeholder. Every
deployable-capacity figure in the model is currently either a zero or an explicit
"unknown"; this is what makes it a number.

**Independent Test**: Declare a synthetic monthly amount arriving on a known date, declare
a synthetic official rate for that date, and check both charges and the base against
arithmetic worked out by hand on paper.

**Acceptance Scenarios**:

1. **Given** a stream declared as arriving in a ФОП account in a foreign currency and a
   declared official rate for the credit date, **When** a month's income is charged,
   **Then** the taxable base is the credited amount at that date's official rate and both
   components are charged on it, matching hand-computed arithmetic within the single
   project tolerance.
2. **Given** the same charge, **When** it is inspected, **Then** the two components appear
   as separately named lines using the names the law uses, each naming its own rate, its
   own cited source and its own verification date — never as one blended percentage.
3. **Given** no official rate is declared for the credit date, **When** the charge is
   attempted, **Then** the outcome is the typed refusal feature 011 specifies, naming the
   date — no charge is produced and no rate is borrowed from another date.
4. **Given** the credited dollars are later sold for hryvnia through a declared channel on
   a different date, **When** results are produced, **Then** the hryvnia received and the
   hryvnia tax base are two separately reported figures, and neither is presented as the
   other even when they happen to be close.
5. **Given** any charge produced under this regime, **When** its provenance is inspected,
   **Then** it carries the marks of both the rate schedule and the official-rate
   observation that struck its base.

---

### User Story 2 - The stream names a regime, not a rate (Priority: P1)

The owner declares which tax treatment his income stream falls under, the way he declares
which tax classes an instrument falls under. The rates live in curated tax data with their
citations. A stream that names no treatment still reports what it reports today: the
deployable amount is unknown, and at most the gross.

**Why this priority**: Equal-highest, because Story 1 is unimplementable on the old shape
and because the migration is the part that can quietly break something. Two behaviours
must survive it verbatim — *undeclared is not zero*, and *no net figure quietly equals a
gross one* — and they are exactly the kind of behaviour a schema change deletes by
accident.

**Independent Test**: Run feature 002's deployable-capacity cases against the new shape
and confirm the undeclared case still yields a result with no net field on it; then
declare a treatment and confirm the net figure is net of the regime's charge rather than
of a scalar.

**Acceptance Scenarios**:

1. **Given** an income stream naming a declared tax treatment, **When** deployable capacity
   is computed, **Then** it is net of the charges that treatment produces, and every
   component of `gross − charged = net` is present in the result.
2. **Given** an income stream naming no tax treatment, **When** deployable capacity is
   computed, **Then** the result carries no net field at all and states that the owner has
   not declared a treatment — the same claim, the same shape and the same reason as feature
   002's undeclared-rate result.
3. **Given** an income stream naming a treatment no tax file declares, **When** the data is
   loaded, **Then** loading fails naming the file, the stream and the unknown treatment; no
   default treatment exists and none is substituted.
4. **Given** the migration, **When** the tax rates are located, **Then** they are in curated
   tax data carrying source, retrieval date and verification date — not in the per-owner
   stream file, whose citation exemption never covered a legal rate.

---

### User Story 3 - A projection that crosses the commencement date (Priority: P1)

The owner projects income across 1 January 2025. From that date the військовий збір is
charged at 1%, from a dated entry in a data file. Before it, the schedule does not reach and
the run says so, naming the component and the date — it does not quietly charge nothing.

**Why this priority**: Equal-highest because it is the correctness proof for the whole
dated-schedule mechanism against a real statute rather than a synthetic fixture, and
because getting it wrong is invisible: a projection that charged 1% for all of 2024 would
look entirely plausible, and so would one that charged 0%.

**Independent Test**: Project monthly income across the commencement date, check the
charged side by hand, and confirm the uncharged side is a typed error naming the component
and the date rather than a levy line reading zero or a levy line silently absent.

**Acceptance Scenarios**:

1. **Given** a levy schedule whose earliest entry is effective 1 January 2025, **When**
   income arrives in December 2024 and in January 2025 in one run, **Then** the January
   charge carries a 1% levy line matching hand-computed arithmetic and the December one is a
   typed error naming the component and the date — not a charge with the levy line missing,
   and not a levy line of zero.
2. **Given** income dated before the earliest entry of a component's schedule, **When** the
   charge is attempted, **Then** the outcome is a typed error naming the component and the
   date (feature 006's FR-012). No rate is defaulted, no zero is silently charged, and no
   entry is backdated to make a projection run.
3. **Given** a future legislated change to either component, **When** it is entered,
   **Then** it is one dated entry added to a data file, carrying its own source, retrieval
   date and verification date, with no source-code change.

---

### User Story 4 - A scheme is a set of components, and one can be nothing (Priority: P2)

The owner declares which taxation scheme he is in, and the scheme decides the whole set of
components charged. For his — ФОП group 3, non-VAT — that set is єдиний податок, військовий
збір, and a ЄСВ component declared at zero. A scheme for a different ФОП group, or for a
legal entity, declares a different set, and one of those charges ЄСВ as a real amount per
elapsed period. Both run on the same engine, and neither scheme's name appears anywhere in
it.

**Why this priority**: P2 because the owner's own scheme charges nothing here, and P2
rather than P3 because *nothing charged* has to be a stated property of the declaration
rather than an absence in the output — and because the day he moves to another group or to
a legal entity, applying the new scheme must be a declaration, not an engine edit. An
unmodelled obligation becomes an unbudgeted bill.

**Independent Test**: Declare two synthetic schemes differing only in the amount of their
periodic component — one zero, one not — point one stream at each, confirm the totals differ
by exactly the declared amount, and confirm the zero is reported as a declared value with
its provenance rather than as an absence — with no source file edited.

**Acceptance Scenarios**:

1. **Given** the scheme the owner declares, **When** the projection runs, **Then** nothing
   is charged for ЄСВ, the nil is reported as a **declared zero** carrying its source and
   its empty verification date, and every figure resting on it is marked — distinguishable
   both from a component the scheme does not declare at all and from one declared with no
   amount in force for the period.
2. **Given** a second scheme declaring a periodic component with a dated schedule of
   statutory amounts, **When** a stream names it, **Then** the amount is charged once per
   elapsed period, with zero lines of source code changed.
3. **Given** a period with zero income under a scheme that charges a periodic component,
   **When** the obligation is evaluated, **Then** it is charged anyway — the trigger is the
   period, not the income — which is the property that distinguishes it from a rate.
4. **Given** a scheme declaring a periodic component with no amount in force for a period,
   **When** the obligation is evaluated, **Then** the outcome is a typed refusal naming the
   period and the missing amount — never a zero, and never a rate applied to income as a
   stand-in.

---

### User Story 5 - The mandatory sale, and the spread paid twice (Priority: P2)

The dollars on the ФОП account cannot be spent domestically; they are sold for hryvnia
through a declared channel, at a cost. If the owner later wants dollars again — on a debit
card — he pays a spread a second time. Both costs come out of machinery that already
exists, and this feature adds none of it.

**Why this priority**: P2 because the numbers already work — 002 costs the conversion and
forbids reporting a one-way figure as a round trip (required test G6) — but the *boundary*
needs stating in this spec or the plan will re-model routing here. What this feature owes
the sale is the tax consequence of it, which is precisely that there is none: the sale does
not change the base.

**Independent Test**: Declare the ФОП account and the sale as an ordinary route leg through
an existing channel; confirm the cost is produced by the existing costing path, that the
round-trip figure back to dollars is the existing round-trip figure, and that neither
changes the tax base by a digit.

**Acceptance Scenarios**:

1. **Given** the compulsory sale of dollars on the ФОП account, **When** it is modelled,
   **Then** it is a declared route leg through a declared channel at a declared venue, and
   this feature introduces no new leg kind, no new channel kind and no new cost mechanism.
2. **Given** the owner later converting hryvnia back to dollars, **When** the comparison is
   produced, **Then** it is the existing round-trip cost — the second spread is not a new
   concept, it is the half of the round trip feature 002 already refuses to omit.
3. **Given** a sale executed at any market rate whatsoever, **When** the tax figures are
   recomputed, **Then** the taxable base is unchanged: it was fixed at the credit date and
   nothing about the sale moves it.
4. **Given** the difference between the hryvnia the base implies and the hryvnia actually
   received, **When** results are produced, **Then** the difference is visible as its own
   reported figure and is explicitly labelled as *not part of the taxable base*.

---

### User Story 6 - A second regime is data (Priority: P3)

A different ФОП group, the general system, a VAT-payer variant, or another jurisdiction's
regime is a data-only addition. Nothing in the engine knows that group 3 exists.

**Why this priority**: Principle II applied to the tax regime, and P3 for the same reason
006's and 007's equivalents were: if the other stories are built correctly this already
works, and this story's job is to prove it — before required test E8 (the same scenario
under two jurisdictions) discovers otherwise.

**Independent Test**: Declare a second, differently identified synthetic regime with a
different component set and different schedules, point a second synthetic stream at it, and
confirm both produce complete results with no source file edited.

**Acceptance Scenarios**:

1. **Given** a second regime declared purely as data with a different set of components,
   **When** a stream names it, **Then** complete results are produced with zero lines of
   source code changed.
2. **Given** a regime declaring a component the engine has never seen a name for, **When**
   it is charged, **Then** the component is charged and reported under its declared name —
   no component name is hard-coded, and no engine branch exists for "the levy".

---

### Edge Cases

- **Income credited on a day the official rate is not published** — feature 011's behaviour
  applies unchanged: a refusal naming the date, unless the series declares a cited
  non-publication-day rule. This feature does not get its own answer to that question.
- **Income dated before a component's earliest schedule entry** — a typed error naming the
  component and the date (006 FR-012). In particular, income before 1 January 2025 is not
  charged a levy of zero: the schedule simply does not reach back, and saying so is
  different from saying the rate was nil.
- **Income dated after the levy's statutory sunset** — no such date exists to test against,
  because the sunset is conditioned on an event and not on a date (FR-008a). The schedule
  therefore charges 1% for every date it reaches, and the declared termination sits beside
  it as recorded, cited context. What must not happen is the absence of an end date being
  read as a claim that the charge is permanent; it is a gap this repository has already
  named (`features.toml`, `martial-law-ends-one-belief-two-places`).
- **A period with zero income under a scheme that charges a periodic component** — the
  rate components charge nothing (no income), and the periodic component is evaluated
  anyway, because a period elapsed. This is the case a rate-shaped model gets wrong.
- **A scheme that charges no ЄСВ beside one that does** — the difference is two
  declarations, not two code paths, and the first reports its nil as a property of the
  scheme rather than as an absence.
- **A period whose scheme declares a periodic component with no amount in force** — a typed
  refusal naming the period, never a zero.
- **A stream naming a treatment that no tax file declares** — a load-time failure naming the
  file, the stream and the unknown treatment.
- **A stream naming no treatment at all** — not an error: the same "deployable capacity
  unknown, at most the gross" result feature 002 produces today, with no net field on it.
- **A stream declaring a routing origin and no crediting destination, or the reverse** — a
  load-time failure naming the stream and the missing field. Neither is inferred from the
  other: for the owner today they are Deel and the ФОП account, and either inference would
  be wrong (FR-024a).
- **A stream in the tax currency naming this regime** — charged normally, with no official
  rate consulted (011 FR-009). The regime is not a foreign-currency feature; it is a regime
  that happens to receive foreign currency.
- **Two regimes declaring the same identifier** — a load-time collision, as everywhere else.
- **A regime declaring a component with a negative rate, an unordered schedule, or two
  entries on one effective date** — load failure naming the file and the field (006 FR-003).
- **The mandatory sale executed at a rate far from the official one** — the taxable base
  does not move. The gap is reported as its own figure and labelled as outside the base.
- **Contract income credited to the ФОП's foreign-currency account** — recognised on the
  credit date and charged under this scheme; INTERPRETED, with its citations on the figure
  (FR-025).
- **Contract income credited to a crypto exchange** — a labelled switch of **one** figure at
  personal-income rates (FR-026c). The source that reaches it excludes the ФОП scheme in
  answer to a question naming this destination; the four sources cited before it do not reach
  it at all, and FR-027 keeps that reasoning.
- **Contract income credited to an international payment system** — a labelled switch of
  **three** figures, the ДПС and НБУ readings of the ФОП scheme on two different dates and
  the non-repatriation reading at personal-income rates (FR-026a). Not INTERPRETED, and not
  refused.
- **Contract income credited to a personal, non-ФОП account or card** — a labelled switch of
  **one** figure at personal-income rates (FR-026b). The one source that reaches this
  destination excludes the ФОП scheme rather than contesting it, so there is no second
  reading to compute, and it numbers nothing, so the one figure is still not the tax owed.
- **Contract income credited to a bank account outside Ukraine** — a labelled switch of
  **two** figures, the ФОП scheme at the credit date against personal income (FR-026d). The
  only row whose readings are numbered on both sides, and UNSETTLED for exactly that reason:
  two ДПС positions that contradict each other.
- **Contract income credited somewhere no source names a reading for** — refused as a typed
  result naming the destination and the scheme (FR-027). Applying these rates to income that
  may not be this scheme's income at all would be inventing a legal position.

## Requirements *(mandatory)*

### Functional Requirements

**The regime as declared data**

- **FR-001**: A tax **regime** — the taxation scheme an income stream is under — MUST be
  declarable purely as data: an identity, the set of components it charges, each component's
  dated schedule, and its reporting and payment cadence. Adding one — a different ФОП group,
  a legal entity, the general system, another jurisdiction's — MUST require no source-code
  change and MUST introduce no scheme-specific engine behaviour. No engine branch may exist
  for a named component. ⚙ The set of components is the scheme's, not the engine's: what a
  scheme charges is exactly what it declares, which is what lets one scheme charge ЄСВ and
  another charge none without a rule anywhere deciding between them (FR-020).
- **FR-002**: The declaration MUST name which variant of the regime applies where the law
  offers more than one (for group 3, the VAT-payer and non-VAT-payer rates). The variant
  the owner is in is a **fact about him** and is declared as per-owner data with no
  citation, exactly as his salary is; the **rates** of every variant are public legal facts
  and live in curated tax data with citations. ⚙ This split is the point of the feature's
  data-model change, not an incidental tidy-up: `data/README.md`'s citation exemption for
  per-owner data is argued for an owner's statement about himself, and it never covered a
  legal rate.
- **FR-003**: Every rate, amount, effective date and declared rule MUST carry its value,
  source, retrieval date and verification date, and an empty verification date is permitted
  and expected. No legal value in this feature may originate from an implementer's or an
  agent's memory. The mark MUST propagate to every derived figure.
- **FR-004**: The regime MUST declare its reporting and payment cadence (quarterly, for
  group 3) as data, and this feature MUST record each liability against the period it
  accrues to. It MUST NOT model payment timing, filing deadlines or the cash movement that
  settles a liability — those change no figure here and belong to feature 009 (required
  test E7). ⚙ The cadence is declared now, unused, so that 009 inherits a declared fact
  rather than having to guess one; a filing deadline that moves no number is context and is
  recorded as such in the sources table above, not as a requirement.

**Two components, two commencement dates**

- **FR-005**: The regime MUST charge **єдиний податок** and **військовий збір** as two
  separately named components on one base. They MUST NOT be blended into a single
  percentage at any point — not in the data, not in the computation, and not in the output.
  ⚙ `core/tax/interface.py` already argues this for PIT and the levy: *"foreign withholding
  creditable against PIT but not against the levy cannot be expressed against a blended
  figure at all."* The same argument applies to any two components with independent legal
  lives, which these have — a different statute created one of them, on its own date.
- **FR-006**: Component lines MUST be reported under the names the law uses for them. ⚙ The
  existing charge record carries two fixed lines named for personal income tax and the
  military levy. A єдиний податок charge is neither, and putting it in a field named
  personal income tax would be a mislabelling that no downstream reader could detect.
  Whether that is met by generalising the charge record to named components or another way
  is a planning decision; what this requirement fixes is that the output may not lie about
  what was charged.
- **FR-007**: Each component's rates MUST be declared as a **dated schedule** in feature
  006's sense: ordered entries, each with its effective date, its rate and its own
  provenance. The rate applied to an income event is the entry in force on the event's date,
  effective date inclusive (006 FR-011).
- **FR-008**: The військовий збір component MUST be declared effective **1 January 2025**
  at **1% of income**, with the **rate** cited to Закон України № 4015-IX від 10.10.2024 and
  the **commencement** cited to Закон України № 4113-IX від 04.12.2024, which replaced the
  1 жовтня 2024 that 4015-IX's own text names. **4015-IX MUST NOT be cited for either date.**
  Income dated before the schedule's earliest entry MUST produce a typed error naming the
  component and the date (006 FR-012) — it MUST NOT be charged a rate of zero, and it MUST
  NOT produce a charge with the levy line merely absent, because *"the schedule does not
  reach this date"*, *"the rate was nil"* and *"this scheme charges no such component"* are
  three different claims and only the first is true here.

  ⚙ A cited pre-commencement nil is **available and deliberately not built**: 4113-IX's
  «встановлюється з 1 січня 2025 року» is itself a statement that these payers owed nothing
  before that date, so a declared, cited *not in force before* boundary would let December
  2024 report a nil with a citation instead of an error. It would also add a fourth state to
  FR-020's three, and nothing in this feature needs it — the owner's projections start after
  the date. Recorded so the next reader knows the error is a choice and not a gap.
- **FR-008a**: The same component MUST carry its **termination** as a declared, cited fact
  beside its commencement: the levy runs *«по 31 грудня третього календарного року,
  наступного за роком, у якому буде припинено або скасовано воєнний стан»*, cited to Закон
  України № 4835-IX від 07.04.2026 (пункт 1 розділу I), which replaced 4015-IX's *«по 31
  грудня року, у якому»*. A schedule that declares a commencement and no end asserts a
  permanent charge, and this one is not permanent. ⚙ A declaration carrying half a provision
  is the same defect as a citation to a proposition the source does not make.

  The termination MUST NOT be entered as a schedule end date, because it **is not a date**:
  it is conditioned on an event whose occurrence nothing in this system models. Until that
  changes it is recorded as declared context on the component — visible, cited, and not
  applied — and the modelling question stays where it already lives,
  `specs/features.toml`'s `[[future]]` entry `martial-law-ends-one-belief-two-places`. This
  feature MUST NOT invent an end date, and MUST NOT let the absence of one read as a claim
  that the levy is permanent.
- **FR-009**: The єдиний податок component MUST be declared at **5% of income** for the
  non-VAT-payer variant of group 3, cited to **підпункт 2 пункту 293.3 статті 293 ПКУ**
  — *«5 відсотків доходу - у разі включення податку на додану вартість до складу єдиного
  податку»* — with its effective date taken from Закон № 909-VIII від 24.12.2015, which set
  that wording. Where a rate's available citation establishes only that it is in force as of
  the source's own date, the entry MUST be declared effective from that date, and earlier
  income MUST refuse under FR-008's rule rather than being charged at a backdated entry;
  this rate is no longer such a case, and the rule stays for the next one that is. The exact
  commencement — № 909-VIII takes effect *«з дня набрання чинності Законом України "Про
  Державний бюджет України на 2016 рік", але не раніше 1 січня 2016 року»* — is owner
  verification task 1.
- **FR-010**: The levy on ordinary personal income (1,5% → 5% from 1 December 2024, the same
  law; reverting to 1,5% on the same event-conditioned date, абзац шостий підпункту 1.3 as
  amended by Закон № 4835-IX — recorded, like FR-008a's termination, and not applied) MUST
  NOT be entered as the treatment of an **employment** income stream: none is modelled
  here. It is declared in exactly **one** place — the personal-income reading's levy
  component, beside the ПДФО component of FR-010a — cited like every other rate here. **Every
  personal-income reading consumes that one declaration and none may copy it**; which
  readings those are is the table under "Legal grounding", not a list kept here. ⚙ The rule
  this expresses is not *this rate stays out*; it is *a rate no declaration names stays out*,
  because a legal value nothing consumes is a number nobody checks.
- **FR-010a**: The **ПДФО** component of every personal-income reading MUST be declared at
  **18% of income**, as one dated entry in curated tax data with its own provenance, cited to
  biz.ligazakon.net (19.09.2022) — *«Дохід фізичної особи (не ФОП) … оподатковуються
  заставкою 18%»* — with an **empty verification date** and the inference that carries it
  into these readings recorded on the entry, not only in prose. The primary Tax Code article
  and the rate's effective date are owner verification task 5. It MUST be **one**
  declaration, never copied per destination, and it MUST NOT be declared as a treatment any
  stream can name: no personal-income stream is modelled
  here, and this rate exists only inside a labelled reading.

  ⚙ Added 2026-08-26 because it was the only legal value in this feature carried by the
  source table and a bullet with no requirement naming it — FR-008 pins the 1%, FR-009 the
  5%, FR-010 the levy, and nothing pinned the 18%. A rate whose only home is a table is the
  one a plan drops, and this one is half of the gap every switch here exists to size.

  ⚙ **Stale list, live rule.** FR-026c and FR-026d consume this one declaration too; the
  enumeration predates them. The governing form as of 2026-08-27 is FR-010's — *which
  readings those are is the table under "Legal grounding", not a list kept here* — and this
  sentence should carry no list at all.

**The base is in the tax currency**

- **FR-011**: The taxable base of a foreign-currency income event under this regime MUST be
  the amount credited, converted at the official rate for the **credit date**, through
  feature 011's machinery. This feature MUST NOT introduce its own conversion, its own rate
  lookup, or its own idea of which date applies.
- **FR-012**: The hryvnia the owner actually receives MUST be computed from the declared
  channel that performs the sale, on the sale's own date, through the existing costing
  machinery. It MUST NOT be computed from the official rate, and the taxable base MUST NOT
  be computed from the channel (011 FR-012, FR-013).
- **FR-013**: The difference between the hryvnia the base implies and the hryvnia actually
  received MUST be reported as its own figure and MUST be labelled as **not part of the
  taxable base**. ⚙ This is the owner's real exposure and it points either way: the base can
  exceed what he has, or fall short of it. Reporting only one of the two numbers would hide
  whichever direction it went in, and netting them would assert a deduction nobody cited.
- **FR-014**: No deduction of any kind MUST be applied to the base by this feature — not the
  conversion spread, not a fee, not a cost. For the **bank commission** this is now
  **INTERPRETED** rather than merely assumed: practitioner guidance reads the income as the
  whole invoice amount including the commission, not the net received (id-legalgroup, citing
  п. 292.5, п. 292.6 and п. 291.4 ст. 291 ПКУ — see Sources), and that citation MUST travel
  with the base. Every other candidate deduction remains an **absence, recorded**: an owner
  verification task, and until it is answered with a citation the base is the credited
  amount and nothing is subtracted from it. A modelled zero deduction and an unasked
  question are different claims.

**The stream names a treatment**

- **FR-015**: `IncomeStream.income_tax_rate` MUST be retired. An income stream MUST instead
  name a declared tax treatment, exactly as an instrument names tax classes (feature 006).
  A stream MAY name none.
- **FR-016**: A stream naming **no** treatment MUST produce the same claim, the same shape
  and the same reason as feature 002's undeclared-rate result: no net field at all, the
  gross reported as a known upper bound, and a stated reason that the owner has not declared
  a treatment. ⚙ 002's argument survives the migration verbatim — *no treatment declared* is
  not *a treatment that charges zero* — and this requirement exists because a schema change
  is exactly what deletes a carefully argued distinction by accident.
- **FR-017**: A stream naming a treatment that no tax file declares MUST fail at load,
  naming the file, the stream and the unknown treatment. No default treatment exists and
  none may be substituted.
- **FR-018**: The landing change MUST carry the retirement through everything that records
  the old shape: `data/README.md`'s citation-exemption note, the declaration-schema
  contract, `docs/METHODOLOGY.md`'s deployable-capacity formula, and a ⚙ cross-reference on
  feature 002's FR-007 recording that this feature supersedes it. ⚙ Recorded here as an
  obligation because 002's spec is not edited from this specification's branch — the same
  pattern feature 007 used for 001's FR-022.

**The scheme's component set, and ЄСВ**

- **FR-019**: A scheme MUST be able to declare a **periodic component**: an amount owed per
  elapsed period rather than a rate applied to income. Its declaration carries the period, a
  dated schedule of statutory amounts, and its own provenance. It MUST NOT be expressible
  as, or coerced into, a rate on income. ⚙ Two things differ: the trigger is a period
  elapsing rather than income arriving, and the base is a statutory sum rather than a
  percentage. A rate-shaped model gets the zero-income period wrong.
- **FR-020**: A scheme charges exactly the components it declares. A component the scheme
  does not declare MUST be reported as *not charged by this scheme* rather than as an
  absence or as a zero the engine chose, and MUST remain distinguishable from a declared
  component with no amount in force, which refuses under FR-021. Where a scheme declares a
  component whose amount or rate is zero, that zero MUST carry its own provenance exactly as
  a non-zero value does — an uncited zero is the figure that gets believed without checking.
- **FR-021**: The scheme the owner declares — ФОП group 3, non-VAT — charges **no ЄСВ**, and
  that nil MUST be a property of the declared scheme rather than the output of any engine
  rule, exemption or default. No per-period exemption condition is modelled by this feature.
  The component MUST be declared **explicitly at zero** rather than omitted, its source
  recorded as the owner's own statement of his position (2026-08-23) and its verification
  date empty, so every figure resting on it renders marked until owner verification task 2
  replaces that source with a legal citation. ⚙ An omitted component is invisible; a
  declared zero can be argued with. This is the one value in this feature whose source is
  the owner rather than a public text, and marking it as such is what stops it being read as
  a curated legal fact. A scheme that declares a periodic component but has no amount in
  force for a period MUST produce a typed refusal naming the period and the missing amount —
  never a zero, and never a rate on income used as a stand-in.

  ⚙ The **statutory ЄСВ monthly minimum amounts** are recorded rather than modelled, so
  that their absence is not mistaken for a gap: no scheme declared here charges the
  component, and the first scheme that does declares them with its own citations or refuses
  under this requirement. What the owner's nil rests on legally — that a group-3 scheme can
  carry no ЄСВ — is owner verification task 2.

**What this feature leaves to routing**

- **FR-022**: This feature MUST NOT re-model funding routes. The Deel → ФОП account versus
  Deel → Coinbase choice is a funding-route question that features 002, 003 and 004 already
  answer: 002 costs the corridor, 003 says whether the money can get back out to something
  spendable, 004 composes chains. What this feature contributes is the **tax consequence of
  where the money is credited**, and nothing else.

  Where it is credited is a different question from where the route started, and the two are
  separately declared facts on the stream (FR-024a) answered by FR-025 to FR-027 rather than
  here.

- **FR-023**: The compulsory sale of foreign currency on the ФОП account MUST be modelled
  with the existing route machinery — a declared leg through a declared channel at a
  declared venue — and this feature MUST introduce no new leg kind, no new channel kind and
  no new concept of compulsion. ⚙ Preferred because the compulsion changes nothing about
  what the conversion *costs*: a forced conversion and a chosen one price identically, and
  the only thing compulsion changes is which routes exist, which is already what a declared
  route registry says. The accepted limitation is that the data then records *that* only one
  route leaves the account and not *why*; if a later feature needs to distinguish "nobody
  declared a route" from "the law forbids one", that is 003's deficit vocabulary being
  extended, not a new mechanism here.
- **FR-024**: The second spread — converting hryvnia back to dollars on a card — MUST NOT be
  modelled as anything new. It is the return half of the round trip feature 002 already
  requires and required test G6 already pins: a one-way figure may never be presented as a
  round-trip one. This feature's obligation is to not accidentally present the sale's
  one-way cost as the whole cost.

**Where the income is credited**

The original single question — *does income credited somewhere other than the ФОП account
fall under this scheme at all?* — was never one question, and collapsing them cost the
answerable one its answer. It is now five named destinations plus a residual, carrying two
different verdicts, which is why the criteria that separate them are stated once under
"Legal grounding" and applied there in a table rather than argued destination by destination
here.

- **FR-024a**: The **crediting destination** and the stream's existing `arrives_at` are two
  different declared facts and MUST be declared separately. `arrives_at` is the **routing
  origin** — the venue where the owner first controls the money, and the node every funding
  route starts from. The crediting destination is the **tax event's location** — where the
  income is credited for the purpose of deciding which reading of FR-025 to FR-027 applies.
  **Neither may be defaulted from the other**, in either direction, and a declaration
  supplying only one MUST fail at load naming the stream and the missing field rather than
  inferring it.

  ⚙ They answer different questions, and for the owner today they hold different values:
  `data/streams/owner-001.toml` declares `contract_usd` with `arrives_at = "deel"` while the
  crediting destination is the ФОП account in USD, which is exactly what FR-025 covers.
  If Deel were ever declared as a crediting destination it would be read against the table
  under "Legal grounding" like any other, and nothing about its being this stream's routing
  origin would privilege it there. A default in either direction would make the engine settle
  that by accident — turning one INTERPRETED charge into a switch, or a switch into an
  uncited charge, depending on which way the default ran. Both are wrong for the same reason:
  routing and recognition are not the same fact.

- **FR-025**: Income from a non-resident credited to the **ФОП's own foreign-currency
  account** — the owner's actual destination, and the one the cited guidance describes —
  MUST be recognised on the **date the funds are credited** and converted to hryvnia at the
  official rate on that date. Verdict **INTERPRETED**: the guidance answers it one inference
  deep from the primary provisions, and the figures it produces MUST carry those citations —
  п. 292.6 ПКУ (the date of income is the date of crediting) and п. 292.5 ПКУ
  (foreign-currency income converts at the official NBU rate on the date of income), as
  cited and applied by id-legalgroup and factor.academy (see Sources).

  An **international payment system**, or a bank account **outside Ukraine**, is **not
  covered by this requirement** — the first because it fails Line 1, the second because the
  numbered positions on it contradict each other. The table under "Legal grounding" is where
  they land, at FR-026a and FR-026d.

  ⚙ Adds nothing to feature 011: this is 011's FR-007 and FR-008 applied unchanged. ⚙ The
  narrowing costs the owner nothing today **provided the two facts of FR-024a are kept
  apart**: his contract income is *routed* through Deel, which this requirement excludes,
  and *credited* to a ФОП account in USD, which it covers. Read against `arrives_at` alone
  — the only destination field a stream carries today — the owner's own stream would fall
  under FR-026a rather than here, which is why FR-024a is a requirement and not a note. What
  the narrowing does cost is a claim this specification could not source: charging a
  foreign-located destination at these rates on the strength of an article that never
  mentions one would be the invented legal position Line 1 exists to keep out.
- **FR-026**: An **UNSETTLED** crediting destination MUST be modelled as an explicit,
  defaultless **labelled scenario switch**, on the pattern feature 009 established for an
  unsettled legal question, with an індивідуальна податкова консультація (ст. 52 ПКУ)
  recorded as its resolution path. Which destinations those are is the table under "Legal
  grounding"; this requirement states what a switch is, and FR-026a to FR-026d state what
  each one holds.

  The system MUST produce **one labelled what-if figure per computable reading**, the count
  being Line 3's output and never a fixed number:
  - each figure MUST state which reading produced it and MUST carry that reading's own
    citations;
  - the system **MUST NOT** label any figure the tax owed, and **MUST NOT** blend, average or
    otherwise combine two of them into a single number;
  - every candidate Line 3 cannot compute MUST be named on the switch with the reason,
    rather than omitted, so a switch is never read as complete when it is not;
  - each reading's components MUST be declared, cited data like every other rate here — a
    єдиний-податок reading is the scheme of FR-007 to FR-009; a personal-income reading is
    the ПДФО of **FR-010a** and the levy of **FR-010**, consumed and never copied. Neither
    may be declared as a treatment a stream can name.

  ⚙ **A personal-income reading's 18% + 5% are the general rates, and their lineage MUST
  be recorded as such.** The 18% is the ПДФО biz.ligazakon.net states for a фізична особа
  не ФОП; the 5% is the levy Закон № 4015-IX sets for ordinary personal income. **Those two
  citations are the rates' source. Two others state the same numbers and are not**, and the
  distinction is what stops four entries becoming one: draft 10225-д proposes 18% + 5% for
  crypto (yankiv.com), and forbes.ua reports a bill setting 18% + 1,5% on virtual-asset
  profit after a five-year preferential period. Required test E4's `draft_18_5` scenario *is*
  the draft's rates, on a crypto **asset** disposal — a different question again.

  ⚙ **Why labelled figures and not a refusal, where a switch is reached at all.** The
  readings a switch holds differ by more than every route cost this engine computes — 5% +
  1% against 18% + the levy on the same base. A refusal tells the owner nothing; labelled
  figures tell him what the uncertainty is worth, which is the decision he actually faces.
  That argument is a reason to compute *readings that exist*, and it is deliberately not a
  reason to manufacture them: where Line 2 or Line 3 leaves nothing to compute, FR-027's
  refusal is the honest output and this argument does not reach it.

  ⚙ **This requirement was the crypto-exchange destination until 2026-08-27**, when that
  destination moved out from under it and the switch machinery was left without a home (the
  destination's own history is in the register; FR-026c is where it lives now). It is the
  general requirement it had always been in substance, and every existing reference to
  *"FR-026's labelled scenario switch"* resolves to it unchanged.

- **FR-026a**: Income credited to an **account in an international payment system** is
  **UNSETTLED** — Line 1 fails, Line 2 passes — and MUST be modelled as FR-026's labelled
  scenario switch, under the same rules: none of its figures labelled the tax owed, none
  blended with another. The source is not one position with two branches; it sets out **two
  competing positions plus a consequence**, so under Line 3 the switch holds **three**
  computed readings:
  - **the ДПС reading** (*«Стратегія 1»*) — income on the date funds reach the payment-system
    balance, charged at FR-007 to FR-009's components, base struck at that date's official
    rate;
  - **the НБУ reading** (*«Стратегія 2»*, resting on *«Положення … №5»*) — *«Датою отримання
    доходу вважається день зарахування коштів з Payoneer на ваш рахунок ФОП в українському
    банку»*: the same scheme and the same components, on a **different date**, which means a
    different official rate, a different base and possibly a different quarter;
  - **the non-repatriation reading** — personal income: the ПДФО of **FR-010a** and the levy
    of **FR-010**, the same two declarations every personal-income reading consumes, never a
    copy.

  ⚙ **The НБУ reading was treated as background colour until 2026-08-26, and that was the
  defect FR-026's third-reading clause exists to prevent, one destination over.** It is a
  declared scheme at a different date, so Line 3 computes it; and it is the **only one of the
  three carrying a numbered document**, which makes dropping it the worst of the three to
  drop.

  ⚙ **One departure from the source, and it is deliberate.** *«Стратегія 2»* computes the
  base as *«гривнева сума, що надійшла на рахунок за курсом банку на момент зарахування»*
  — the **bank's** rate. This specification MUST NOT follow that: a channel rate in a tax
  base is what **011's FR-013** categorically forbids, and what Principle VI's three roles
  exist to keep apart. (011's FR-012 forbids the converse — an official rate pricing a
  realised amount — and is not the prohibition invoked here; the two together are what
  keep the roles from meeting in either direction.) The reading is computed on its own
  **date** with the official rate for that date, per п. 292.5. The article's shortcut is a
  practitioner's convenience and the divergence MUST be stated on the figure, not silently
  absorbed — asserted by SC-017a, since a departure from a cited source is the last thing
  that should rest on prose.

  **A bank account outside Ukraine that is not a payment system is NOT this requirement's
  case**; it is FR-026d's, on its own sources. The only source here is about Payoneer —
  re-fetched 2026-08-25, the words *закордонн*, *Wise*, *за кордоном* and *рахунок за
  межами* appear zero times — and its central argument is that ДПС *«визнає Payoneer
  небанківською установою»*, which by construction says nothing about a foreign **bank**.
  ⚙ This requirement previously covered both, and the wider half had no source naming
  either candidate; narrowed 2026-08-25 to what the source supports.

  ⚙ **This verdict was changed by applying Line 2, and the change is the point of stating
  the lines.** This specification refused the payment-system destination outright, on the
  ground that a reading needs a pair of source-backed competitors before it can be UNSETTLED.
  That ground is not 009's. yankiv.com (29.09.2025) addresses this destination and sets out
  every reading the switch computes — *«датою отримання доходу ФОП є дата зарахування коштів
  на рахунок у системі Payoneer, а не на банківський рахунок в Україні»*, conditioned on
  *«щоб ці кошти вважалися доходом підприємця, їх необхідно перерахувати на український
  банківський рахунок ФОП (у форматі IBAN) до кінця звітного періоду»*, failing which
  *«вони оподатковуються як дохід фізичної особи за значно вищими ставками: 18% ПДФО та
  5% військового збору»* — and reports a ДПС/НБУ disagreement over it.

  ⚙ **What Line 1 is reading here**, since a flat *«the source cites nothing numbered»*
  would be false: the article **does** cite *«Положення … №5»* by number — but for the **НБУ
  counter-reading**, while the ДПС position a charge would rest on is reported as living in
  *«роз'ясненнях та індивідуальних податкових консультаціях (ІПК)»* with no number given for
  any of them. A number on the other side of a disagreement does not make this side
  checkable.

  ⚙ **What the three readings are readings *of*.** Not three constructions of one text: two
  authorities disagreeing about the date of income, plus the consequence of not repatriating,
  which is conditional on the owner's own conduct. ⚙ That conduct **may** be declared — it is
  an ordinary fact about the owner and declaring a fact presupposes nothing — but declaring
  it MUST NOT collapse the switch to one figure. That prohibition needs no argument of its
  own: Line 1 already forbids labelling any reading here the tax owed, because nothing
  numbers the position. ⚙ Trimmed 2026-08-26 from a claim that declaring the conduct would
  presuppose the disputed answer, which conflated declaring a fact with using it to select a
  treatment.
- **FR-026b**: Income credited to a **personal, non-ФОП account or card** is **UNSETTLED** —
  Line 1 fails, Line 2 passes — and MUST be modelled as FR-026's labelled scenario switch.
  Under Line 3 the switch holds **one** computed reading: **personal income**, the ПДФО of
  FR-010a plus FR-010's levy. The ФОП scheme is **not** a candidate here, because the one
  source that reaches this destination excludes it rather than contesting it:

  > *«Чи можна виводити кошти на особисту картку?»* — *«Категорично ні. Це призведе до
  > оподаткування доходу за сукупною ставкою 23% замість пільгових 6%.»*

  and, on the same page, *«кошти залишилися на Payoneer або виведені на особисту картку …
  оподатковуються як дохід фізичної особи за значно вищими ставками: 18% ПДФО та 5%
  військового збору»*. (The first is an FAQ heading and its answer, two blocks on the page,
  joined here and marked as such.)

  ⚙ **yankiv carries Line 2 here alone, and biz.ligazakon does not help.** That article's
  proposition is *«Дохід фізичної особи (не ФОП), який отриманий **від операцій з
  криптовалютою**, оподатковуються заставкою 18%+ військовим збором 1,5 %»* — a **taxpayer
  status** plus **crypto income**, not a crediting destination: `особист` and `вивед` return
  zero hits on the page and the only `карт` is site chrome. Neither half matches this row.
  «не ФОП» is a status, and FR-026b's owner **is** a ФОП whose money lands somewhere
  personal;
  the income is crypto, and this is contract income. Carrying the 18% into a personal-income
  reading remains the inference FR-010a and owner verification task 5 say it is — here as
  much as anywhere, and the reading is no better attached for this destination than for the
  others.

  ⚙ **A switch with one figure is what the criterion produces, and it says something.** There
  is nothing to contest, because the source that reaches the destination excludes the ФОП
  scheme; but it numbers nothing, so Line 1 refuses the figure the INTERPRETED level and it
  MUST NOT be labelled the tax owed. One labelled what-if is the honest shape of *the source
  is unambiguous and nobody can check it*.

  ⚙ Added 2026-08-26 out of FR-027's residual row, which was wrong on the criterion's own
  terms — its source names the destination in as many words, which not every row's does
  (register). `data/venues.toml` already declares `monobank_uah`
  and a stream already routes through it, so a personal card is a destination this model can
  name today; whether the owner would ever credit contract income there is his declaration
  to make and not this specification's assumption.

- **FR-026c**: Income credited to a **crypto-exchange account** is **UNSETTLED** — Line 1
  fails, Line 2 passes — and MUST be modelled as FR-026's labelled scenario switch. Under
  Line 3 the switch holds **one** computed reading: **personal income**, the ПДФО of FR-010a
  and the levy of FR-010. The ФОП scheme is **not** a candidate, because 7eminar excludes it
  in answer to a question that is this destination: *«Ні, не включаються … А оплата за
  послуги у криптовалюті не є доходом ФОП, а є доходом фізособи»* (see Sources).

  ⚙ **This destination was refused for one round, and the refusal was wrong for a reason
  worth keeping: nobody searched for a source, only re-read the four already cited.** Those
  four genuinely do not reach it — the reasoning is at FR-027, as the argument against
  re-deriving figures from them — but 7eminar does, and its question names the destination
  more exactly than any source behind any other row. *Nothing reaches it* is a claim about
  the world, not about a bibliography, and it cannot be established by re-reading the
  sources one already has. Dates: register.

  ⚙ Line 1 fails because the destination proposition carries **no number**. The three
  citations in the answer attach elsewhere — ЗІР 107.01.02 to selling crypto, ЗІР 104.08 to
  the general system's crypto bookkeeping, п. 168.2.1 / ЗІР 103.02 to the general
  declare-and-pay duty — and a number on a neighbouring proposition does not make this one
  checkable, exactly as at FR-026a.
- **FR-026d**: Income credited to a **bank account outside Ukraine** is **UNSETTLED** —
  Line 2 passes, and Line 1 is satisfied on the numbers but stopped by **both** of its
  qualifications: the documents are ІПК and a letter answering one taxpayer, and they point
  different ways. Under Line 3 the switch holds **two** computed readings, and it is the only
  switch here whose readings rest on documents this specification has **retrieved and read**
  rather than seen reported:
  - **personal income** — the ПДФО of FR-010a and the levy of FR-010 — the current ДПС
    position, stated in terms in **лист ДПСУ № 5064/Г/99-00-24-03-03-09 від 04.07.2022**
    (retrieved 2026-08-27, see Sources): *«якщо кошти, отримані від нерезидента на рахунок,
    підкритий у іноземному банку, не зараховані на рахунок для здійснення підприємницької
    діяльності у банку в Україні, то такі кошти не включаються до доходу фізичної особи –
    підприємця платника єдиного податку»*, taxed instead as *«іноземний дохід»* under
    п. 170.11 ст. 170, п. 164.4 ст. 164 and п. 16-1 підрозділу 10 розділу ХХ ПКУ. Conditional
    on the funds not being moved to a Ukrainian entrepreneurial account;
  - **the ФОП scheme at the credit date**, base at that date's official rate — the reading
    factor.academy argues for (*«такий фіскальний підхід неправомірний»*), resting on
    **ІПК № 100/ІПК/99-00-04-03-03-06 від 21.01.2022** (retrieved 2026-08-27), which answers
    a ФОП of the third group asking about *«дохід від своєї діяльності за договором про
    надання послуг, укладеним з нерезидентом»* credited to *«рахунок в іноземному банку»*.

  ⚙ **What this reading rests on, said where the reading is stated.** ІПК № 100/ІПК does not
  state the ФОП-scheme position — the ⚙ below records that reading its silence is
  factor.academy's inference. The table's Line 1 cell (*each answering one taxpayer and
  pointing the other way*) and this requirement's *rest on documents this specification has
  retrieved and read* are therefore exact on the personal-income side and one inference deep
  on this one. The verdict is unaffected: Line 1's first ground refuses INTERPRETED to both.
  Recorded 2026-08-27; closed by owner verification task 6.

  ⚙ **The two readings are not symmetrically supported, and saying so is the point of
  retrieving the documents.** № 5064/Г states its proposition in terms. ІПК № 100/ІПК does
  **not**: asked squarely whether such income is taxed with ПДФО, ВЗ and ЄСВ, it recites the
  єдиний-податок machinery — п. 291.4, п. 292.5, п. 292.6, п. 296.3 — and concludes only that
  a ФОП *«можуть здійснювати зовнішньоекономічну діяльність за умови дотримання вимог
  розділу XIV Кодексу»*, without applying ПДФО. factor.academy reads that silence as the
  earlier position; **the silence is real and the reading of it is factor's inference, not
  the document's words.** The same ІПК also states, on its Q1, that *«кошти за операціями
  суб'єктів господарювання - резидентів, зокрема, з експорту товарів (послуг), підлягають
  зарахуванню на рахунки резидентів у банках України»* — the very premise the later letter
  builds on, which makes *«a change of position»* a thinner description than it looked.

  ⚙ **One cited number does not check out, and it is removed.** factor.academy also cites
  **ІПК № 177/ІПК/99-00-04-01-04-06 від 27.01.2023** for the personal-income position. That
  number and date resolve, in the public ІПК register, to a consultation for a **Товариство
  про сплату земельного податку** — *«щодо сплати земельного податку»*, about a Kyiv council
  decision on land-tax rates. It has nothing to do with a ФОП or a foreign account. This
  specification carried it for one round on factor's word; it is struck, and the
  personal-income reading rests on № 5064/Г alone. ⚙ Worth the sentence because the defect
  is the one this branch has been hunting all along, arriving from a new direction: a
  **secondary source** mis-citing a primary one, inherited without checking.

  ⚙ **Why still UNSETTLED and not INTERPRETED on the stated side.** № 5064/Г is a letter
  answering one taxpayer and № 100/ІПК says in its own closing paragraph that a consultation
  *«може використовуватися виключно платником податків, якому надано таку консультацію»*.
  Neither binds this owner. Line 1's first qualification therefore applies: both readings are
  computable and citable, neither is the tax owed, and what would settle it is an ІПК of the
  owner's own — task 6.

  ⚙ **The provision reaches one of the two documents.** п. 52.2 ст. 52 ПКУ governs an
  індивідуальна податкова консультація; № 5064/Г is a лист in reply to one person's звернення
  and the provision does not name it. The ground stated for it here — that it answers one
  taxpayer — is a description of the document and carries no citation. The conclusion is
  unaffected, a лист binding this owner no more than someone else's ІПК does, but as of
  2026-08-27 that half of the ground is uncited, and it closes with a citation for the
  standing of a ДПС лист-роз'яснення.

  ⚙ It is the row that most sharpens FR-024a: the
  owner's routing origin is Deel and Deel is not a bank, so nothing reaches him through this
  row — but a reader who defaulted the crediting destination from `arrives_at` would land on
  it.
- **FR-027**: A stream naming this scheme with a destination that produces no computable
  reading MUST be refused as a typed result naming the destination and the scheme — never
  silently charged at these rates, and never silently charged at nothing. The refusal MUST
  name **which of three states** it is in, because they close differently and a refusal that
  named only the outcome would tell the owner nothing about what to do:
  - **no source reaches the destination** (Line 2 fails). Closes by finding a source.
  - **a source reaches it, but no row of the table records the judgement.** Closes by adding
    the row with its reasoning. The table is normative, so a destination it does not name is
    unresolved even where a source exists.
  - **a source reaches it, but no candidate is computable** (Line 3 leaves nothing). Closes
    by declaring the missing scheme with its rates cited. The refusal MUST name the
    uncomputable candidates, since a switch of zero figures is not a switch.

  ⚙ **No named destination is in any of the three states, and that is the honest position.**
  Every row of the table now resolves to a charge or a switch; FR-027 is reached only by a
  destination nobody has declared yet. Each state is reachable and each closes differently,
  and the requirement earns its place by being the thing that fires *instead of* an invented
  charge — but a reader should not be told it has worked cases when it has none. ⚙ The
  branch's record here is the argument for keeping it: this requirement swept in a
  destination two named readings covered, then rested on a test that could not fail, then
  claimed a case that was a counterfactual. A refusal level that never fires is cheap; one
  that fires wrongly is what those three rounds cost.

  ⚙ **Four of this feature's own sources do not reach the crypto-exchange destination**, and
  the reasoning is kept because it is what stops someone re-deriving figures from them once
  FR-026c's one figure looks thin:

  1. biz.ligazakon — *«ФОП на єдиному податку І-ІІІ групи використовувати криптовалюти **в
     розрахунках** не можна. **Наслідки**: примусове переведення на загальну систему
     оподаткування та сплата єдиного податку за штрафною ставкою - 15 %.»* Its antecedent is
     the ФОП **settling in crypto**. What is modelled is contract income in **dollars**
     credited to an account at a crypto exchange: `data/routes/deel_to_coinbase.toml`
     declares the leg `USD → USD` and `data/venues.toml` gives the venue
     `currencies = ["USD"]`. No crypto is used in the розрахунок, so the antecedent does not
     obtain — and **a consequence cannot reach a destination its antecedent does not**. The
     загальна система at 15% is that consequence, which is why it is not a candidate at
     FR-026c.
  2. The same article's *«Дохід фізичної особи (не ФОП), який отриманий **від операцій з
     криптовалютою**, оподатковуються заставкою 18%+ військовим збором 1,5 %»* mismatches
     twice, exactly as at FR-026b: the subject is a **non-ФОП** and the income is
     **crypto-operation** income, while this is a ФОП's contract income for services.
  3. forbes.ua reports the virtual-assets law of 17.02.2022 as a framework law and sets out
     the rates **one bill** proposed for profit on virtual-asset operations: *«Фізособи
     отримають пільгу для податку на прибуток на пʼять років. У цей період оподаткування
     прибутку від операцій із віртуальними активами буде 5% ПДФО +1,5%. Після пільгового
     періоду – 18%+1,5%.»* — a five-year preferential period and the rate after it, not two
     drafts. Proposed rates under a framework that does not exist are not a treatment of
     anything. ⚙ The proposition that the 17.02.2022 law produced **no operative tax
     framework** is **biz.ligazakon's**, not forbes's; this specification attributed it to
     forbes until 2026-08-27.
  4. yankiv.com's crypto article is about **законопроєкт 10225-д**, a draft: its *«На
     спрощеній системі оподаткування криптовалюта заборонена»* describes what a law that does
     not exist would do, and again turns on working *with* cryptocurrency. taxer.ua served
     only a JavaScript shell.

  ⚙ **What 7eminar's account-location premise does and does not carry.** Its answer states
  that a ФОП may take service payment *«лише у грошовій формі і лише на рахунки відкриті в
  українському банку»*, and the second limb is currency-agnostic on its face — it would
  reach a payment system and a foreign bank account as readily as a crypto exchange. This
  specification does **not** extend it, for three reasons stated so the judgement can be
  argued with. The answer's own chain runs entirely through crypto: the conclusion sentence
  invokes the monetary-form limb (*«А оплата за послуги **у криптовалюті** не є доходом
  ФОП»*), both ЗІР citations are crypto-specific, and the *«Тому»* follows the crypto
  paragraphs. The account-location limb carries **no citation of its own**. And it is
  contradicted by better-attested material now in hand: factor.academy records that *«в
  законодавстві України не існує і прямої заборони на отримання ФОП доходів на іноземний
  банківський рахунок»* and that ДПС's own ІПК № 100/ІПК від 21.01.2022 accepted ЄП taxation
  of exactly such income. ⚙ **That second clause is factor's reading of the ІПК and not the
  ІПК's words**, as FR-026d records; the mark does not travel with it here. Recorded
  2026-08-27. Extending an uncited premise from a crypto answer across numbered
  ДПС documents that engage the question directly would be the inference this branch has been
  caught making four times. ⚙ The premise that **does** recur across rows is not 7eminar's
  but **ДПС's repatriation condition** — *funds not moved to a Ukrainian entrepreneurial
  account are not taxed under entrepreneurial rules* — which appears numbered at FR-026d and
  unnumbered at FR-026a, and is the same shape in both.

### Key Entities

- **Tax regime (the taxation scheme)** — a declared, identified treatment an income stream
  can name: the set of components it charges, their dated schedules, its variant, and its
  reporting cadence. ФОП group 3, ФОП group 2 and a legal entity are three of them. The
  stream-side counterpart of feature 006's instrument tax classes; "regime" and "taxation
  scheme" are one entity under one name in this specification.
- **Regime component** — one separately named charge the scheme declares, with its own
  provenance. A **rate component** carries a dated rate schedule and applies to the base
  (єдиний податок, військовий збір); a **periodic component** carries a dated schedule of
  amounts and is owed per elapsed period (ЄСВ). What a scheme charges is exactly what it
  declares, and nothing in the engine knows any of these names.
- **Regime variant** — which of a regime's alternative rate sets applies (VAT payer or not).
  Declared per owner without a citation; the rates of every variant are curated and cited.
- **Tax treatment reference** — the field on an income stream naming its regime, replacing
  the retired scalar. Naming none is a permitted and meaningful state.
- **Credit-date base** — the record of the base being struck: the credited foreign amount,
  the credit date, the official rate applied and the resulting hryvnia figure (feature 011's
  conversion record, consumed unchanged).
- **Base-versus-received difference** — the reported gap between the hryvnia the base implies
  and the hryvnia the sale produced, labelled as outside the taxable base and signed in
  whichever direction it fell.
- **Crediting destination** — where the income is credited for tax purposes; the fact
  FR-025 to FR-027 read to select a **treatment**, never a route. Distinct from the stream's
  `arrives_at`, the **routing origin**; separately declared, neither defaulted from the
  other, for the reasons FR-024a gives. Which destinations exist and what each is worth is
  the table under "Legal grounding".
- **Unsettled-reading figure** — one what-if on an UNSETTLED destination's switch: the
  figure, the reading that produced it, that reading's citations, and the label saying it is
  not the tax owed. Feature 009's unsettled-law scenario switch, on this feature's question.
  ⚙ **Stale list, live rule.** FR-026c and FR-026d consume this one declaration too; the
  enumeration predates them. The governing form as of 2026-08-27 is FR-010's — *which
  readings those are is the table under "Legal grounding", not a list kept here* — and this
  sentence should carry no list at all.
- Reused unchanged: the income stream, cadence and deployable-capacity records of feature
  002; the tax charge and provenance records of feature 001; the dated rate schedule of
  feature 006; the official-rate series and conversion of feature 011; the routes, legs and
  channels of features 002 and 003.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A month's foreign-currency income charged under the regime produces a hryvnia
  base and two component charges that match independently hand-computed arithmetic within
  the single project tolerance, with the arithmetic recorded alongside the check. (FR-005,
  FR-007, FR-011)
- **SC-002**: The two components are separately named in 100% of outputs, each naming its
  own rate, cited source and verification date; no output anywhere reports a blended
  percentage; and no component name appears in source code as a branch. (FR-005, FR-006,
  FR-001)
- **SC-003**: A projection straddling 1 January 2025 charges 1% from it, matching a
  hand-computed worked example, and produces a typed error naming the component and the date
  for every month before it — in one run. No test passes by charging zero, and none passes
  by emitting a charge whose levy line is merely absent. (FR-008, US3) ⚙ This criterion
  previously asserted *no levy before it* and the typed error in one sentence, which is a
  contradiction: the levy component **is** declared for the owner's scheme, so a month its
  schedule does not reach is FR-008's error and FR-020's *declared, no amount in force*, not
  a scheme that charges nothing. US3 scenario 1 said the first and US3 scenario 2 the
  second; the requirements were always the argued half and they win.
- **SC-004**: A legislated change to either component is entered as one dated entry in a
  data file with zero source lines changed, and takes effect in the next run. (FR-007)
- **SC-005**: Every deployable-capacity behaviour feature 002 asserts still holds after the
  scalar is retired: the undeclared case yields a result with no net field, the reason names
  the missing declaration, and no net figure quietly equals a gross one. (FR-015, FR-016)
- **SC-006**: A stream naming an unknown treatment fails at load naming the file, the stream
  and the treatment; across a battery of broken regime files — negative rate, unordered
  schedule, duplicate effective date, duplicate regime id, unknown component field — every
  case names the file and the field and no case substitutes a default. (FR-017, and 006's
  FR-003)
- **SC-007**: No tax rate consumed by this feature appears in per-owner data, and every
  value in curated tax data carries source, retrieval date and verification date — checked
  by the provenance gate rather than by reading. Exactly one value is sourced to the owner's
  own statement rather than to a public text — the zero ЄСВ of FR-021 — and it is
  identifiable as such wherever it appears, marking every figure it touches. (FR-002,
  FR-003, FR-021)
- **SC-008**: With any rate or official-rate observation left unverified, 100% of charges
  derived from it carry the unverified mark, and no derived figure appears unmarked.
  (FR-003)
- **SC-009**: For one credited amount, the hryvnia received and the hryvnia base are two
  separately reported figures; recomputing with the sale executed at a different market
  rate leaves the base bit-identical; and the difference is reported with the
  not-part-of-the-base label on its face. (FR-012, FR-013)
- **SC-010**: Two schemes differing only in whether they charge a periodic component
  produce totals differing by exactly the declared amount on identical income, with zero
  source lines changed; the scheme that charges none reports that as a property of the
  declaration; a scheme declaring the component with no amount in force for a period refuses
  naming the period; and a period with zero income evaluates the periodic component
  regardless. (FR-019, FR-020, FR-021)
- **SC-011**: No representation anywhere in the system expresses a periodic component as a
  rate on income, and no nil is ambiguous between *this scheme charges no such component*,
  *this component was charged and came to nothing*, and *no amount is declared* — the three
  are distinguishable in the output in 100% of cases. (FR-019, FR-020, FR-021)
- **SC-012**: A second synthetic scheme with a different component set, different schedules
  and a periodic component the first does not have produces complete results with zero lines
  of source code changed. (FR-001, SC-002's no-branch clause)
- **SC-013**: A stream naming this scheme with a destination that produces no computable
  reading is refused as a typed result naming the destination and the scheme, in 100% of
  cases, and the refusal names the state it is in and what closes that state. **Two of
  FR-027's three states are exercised** by synthetic destinations, since no declared
  destination is in any of them: one nothing reaches, and one whose only candidate needs an
  undeclared scheme. A destination that resolves to a switch never produces a refusal.
  (FR-027)

  ⚙ **State 2 is deliberately not measured here, because the engine cannot reach it.** To
  report *a source reaches this destination but no row records the judgement* rather than
  *nothing reaches it*, the data would have to declare that a source exists for a destination
  the table does not name — and nothing in FR-024a, FR-026 or FR-027 declares such a fact,
  nor should this feature invent one to make a criterion testable. State 2 is a **reviewer's
  determination**, made when someone notices a source the table has not caught; the engine
  emits state 1 and the reviewer reclassifies it. FR-027 keeps all three because the closure
  paths differ for a human reader, and this criterion claims only the two a test can
  construct.
- **SC-013a**: A stream whose routing origin and crediting destination differ — the owner's
  own case, Deel and the ФОП account — is charged under FR-025 rather than refused, and a
  stream declaring only one of the two fails at load naming the missing field. No code path
  anywhere reads one as the other. (FR-024a)
- **SC-014**: The compulsory sale's cost is produced by the existing costing path with no
  new leg kind, channel kind or cost mechanism introduced; the return conversion appears
  only as the existing round-trip figure; and no output presents the sale's one-way cost as
  the whole cost. (FR-023, FR-024, required test G6)
- **SC-015**: `docs/METHODOLOGY.md` gains the scheme's charge formula, the periodic
  component's definition, and a worked example of each, in the same change that implements
  them — verified by that change's own diff. (constitution's documentation clause)
- **SC-016**: Income from a non-resident credited to the ФОП's foreign-currency account is
  recognised on the credit date and charged under this scheme, matching hand-computed
  arithmetic, with п. 292.6 and п. 292.5 ПКУ travelling on the figure; the base is the whole
  credited amount, with no bank commission deducted from it; and every other declared
  destination produces SC-017's switch instead of this charge rather than the same charge at
  a different address. (FR-025, FR-014, FR-026a to FR-026d)
- **SC-017**: An UNSETTLED destination produces **exactly one figure per computable
  reading** — three for a payment system, two for a bank account outside Ukraine, one each
  for a personal account and a crypto exchange — with every
  uncomputable candidate named on the switch and its reason given, so no switch can be
  read as complete when it is not. Each figure names its reading and carries that
  reading's citations; 0% of outputs label any figure the tax owed; and no output anywhere
  reports a number that combines two of them. Neither the count nor the ordering is a
  default, and the personal-income components are **one** declaration consumed by every
  reading that needs them rather than a copy per destination. ⚙ The criterion previously
  fixed the count at two, which dropped a computable reading at one destination and
  invented one at another; the blend and the tax-owed label were always the point, never
  the number. (FR-026, FR-026a, FR-026b, FR-026c, FR-026d, FR-010, FR-010a, Line 3)
- **SC-017a**: The НБУ reading of a payment-system destination reports, **on the figure**,
  that its base was struck at the official rate for its own date and **not** at the *«курс
  банку»* its source uses — naming both what the source says and what was computed instead,
  in 100% of outputs carrying that reading — and no configuration, flag or option produces a
  base for it from a channel rate, asserted as a property of the engine rather than of one
  call site. ⚙ Both halves are machine-checkable, deliberately: an earlier draft also asked
  that *no output present the reading as the source's own arithmetic*, which is true and
  necessary but is a reviewer's judgement rather than a test, and a criterion a test author
  cannot construct from its own sentence is a criterion that quietly does not get written.
  What replaces it is the two mechanical facts that make the judgement hold. ⚙ Pinned
  separately because it is the only place on this branch where the specification knowingly
  departs from a source it is citing, and it was the one prohibition in FR-026a that nothing
  exercised while its three siblings — not-the-tax-owed, no blend, one declaration — were all
  in SC-017. A departure nothing checks is a departure that becomes a silent absorption, and
  the constitution's ground for it (Principle VI's three roles, 011 FR-013) is exactly the
  kind of claim that has to be asserted rather than written down. (FR-026a, 011 FR-013)

## Assumptions

- **The owner's own facts are declarations, not observations.** That he is a ФОП of the
  third group, that he is not a VAT payer, that this is the scheme he is in — these are
  statements by the only person who can make them, declared as per-owner data with no
  citation, exactly as his salary is. Every **legal** value they select is curated and
  cited, with one marked exception: the zero ЄСВ of FR-021 is a curated value whose source
  is the owner's statement rather than a public text, and it says so on its face.
- **Retrieved is not verified.** Every rate, date and rule below the table above enters with
  its citation, its retrieval date (2026-08-23) and an empty verification date until the
  owner checks it against the primary text. The hand-computed worked examples run on
  clearly-labelled **synthetic** amounts, rates and dates, following the precedent of 001,
  006 and 007: they test the engine's arithmetic, not Ukrainian tax law.
- **The stream has no crediting-destination field yet.** Adding it is FR-024a's, which is
  also where the distinction from `arrives_at` is argued; until it exists this specification
  assumes a ФОП account venue and a declared crediting destination naming it. ⚙ A personal
  account as a curated venue follows the precedent already set by `monobank_uah` and
  `coinbase` in `data/venues.toml`; whether curated venues should eventually split per-owner
  is a Principle VII question this feature does not open.
- **Amounts remain the honest placeholder.** The declared stream amounts are zero because
  the owner's real monthly figures have not been stated (`SIMULATOR_SPEC.md` §11 item 3).
  This feature produces zero charges on zero income and does not invent a salary to make an
  example interesting; the examples use labelled synthetic amounts instead.
- **One scheme is the owner's.** UA, ФОП group 3, non-VAT. The second scheme of Story 6 is
  declarable and addressable, not consumed. The personal-income components the UNSETTLED
  readings declare are consumed *only* as labelled what-ifs and are never his treatment.
  Residency changes (required test E9) and multi-jurisdiction comparison (E8) are later
  features.
- **No payment timing, no filing.** Liabilities are recorded against their period. When they
  are paid, from what cash, and what happens when there is not enough, is feature 009 and
  required test E7.
- **No delivery surface.** As in every feature so far: results are produced and asserted by
  the test suite.

## Clarifications resolved

Six rows. The first four are design positions settled before the requirements were written
and argued in "Design positions this specification is built on" above rather than merely
asserted. The last two arrived as a single `[NEEDS CLARIFICATION]` covering three
destinations: separating them answered one, gave the second a shape, and left the third to
owner verification task 6. Which destination is worth what is the table under "Legal
grounding", which is where the verdicts live and where they have moved; nothing is counted
here.

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Is ЄСВ a tax rate with a zero value? | **No — a periodic component of a scheme.** Different trigger (a period elapsing, not income arriving) and different base (a statutory fixed amount, not a percentage). A rate-shaped model is wrong the first period income is zero. | FR-019, SC-011 |
| 2 | What makes the owner's ЄСВ nil? | **The scheme he is in, not an exemption** (owner correction, 2026-08-23, superseding the per-month conditional exemption this spec first carried). A taxation scheme — ФОП group 3, ФОП group 2, a legal entity — is a declared set of components, and his charges no ЄСВ — declared explicitly at zero so the nil is visible and marked rather than absent. Which scheme applies is a declaration, not a branch: Principle II. | Design position 2; FR-020, FR-021, US4, SC-010, SC-011 |
| 3 | Does `IncomeStream.income_tax_rate` survive? | **Retired.** A scalar cannot carry two components with different commencement dates, a fixed-amount obligation, or the choice of a whole scheme. The stream names a treatment, as 006's instruments name tax classes — the inconsistency 006 left behind. The relocation also moves legal rates out of uncited per-owner data, which sharpens Principle VII's boundary. | FR-002, FR-015…FR-018, SC-005, SC-007 |
| 4 | Which hryvnia figure is the taxable base? | **The credited dollars at the official rate on the credit date**, and the hryvnia the sale produces is a different number at a different rate on a different date. Both are reported; the gap is labelled as outside the base; nothing nets them. | FR-011…FR-014, SC-009 |
| 5 | What if the income is credited somewhere other than a plain hryvnia ФОП account? | **It depends on the destination, and two stated criteria decide which** rather than a judgement per case: the verdicts and their grounds are the table under "Legal grounding" and are not repeated here. Two things settled alongside them — the question is read against a **crediting destination** declared separately from the stream's routing origin (owner decision, 2026-08-25), and the owner's own case, routed through Deel and credited to the ФОП account, is INTERPRETED. | FR-024a, FR-025, FR-026, FR-026a to FR-026d, FR-027, FR-014, SC-013a, SC-016 |
| 6 | What if it is credited to a crypto exchange? | **UNSETTLED**, one computed reading — personal income (FR-026c). The four sources this feature already cited do not reach it, and FR-027 keeps that reasoning; a fifth, found on 2026-08-27, does — 7eminar's question *is* this destination. Its verdict history is in the register; the middle step was wrong for a reason worth keeping, that *nothing reaches it* was concluded from re-reading the sources in hand rather than from looking for one. | FR-026, FR-026c, SC-017 |

## Owner verification tasks

Six facts that were cited but not verified, or not obtainable at all. Each is recorded as a
task, never filled with a guess; the affected values carry empty verification dates and the
mark propagates until the owner closes them. **Two of the six change what the engine does**
and are marked *load-bearing* where they say so; the other four change a source or a
confidence, not a number.

1. **The owner's own reading of the primary Tax Code article for the 5% єдиний податок
   rate, and the one further statute that pins its exact commencement.** The article was
   found on 2026-08-25 and this task shrank accordingly. It is **підпункт 2 пункту 293.3
   статті 293 ПКУ** — *«5 відсотків доходу - у разі включення податку на додану вартість до
   складу єдиного податку»* — read in the consolidated Code at `2755-17/print`, which marks
   it *«{Підпункт 2 пункту 293.3 статті 293 із змінами, внесеними згідно із Законом
   № 909-VIII від 24.12.2015}»*. № 909-VIII's розділ I, пункт 81, підпункт 1 is the change
   itself — *«у підпункті 2 цифру і слово "4 відсотки" замінити цифрою і словом "5
   відсотків"»* — and its розділ II, пункт 1 commences it *«з дня набрання чинності Законом
   України "Про Державний бюджет України на 2016 рік", але не раніше 1 січня 2016 року»*,
   with three named exceptions — підпунктів 3 та 10 пункту 45, підпункту 2 пункту 52, and
   пункту 58 розділу I — none of which is пункт 81.

   So the 5% has stood in this wording since **at latest** the commencement of the 2016
   State Budget law and **at earliest** 1 January 2016; which of the two it is needs that
   budget law read, and that read is what remains of this task. It is **no longer
   load-bearing** for the owner's projections: either date precedes every period this
   feature can project, so FR-009's fallback — dating the entry from a secondary source's
   own publication date — is not the shape this entry takes. FR-009 keeps the fallback as a
   rule for the next uncited rate, not as a description of this one.
2. **The legal ground for a ФОП group 3 scheme carrying no ЄСВ.** The owner states this is
   his position (2026-08-23), and until a public text is cited for it the component is
   declared at zero with his statement as its source and an empty verification date, marking
   every figure that rests on it. Closing this task replaces the source; it changes no
   number (FR-020, FR-021, SC-007).
3. **Whether any deduction reduces the base under this scheme.** The bank commission is
   answered at INTERPRETED level — the income is the whole invoice amount including it
   (FR-014) — and every other candidate deduction is open. A cited answer either way closes
   it.
4. **The owner's own reading of the consolidated Податковий кодекс for пункт 16-1
   підрозділу 10 розділу ХХ.** This task asked whether a third law neither 4015-IX nor
   4113-IX records had moved anything. It has been answered on 2026-08-25 against
   `2755-17/print`, станом на 24.08.2026, and the answer is: **the third law exists and it
   moved only the sunset** — Закон № 4835-IX від 07.04.2026, whose two changes are quoted in
   "One rate, three laws, and an end nobody can put a date on". The **1% for group 3 and the
   1 January 2025 commencement are unchanged** in the consolidated text. What is left of the
   task is the owner reading that text himself: retrieved is not verified, and the sunset
   FR-008a records entered this specification on the strength of one automated retrieval.
5. **The primary Tax Code article for the 18% ПДФО of FR-010a, the date it took effect,
   and the inference the rate rests on.** *Load-bearing.* The rate is cited to one
   practitioner article that states it for a фізична особа **не ФОП** *«від операцій з
   криптовалютою»* and says something different about a ФОП; carrying it into a
   personal-income reading is an inference this specification states rather than a
   proposition the source makes, and the task is to close both halves. The inference is
   the same size at **every** destination whose switch consumes FR-010a — the article
   names no destination at all — so closing it moves every one of them. The *readings* are
   UNSETTLED and no verification closes that, but the rate inside them is an ordinary
   legal value: it labels no figure the tax owed, and it sizes the gap between readings,
   which is the only reason they are all computed.
6. **An індивідуальна податкова консультація (ст. 52 ПКУ) for each UNSETTLED crediting
   destination.** *Load-bearing.* Four destinations are UNSETTLED and every one of them is
   UNSETTLED for a Line 1 reason — no numbered document, or two that contradict each other —
   so all four close the same way, with a numbered ДПС position the owner obtains for
   himself. That is 009's standing resolution path, and it is one task rather than four
   because the shape and the remedy are identical; what differs is only which document is
   missing:
   - **an international payment system** (FR-026a) — ДПС's position is reported as living in
     *«роз'ясненнях та індивідуальних податкових консультаціях»* with no number given.
     ⚙ Cross-reference worth following before requesting one: **лист ДПСУ № 5064/Г**,
     retrieved at FR-026d, states the same repatriation condition for a foreign **bank**
     account, and whether it reaches a non-bank payment system is exactly what ДПС
     distinguishes when it calls Payoneer a *«небанківська установа»*.
   - **a personal, non-ФОП account or card** (FR-026b) — yankiv numbers nothing behind
     *«Категорично ні»*. The cheapest of the four: nothing about the substance is disputed.
   - **a crypto-exchange account** (FR-026c) — 7eminar numbers nothing on the destination
     proposition.
   - **a bank account outside Ukraine** (FR-026d) — here two ДПС documents were retrieved
     and they point different ways, and neither binds this owner, so what is needed is not a
     first number but one addressed to him. ⚙ A third document factor.academy cited for this
     row, ІПК № 177/ІПК, was retrieved and is about земельний податок; it is struck, and
     FR-026d records why.

   Closing any of them turns that destination's switch into a single INTERPRETED charge and
   changes nothing else. ⚙ Written as one task with four items rather than four tasks of one
   shape, which would be four counts to keep in step for one remedy.

**Recorded context, not on the critical path.** The **statutory ЄСВ monthly
minimum-contribution amounts and their effective dates** were load-bearing under the
superseded design and are not now: no scheme declared here charges the component, and one
that declared it without them would refuse under FR-021. They were never supplied and are
not guessable, so they stay recorded rather than sought.

**Every UNSETTLED destination has a task, which was not true for a day.** This section once
said of the crypto-exchange destination that no task could close it, because *«a verification
task presupposes something to verify»*. That was an inference from a bibliography: a source
addressing the destination existed and had not been looked for. Task 6 covers it with the
other three.

## Required tests this feature relates to

- **E10** (*a rate declared as a dated schedule changes on its effective date*) is closed by
  feature 006 on instrument tax classes. This feature is the first to exercise the same
  mechanism on **income**, against a real statute with a real commencement date, and the
  landing change should record that second exercise beside the row rather than re-flipping
  it.
- **E8** (*the same scenario under jurisdiction A vs B differs only in the tax terms*) is
  **not closed**: only one regime is consumed. Story 6 and SC-012 are its structural
  prerequisite — proving a second regime is a data-only addition — and the row stays
  unflipped.
- **E7** (*tax paid from cash in the following tax year*) is **not closed** and is not
  attempted; FR-004 declares the cadence 009 will need and stops there.
- **F1** is **not** closed by this feature either, and the reason is worth stating because
  it is easy to assume otherwise. F1 is about a *position* flat in USD across a devaluation
  posting a taxable UAH gain. What this feature produces is a different asymmetry: a base
  fixed at the credit-date official rate against hryvnia received at a market rate on the
  sale date, with no holding period and no cost basis anywhere in it. Both come from the
  same conflation this project exists to refuse, and they are not the same test.
- **E4** (*the crypto scenarios `current_practice`, `draft_18_5`, `draft_transitional_5_5`
  produce three different hand-checkable results from identical market data*) is **not
  closed**, and the resemblance to this feature's crypto material is worth naming so
  nobody flips the row. E4 is about disposing of a crypto **asset** under a regime that
  does not exist yet; this feature's question is where contract **income** is credited,
  and its crypto-exchange destination is a switch of one personal-income figure (FR-026c).
  The two never met: E4's `draft_18_5` is draft 10225-д's rates on an asset
  disposal, and the 18% + 5% declared here is FR-010a plus FR-010 on income — the same
  numbers from different places, which FR-026's lineage note exists to keep apart.
- Per the constitution, every behaviour above lands with a hand-computed worked example
  (SC-001, SC-003, SC-016), load-failure coverage (SC-006), refusal coverage (SC-010,
  SC-013), and propagation checks (SC-008). SC-002's no-branch clause and SC-012's data-only
  claim are `contract` tests, being compliance statements about Principle II; SC-017's
  never-blended and never-the-tax-owed clauses are the same shape for Principle I.

## Out of scope

Named explicitly so the plan does not drift into them: funding-route modelling of any kind,
which features 002, 003 and 004 own (FR-022); any new leg kind, channel kind or cost
mechanism for the compulsory sale (FR-023); the official-rate machinery itself, which is
feature 011 and is consumed here unchanged; correcting `data/streams/owner-001.toml`'s
`arrives_at`, which needs no correction — it is the routing origin and it is right (FR-024a
adds the crediting destination beside it, and that field is in scope); the owner's real
income amounts; payment timing, filing deadlines, declarations and the cash movement that
settles a liability (feature 009, required test E7);
loss carryforward; a second jurisdiction or a residency change (E8, E9); the VAT-payer
variant's rate, which is not cited and is not entered; the general system and the other ФОП
groups beyond being declarable; employment income as a modelled stream, and the
ordinary-personal-income levy schedule such a stream would need (FR-010) — distinct from
the personal-income components every UNSETTLED reading shares for its own what-if (FR-010,
FR-010a — which readings those are is the table under "Legal grounding", not a list kept
here); the crypto **asset** tax scenarios of required test E4, which are a different
question from the crediting-destination one; the display-currency switch;
the decision layer and candidate generation; and the web and command-line interfaces.

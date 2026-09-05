# Contract: the objective set, as declared

**Feature**: `019-decision-layer` | **Files**: `data/objectives/<owner>.toml`,
`data/questions/<id>.toml`

## The owner's own set (CL-1, CL-2)

```toml
# data/objectives/owner-001.toml
[owner]
id = "owner-001"

[objective_set]
id = "money-and-when"

  # More money that reaches a spendable endpoint by the horizon's end is better.
  # The band is 0.01 % OF THE QUESTION'S AMOUNT, stored as a fraction: 0.0001, not 0.01.
  [[objective_set.objective]]
  criterion = "money_at_the_endpoint"
  direction = "more_is_better"

    [objective_set.objective.band]
    fraction_of_the_question_amount = 0.0001

  # Sooner is better, which on a date is `less_is_better` -- the vocabulary is two tokens
  # and has no per-criterion synonym. A percentage of a date means nothing, so the band is
  # a count of days.
  [[objective_set.objective]]
  criterion = "all_money_back_on"
  direction = "less_is_better"

    [objective_set.objective.band]
    days = 7
```

The absolute money shape, legal beside the fraction (FR-011d):

```toml
    [objective_set.objective.band]
    amount   = 5.0
    currency = "UAH"
```

## The question names one set

```toml
# data/questions/fifty-thousand.toml
[question]
benchmark  = "UA4000231195"
objectives = "money-and-when"
```

Required, no default. A question naming none refuses at load naming the file and the field; one
naming a set the registry does not declare refuses in `resolver.check_question` (FR-001a).

## What refuses at load (FR-001, FR-002, FR-011b, FR-011d, SC-003)

One assertion per case in `tests/contract/test_objective_declaration_loading.py`.

| Case | Names |
|---|---|
| `data/objectives/` empty | the directory, and that there is no default |
| two files declaring one set id | both files and the id |
| a criterion outside the closed set | the file, the field, and the criteria that exist |
| an objective with no direction | the file and the field |
| an objective with no band | the file and the field |
| a band that is negative, zero or non-finite | the file, the field, and why zero is refused |
| `fraction_of_the_question_amount` on a **date** criterion | the criterion and the shapes it takes |
| `days` that is not a whole number | the field |
| a money band that is neither an amount-with-currency nor a fraction | the criterion and the shapes it takes |
| an unknown field anywhere | the file and the field (`extra="forbid"`) |
| `owner_id` not the streams' owner | the file and the field |
| a question with no `objectives` | the file and the field |
| a question naming an undeclared set | the question file, the field, and the sets that exist |

**Deliberately not here**: FR-011c's acyclicity floor. A declaration file does not carry the
figures the slack depends on, and a load-time check written against the bare constant would pass a
band five orders of magnitude too small. Its criterion is SC-004's and SC-007's.

**No citation keys** (FR-004). `data/objectives/` is already in `check_provenance.py`'s
`EXEMPT_DIRS` with its reason: a stated preference is not an observation. If a number describing
the world is ever needed here it moves to a sourced directory rather than the exemption widening.

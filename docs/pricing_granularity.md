# The pricing atom: choosing the right granularity for valuation

The single most important modeling decision is: **what is the unit you price?**
Too coarse and you average different markets into a meaningless number (a
$40k champagne Daytona and a $71k green "John Mayer" become one "116508").
Too fine and every unit has one sale and nothing is estimable. This document
sets the principle and shows what our data actually supports.

## The principle: identity vs. configuration

Every price-relevant attribute is exactly one of two kinds.

**IDENTITY** — factory-fixed, immutable, market-distinct. It defines the atom
and can *split* it into finer atoms:

- case **material** (steel / two-tone / gold / platinum / titanium / ceramic)
- **dial** (color/finish)
- **bezel** (material/color)
- case **size**
- **movement generation**

**CONFIGURATION** — the state of a specific example. It never splits the atom;
it is a pooled hedonic multiplier applied on top of the atom's value:

- **condition** (unworn / excellent / good / fair)
- **completeness** — box & papers / full set (~+13% in our data)
- **bracelet vs strap** where swappable (~+15% for a jubilee in our data)
- minor **age** effects

The reference number is a *proxy* for the identity signature — a good one,
because for modern watches material/bezel/size are usually baked into the
reference (116508 YG vs 116509 WG vs 116500LN steel are different references).
It fails in exactly two places, which is where the real modeling work is.

## Where the reference is not enough

### 1. One reference, several dials → split by dial
A single reference sold with materially different dials that trade apart. The
atom is `reference × dial` (116508 Green vs Champagne vs Black). Material is
inherited from the reference; the dial is the live split dimension.

**Dial splits are data-thin and need a prior.** 116508 has ~10 dial-labeled
sales total — not enough for two ≥5 groups to pass a rank test. So the John
Mayer split is justified by a *domain prior* (a known, large, structural price
gap) and confirmed as volume accumulates. You cannot purely data-drive sparse
variant splits; you need knowledge + data, not data alone.

### 2. Unmatched listings (~60%) → split by material, then size
When a listing resolves only to a family (no reference), the reference can't
carry material or size — but the title often can. Here the atom is
`family × material × size-band`, and this is where the data is *dense*:

| Datejust (family-level, sold) | n | median |
|---|---|---|
| steel | 108 | $11,806 |
| two-tone | 41 | $15,293 |
| rose gold | 4 | $19,451 |

Material moves price +30–65% with real sample sizes — the dominant,
data-supported split. Size is secondary but real (steel Datejust: 41mm
$11,985 vs 36mm $10,799).

## Adaptive granularity: split only where the data supports it

The rule the engine enforces:

> Create a finer atom along an identity attribute **only when** each candidate
> sub-group clears a density floor **and** the price gap is real. Otherwise
> keep the attribute aggregated and let a hedonic carry it.

Concretely, in `valuation.py`:

- **Material** always defines the family-generic atom (it is dense everywhere
  and the biggest driver).
- **Size** splits a `(family, material)` atom into a `(family, material,
  size-band)` atom **only when that cell has ≥ 15 sales**; below that, size
  folds back into the material atom. A size sub-atom's offset is shrunk toward
  its `(family, material)` parent (empirical-Bayes), so a thin size band leans
  on its material parent instead of its own noise.
- **Dial** splits a reference via the curated variant catalog (the prior),
  and `taxonomy.analyze_reference_granularity` audits those splits against the
  data (a rank test on dial groups), flagging both catalog splits the data now
  confirms and any the data suggests we are missing.

Size bands (coarse, so each has density): `sub34`, `34-37`, `38-41`, `42+`.

## What the data currently splits (18 dense size atoms)

Real size markets the engine now prices separately (same family+material):

- Seamaster 300M steel: **42+ $5,431 · 38-41 $3,699 · 34-37 $2,668**
- Pasha steel: **38-41 $3,361 · 34-37 $2,540**
- Ballon Bleu steel: **42+ $5,794 · sub34 $4,910**
- Santos / Tank sub34 (ladies') priced as their own market
- Sky-Dweller 42+, GMT-Master II 38-41, Submariner 38-41, …

## The hierarchy (coarse → fine; each level shrinks toward its parent)

```
family                                   ← trend lives here (shared)
├── reference            (material fixed by ref)
│    └── reference × dial variant         ← prior + accumulating data
└── family × material                     ← dense, dominant split
     └── family × material × size-band    ← adaptive; only where dense
CONFIG (never a split): condition · full set · bracelet → hedonic multipliers
```

The family trend is shared down the whole tree; each atom carries only its
offset (level) from the family base, shrunk toward its parent when thin. That
is what lets a 3-sale variant have a trustworthy value: it borrows the
family's trend and estimates only one number of its own.

## Why not just split everything finely?

Because value = (level offset) + (shared trend) + noise, and a finely-split
atom with 1–2 sales has a noisy offset and no trend of its own. Splitting past
the density floor trades a real bias (mixing markets) for a larger variance
(noisy per-atom estimates) — and below the floor the variance wins. The
adaptive rule sits exactly at that bias/variance frontier: split where the
gap is real and the data is there; pool and hedonic-adjust otherwise.

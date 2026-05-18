---
title: "Why not only OptimalBinning"
description: "An honest explanation of where OptimalBinning is already strong and where RiskBands adds the decision layer credit teams need under temporal stress."
---

## Start with the honest point

`OptimalBinning` already solves the static cutting problem very well.

RiskBands does not need to deny that. On the contrary: in the current
repository, the numeric supervised strategy uses `optbinning.OptimalBinning` in
the backend.

This means the correct message is not:

- "RiskBands completely replaces OptimalBinning"

The correct message is:

- "RiskBands reuses a strong static cut when it makes sense and adds the layers needed for credit selection under temporal stress"

## What static search does not answer by itself

Static search is excellent for questions such as:

- where are the best aggregate cuts?
- how can static separation be maximized?

But credit teams also need to answer questions such as:

- does ordering between bins survive by vintage?
- where does the event rate cross over time?
- which bins lose coverage?
- are we accepting a candidate with hidden structural fragility?
- if two candidates are plausible, which one has the more defensible rationale?

## What RiskBands adds on top

| Layer | Role |
| --- | --- |
| Temporal diagnostics | Look beyond aggregate separation |
| Structural penalties | Penalize fragile bins, low coverage, reversals, and volatility |
| Candidate comparison | Put static, temporal, and balanced candidates on the same scale |
| Auditable rationale | Explain why a candidate won in terms closer to the business |
| Credit-oriented score | Balance discrimination with temporal defensibility |

## An honest comparison

<div class="rb-grid rb-grid--2">
  <div class="rb-card rb-card--positive">
    <span class="rb-kicker">When static remains enough</span>
    <p>
      If behavior by vintage remains coherent and the structure does not lose
      coverage, RiskBands can simply confirm the static winner.
    </p>
  </div>
  <div class="rb-card rb-card--warn">
    <span class="rb-kicker">When the static answer is not enough</span>
    <p>
      If vintage reading reveals crossings, rare bins, or loss of coherence,
      maximizing only IV stops being a comfortable answer for credit.
    </p>
  </div>
</div>

## Where Optuna fits, without exaggeration

The project can also use `Optuna` as an optional search layer in supervised
flows.

This point matters, but it should not be confused with the main RiskBands
thesis.

Optuna enters to explore configurations when that makes sense. The real
differentiator remains the scale used to judge candidates:

- separation
- temporal stability
- coverage
- reversals
- structural fragility
- auditable objective score

## Why this matters in PD

In credit, the practical decision is rarely:

- "what is the best set of static cuts from a mathematical point of view?"

It is usually closer to:

- "what is the best set of cuts that I can still defend when the portfolio changes over time?"

RiskBands was designed to occupy that space.

<figure class="rb-figure rb-figure--wide rb-figure--medium">
  <iframe
    src="../../../benchmark-assets/temporal_reversal_aggregate_vs_vintage.html"
    title="Aggregate versus vintage reading in the benchmark"
    loading="lazy"
  ></iframe>
  <figcaption>
    This visual helps answer directly why the problem does not end with the
    static cut: the aggregate can remain competitive while the vintage view
    reveals loss of coherence.
  </figcaption>
</figure>

## Related pages

- [Why RiskBands](../why-riskbands/)
- [Temporal robustness in credit risk](../temporal-robustness-in-credit-risk/)

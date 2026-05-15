# PPO / GRPO / DAPO Clipping Card

Use this when the interview touches PPO, GRPO, DAPO Clip High, clip ratio, entropy, or exploration.

## Core Formula

For a sampled token/action with advantage `A_t`:

```tex
r_t(\theta) = \frac{\pi_\theta(a_t \mid s_t)}{\pi_{\theta_{\text{old}}}(a_t \mid s_t)}
```

```tex
L_{\text{clip}}(\theta) =
\mathbb{E}_t\left[
\min\left(
r_t(\theta) A_t,
\operatorname{clip}(r_t(\theta), 1-\epsilon_{\text{low}}, 1+\epsilon_{\text{high}})A_t
\right)
\right]
```

## Interview-Safe Explanation

- For positive advantage, increasing the action probability is useful until the upper clip boundary stops giving extra gain.
- Raising `epsilon_high` relaxes that upper boundary, so positively rewarded tokens/actions can receive a larger update before clipping.
- This is not the same as directly adding entropy. It may help exploration indirectly in long-horizon tasks because rare but valuable actions are less prematurely capped.
- Whether exploration is actually preserved must be checked with entropy, response diversity, low-prob action update statistics, invalid-action rate, and task success.

## Common Pitfalls

- Do not say Clip High directly "keeps low-probability tokens" without explaining the ratio and advantage condition.
- Do not mix absolute probability changes with relative ratio changes.
- Do not ignore negative advantage: lower clip behavior matters for suppressing bad actions.

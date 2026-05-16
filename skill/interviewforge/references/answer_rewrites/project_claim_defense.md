# Project Claim Defense Template

Use this for resume/project questions.

## Shape

1. claim: one sentence on what the project solves.
2. mechanism: implementation details the candidate can defend.
3. evidence: metric, ablation, case, code path, or observed behavior.
4. limitation: one honest caveat.
5. follow-up answer: how to expand if pressed.

## Template

```text
我这块主要解决的是 <problem>。具体做法不是只做 prompt，而是 <implementation mechanism>。
我负责/深度参与了 <owned components>，指标上 <metric/evidence>。
它的限制是 <limitation>，所以我们又做了 <ablation/debug/check> 来确认不是偶然提升。
如果继续做，我会优先补 <next experiment or engineering fix>。
```

## Strong Follow-Up Pattern

- "这里我可以从训练流程讲：rollout 怎么来、teacher logp 怎么算、loss 怎么进、梯度流怎么处理。"
- "这里我可以从实验设计讲：baseline 控制什么变量、checkpoint 怎么选、曲线和表格如何对应。"
- "这里我可以从失败 case 讲：哪些任务掉了、reward/entropy/length/invalid action 哪个指标先异常。"

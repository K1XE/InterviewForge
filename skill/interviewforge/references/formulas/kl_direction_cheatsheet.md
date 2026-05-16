# KL Direction Cheatsheet

Always state the direction explicitly.

## Definitions

```tex
D_{\mathrm{KL}}(p \| q) = \mathbb{E}_{x \sim p}\left[\log \frac{p(x)}{q(x)}\right]
```

If `p = pi_student` and `q = pi_teacher`, then:

```tex
D_{\mathrm{KL}}(\pi_{\text{student}} \| \pi_{\text{teacher}})
```

penalizes student probability mass where the teacher assigns low probability.

If `p = pi_teacher` and `q = pi_student`, then:

```tex
D_{\mathrm{KL}}(\pi_{\text{teacher}} \| \pi_{\text{student}})
```

pushes the student to cover teacher-supported modes.

## Interview-Safe Rules

- Use `KL(pi_actor/current || pi_ref)` when discussing the usual RLHF policy-to-reference penalty unless the implementation says otherwise.
- In teacher/student distillation, first define which distribution is sampled and which is the target.
- Avoid saying only "forward KL" or "reverse KL" without naming the two distributions.
- Be careful with mode-seeking and mean-seeking labels; they depend on which distribution is on the left side.

## Strong Answer Pattern

"这里我先把方向说清楚：我指的是 `KL(student || teacher)`，也就是用 student 当前分布作为左侧分布，惩罚它把概率放到 teacher 认为不合理的区域。这个说法和 `KL(teacher || student)` 不一样，后者更像要求 student 覆盖 teacher 的高概率区域。"

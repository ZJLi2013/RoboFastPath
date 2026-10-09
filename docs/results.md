# RoboJEV pick-and-place result

Predicate-first co-design completed 9/10 preregistered episodes with
Decision-1.0-Nox-4B. The exact-code control completed 10/10. This establishes
that the interface can support the task, while also showing that the model is
not needed for predicates directly available in simulator state.

## Frozen comparison

| Condition | Seeds | Success | Decision owner |
|---|---|---:|---|
| Native RoboJEV `Choice` + Nox | 0–9 | 0/10 | Nox selects intent and motor choices |
| Exact code predicates | 2000–2009 | 10/10 | Code reads all eight predicates |
| Seven Nox predicates + one code predicate | 2000–2009 | 9/10 | Nox judges direct fields; code computes withdrawal height |

Both predicate conditions use the same intent table, deterministic action
mapping, controller, and physical evaluator. The mixed condition has no
rule-answer fallback. Code computes `withdraw_clear` because it requires
subtracting cube height from TCP height; Nox misclassified every negative
example when this predicate was assigned to the model.

## Failure localization

The mixed failure occurred on seed 2000 at the transition from approach to
grasp. From decision 84 onward, all three grasp directions were `zero`, so the
exact predicate was true. Nox returned false for `grasp_ready` 113 times and
crossed the 0.5 threshold only twice. Each transient grasp was followed by an
approach decision that reopened the gripper.

Four successful mixed episodes showed the same weaker behavior at lower
severity: uncertainty delayed grasp by 3–14 decisions before the predicate
recovered.

## Interpretation boundary

- The result supports separating bounded model judgments from deterministic
  composition and execution.
- It does not show an advantage over code; code is exact, faster, and 10/10.
- Nox consumes privileged structured state rather than perception.
- Ten seeds are sufficient to expose the failure mode, not to estimate a
  production success rate precisely.
- Reproduction on other runtimes and hardware must report the pinned model,
  endpoint implementation, thresholds, and all failed episodes.

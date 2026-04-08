"""
fan_out/convergence.py — Convergence matrix computation for fan-out verdicts.

Field-by-field comparison of structured VerdictModel outputs.
Only compares categorical fields (decision) and confidence band (+-0.15).
Does NOT compare prose fields (rationale, conditions) — Pitfall 4.

D-19, D-20, D-21, D-22.
"""

from judgment.pass_ import VerdictModel


def compute_convergence(verdicts: list[VerdictModel]) -> tuple[str, dict]:
    """Compare n VerdictModel outputs and return (verdict_state, convergence_matrix).

    verdict_state: "converged" | "diverged" | "partial"
    convergence_matrix: {field: {"values": [...], "converged": bool}}

    Fields compared:
      decision  -- categorical exact match (D-19)
      confidence -- within +-0.15 spread (D-19, research threshold)

    Prose fields (rationale, conditions) are NOT compared -- high false-positive rate (Pitfall 4).
    """
    if not verdicts:
        raise ValueError("compute_convergence requires at least 1 verdict")

    fields = ["decision", "confidence"]
    matrix: dict = {}
    all_agree = True
    any_agree = False

    for field in fields:
        values = [getattr(v, field) for v in verdicts]
        if field == "confidence":
            spread = max(values) - min(values)
            agrees = spread <= 0.15
        else:
            agrees = len(set(values)) == 1  # exact match for categorical fields
        matrix[field] = {"values": values, "converged": agrees}
        if agrees:
            any_agree = True
        else:
            all_agree = False

    if all_agree:
        return "converged", matrix
    elif any_agree:
        return "partial", matrix
    else:
        return "diverged", matrix

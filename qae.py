"""Amplitude-estimation circuits and estimators.

A  = load the binned flood distribution on n qubits, then flip an objective qubit iff
     bin >= threshold (integer comparator, n-1 ancillas). P(objective = 1) = a = tail probability.
Q  = A S0 A^dagger S_chi (Grover operator). After Q^m A, P(objective = 1) = sin^2((2m+1) theta),
     a = sin^2(theta).

Query accounting: one application of A (or A^dagger) is one oracle query, the same unit as
one classical Monte Carlo draw from the distribution. A shot of Q^m A costs 2m+1 queries.

MLAE (Suzuki et al. 2020, maximum-likelihood amplitude estimation): run Q^m A for
m in {0, 1, 2, 4, ..., 2^(K-1)}, N shots each, and maximize the joint binomial likelihood
over theta. No QPE, no controlled-Q, so it is the shallowest-width QAE variant.
"""

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import IntegerComparatorGate, StatePreparation, grover_operator
from qiskit_aer import AerSimulator
from scipy.optimize import minimize_scalar


def state_prep(probs: np.ndarray, threshold_bin: int) -> QuantumCircuit:
    n = int(np.log2(len(probs)))
    # n-1 idle clean qubits let the comparator synthesize as a ripple of Toffolis (~44 CZ at n=5)
    # instead of ancilla-free multi-controlled X's (~1040 CZ). Ancillas are returned to |0>.
    qc = QuantumCircuit(2 * n, name="A", metadata={"obj": n})
    qc.append(StatePreparation(np.sqrt(probs)), range(n))
    qc.append(IntegerComparatorGate(n, threshold_bin, geq=True), range(n + 1))
    return qc


def grover(a_circ: QuantumCircuit) -> QuantumCircuit:
    obj = a_circ.metadata["obj"]
    oracle = QuantumCircuit(a_circ.num_qubits)
    oracle.z(obj)
    return grover_operator(oracle, state_preparation=a_circ, reflection_qubits=list(range(obj + 1)))


def circuit(a_circ: QuantumCircuit, q_circ: QuantumCircuit, m: int) -> QuantumCircuit:
    qc = a_circ.copy()
    for _ in range(m):
        qc.compose(q_circ, inplace=True)
    return qc


def schedule(k: int) -> list[int]:
    return [0] + [2**j for j in range(k - 1)]


def exact_hit_probs(a_circ: QuantumCircuit, q_circ: QuantumCircuit, ms: list[int]) -> np.ndarray:
    """P(objective = 1) after Q^m A for each m, exact to double precision: one circuit (A then
    Q repeated up to max(ms), with a save_probabilities checkpoint spliced in at every m) run
    once on Aer's statevector backend. Earlier attempts and why they're not used here:
      - Operator(Q) as a dense 2**n x 2**n matrix: O(4**n) memory, impossible past ~n=12
        (the compound joint circuit uses ~17).
      - qiskit.quantum_info.Statevector.evolve(q_circ) gate-by-gate in pure Python: exact and
        low memory, but its per-gate dispatch overhead makes even one Q application on a
        17-qubit, ~4500-gate circuit take ~50s -- Aer's C++ simulator does the same exact
        linear-algebra for about 3 orders of magnitude less wall time.
      - transpile(q_circ, basis_gates=["cx", "u"]) on Q in isolation, then composing the
        flattened piece repeatedly: fast, but WRONG for this circuit -- confirmed by comparing
        against the closed-form sin^2 law, basis_translator silently changes Q's action when
        it flattens grover_operator's definition out of the context it was built in. Composing
        the ORIGINAL (un-flattened) gates first and decomposing the whole assembled circuit
        once, afterward, is the version that matches the law to ~1e-13.
    `.decompose()`, not `transpile(..., basis_gates=...)`, is used to flatten: Aer's
    save_probabilities is a native instruction with no `.definition`, so decompose() passes it
    through untouched, while basis_translator rejects it outright (it's in neither the target
    basis nor the equivalence library)."""
    obj = a_circ.metadata["obj"]
    qc, cur = a_circ.copy(), 0
    qc.save_probabilities(qubits=[obj], label="m0")
    for m in sorted(set(ms)):
        if m == 0:
            continue
        for _ in range(m - cur):
            qc.compose(q_circ, inplace=True)
        cur = m
        qc.save_probabilities(qubits=[obj], label=f"m{m}")
    flat = qc.decompose(reps=6)  # deep enough to clear every high-level op down to {u, cx, p, r}
    data = AerSimulator(method="statevector").run(flat, shots=1).result().data(0)
    return np.array([data[f"m{m}"][1] for m in ms])


def mlae(hits: np.ndarray, shots: int, ms: list[int]) -> float:
    """Maximum-likelihood estimate of a from per-schedule hit counts."""
    odd = 2 * np.array(ms) + 1
    eps = 1e-15

    def nll(theta: float | np.ndarray) -> np.ndarray:
        s = np.sin(np.outer(np.atleast_1d(theta), odd)) ** 2
        s = np.clip(s, eps, 1 - eps)
        return -(hits * np.log(s) + (shots - hits) * np.log(1 - s)).sum(axis=1)

    # Coarse grid finer than one fringe of the highest power, then Brent refine around the best cell.
    n_grid = max(2000, 40 * int(odd.max()))
    grid = np.linspace(0, np.pi / 2, n_grid)
    i = int(np.argmin(nll(grid)))
    lo, hi = grid[max(i - 1, 0)], grid[min(i + 1, n_grid - 1)]
    res = minimize_scalar(lambda t: float(nll(t)[0]), bounds=(lo, hi), method="bounded",
                          options={"xatol": 1e-12})  # fmt: skip
    return float(np.sin(res.x) ** 2)


def queries(shots: int, ms: list[int]) -> int:
    return int(shots * sum(2 * m + 1 for m in ms))

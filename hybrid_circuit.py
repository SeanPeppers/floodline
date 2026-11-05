"""Circuit for one layer of the hybrid estimator (hybrid.py): P(obj = 1) after A_h equals
E[encode(Pq - Gq, layer)], and Q^m A_h follows sin^2((2m+1) theta) like any amplitude.

A_h, in order (registers little-endian; building blocks reused from multidriver_circuit.py):
  1. Load W, P24 | regime(W), S, O with Grover-Rudolph UCRYs. P3 is NOT loaded: it is integrated
     exactly inside the p table.
  2. QROM Gq[coarse cell] -> G (b bits), addressed by the top bits of W, P24, S, O. Done first,
     because the adders below overwrite W and S.
  3. Ripple-carry adders C = W + S, G_stage = S + O (as in multidriver_circuit.build).
  4. QROM T_int[C, G_stage] -> t (n_k bits).
  5. QROM Pq[P24, G_stage >> g_drop, t] -> P (b bits): the conditional flood probability with the
     3-h burst integrated, one lookup instead of a coherent bisection.
  6. Y = P + (2**b - 1 - G): flip G's bits, Cuccaro add into P with a carry qubit (b + 1 bits).
     Y - S is the integer residual r.
  7. One uniformly controlled RY on obj, controlled by Y: angle 2 arcsin sqrt(encode(Y - S)), the
     controlled rotation by arcsin(sqrt(.)) of the layer's [0, 1] value. 2**(b+1) CX in the
     standard multiplexor; a b-bit comparator against a uniform register would cost ~2b Toffoli
     instead (README_hybrid.md, not built).
Work registers stay computed; the pool comes back to |0> after every block, so S0 skips it.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit.library import UCRYGate, grover_operator

import hybrid as hy
import multidriver_circuit as mc


def build(t: hy.Tables, part: tuple[int, int, int], sink: Any = None) -> tuple[Any, Any, dict]:
    """(A_h, Q, layout) for one layer `part` = (sign, lo, hi). With `sink`, gates go to the counter."""
    m, nb, cfg, d, b = t.m, t.m.nbits, t.m.cfg, t.drop, t.bits
    al = mc._Alloc()
    reg = {name: al.take(nb[name]) for name in ("W", "P24", "S", "O")}
    c_carry = al.take(1 if nb["S"] else 0)
    g_carry = al.take(1 if nb["S"] and nb["O"] else 0)
    t_reg, p_reg, g_reg, y_carry = al.take(cfg.n_k), al.take(b), al.take(b), al.take(1)
    obj = al.take(1)[0]
    c_bits = reg["W"] + c_carry
    g_wide, g_narrow = (reg["S"], reg["O"]) if nb["S"] >= nb["O"] else (reg["O"], reg["S"])
    g_bits = g_wide + g_carry
    assert len(c_bits) == m.n_c and len(g_bits) == m.n_g, (len(c_bits), m.n_c, len(g_bits), m.n_g)
    cv_addr = [q for k in ("W", "P24", "S", "O") for q in reg[k][d[k] :]]  # top bits, W lowest
    t_addr = c_bits + g_bits
    p_addr = reg["P24"] + g_bits[m.g_shift :] + t_reg
    adder_need = max(nb["W"] - nb["S"] + 1, len(g_wide) - len(g_narrow) + 1, 1)
    pool = al.take(max(adder_need, len(cv_addr) - 1, len(t_addr) - 1, len(p_addr) - 1, 1))
    qc = sink if sink is not None else QuantumCircuit(al.n, name="A_h", metadata={"obj": obj})

    r = cfg.regime_bits
    mc.load_rows(qc, reg["W"], [], m.pmf_w[None, :])
    mc.load_rows(qc, reg["P24"], reg["W"][-r:], m.cond_p24)
    mc.load_rows(qc, reg["S"], [], m.pmf_s[None, :])
    mc.load_rows(qc, reg["O"], [], m.pmf_o[None, :])
    mc.qrom(qc, cv_addr, g_reg, t.gq.reshape(-1), pool)
    mc.add_into(qc, reg["S"], reg["W"], c_carry[0], pool)
    mc.add_into(qc, g_narrow, g_wide, g_carry[0], pool)
    mc.qrom(qc, t_addr, t_reg, m.T.T.reshape(-1), pool)  # address = c + 2**n_c * g
    mc.qrom(qc, p_addr, p_reg, t.pq.transpose(2, 1, 0).reshape(-1), pool)  # p24 + 2**n24 * (gr + 2**ngr * t)
    for q in g_reg:
        qc.x(q)
    mc.add_into(qc, g_reg, p_reg, y_carry[0], pool)
    y_vals = np.arange(2 ** (b + 1)) - t.scale  # residual r for every Y
    y_amp = hy.encode(np.clip(y_vals, -t.scale, t.scale), part)
    angles = 2 * np.arcsin(np.sqrt(np.clip(y_amp, 0.0, 1.0)))
    qc.append(UCRYGate(angles.tolist()), [obj, *p_reg, *y_carry])

    layout = {"total_qubits": al.n, "obj": obj, "pool": pool, "data_qubits": sum(len(v) for v in reg.values()),
              "cv_addr_bits": len(cv_addr), "t_addr_bits": len(t_addr), "p_addr_bits": len(p_addr)}  # fmt: skip
    if sink is not None:
        return sink, None, layout
    oracle = QuantumCircuit(al.n)
    oracle.z(obj)
    keep = [q for q in range(al.n) if q not in set(pool)]
    return qc, grover_operator(oracle, state_preparation=qc, reflection_qubits=keep), layout


def count(t: hy.Tables, part: tuple[int, int, int]) -> dict:
    """Logical gate counts of A_h by the same emission code, without building it. cx_equiv =
    CX + 6 per Toffoli + UCRY multiplexor CX (textbook decompositions, as mc.count_a)."""
    c = mc.GateCounter()
    _, _, lay = build(t, part, sink=mc._CountingSink(c))
    return {"toffoli": c.ccx, "cx": c.cx, "ucry_cx": c.ucry_cx, "cx_equiv": c.cx + 6 * c.ccx + c.ucry_cx,
            "qubits": lay["total_qubits"], **{k: v for k, v in lay.items() if k.endswith("_bits")}}  # fmt: skip

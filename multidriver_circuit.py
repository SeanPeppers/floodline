"""Quantum circuits for the multi-driver model (multidriver.py): state preparation + coherent
flood oracle A, and the Grover operator Q, built from the same integer tables the classical
samplers use, so P(obj = 1) after A equals Model.exact() exactly.

A, in order (all registers little-endian, qubit 0 of a register = least significant bit):
  1. Load the joint distribution, Rosenblatt order, Grover-Rudolph with uniformly controlled
     RY rotations (UCRY): W marginal; P24 controlled on the top regime bits of W; P3 controlled on
     the top regime bits of P24; S and O marginals. Cost ~2**(controls + bits) CX per driver,
     never the 2**(all data qubits) of a generic joint state preparation.
  2. Ripple-carry (Cuccaro/CDKM) adders: C = W + S in place on W (+1 carry qubit); G = S + O in
     place on the wider of S and O (+1 carry), after step 2 has consumed S.
  3. Two QROM lookups by unary iteration (Babbush et al. 2018, without the T-count tricks):
     T_int[C, G] and R_int[P24, P3, G >> g_drop] into two n_k-bit registers. ~2 Toffolis per
     table entry plus one CX per set data bit; empty subtrees are pruned.
  4. Comparator R_int >= T_int (Cuccaro carry chain, then reversed) flips the objective qubit.
  Work registers are left computed (no uncompute): Q = A S0 A^dagger S_chi pays for A and
  A^dagger once each either way, and S0 reflects every non-pool qubit about |0>. The ancilla
  pool (adder padding, carry-in, unary-iteration ANDs) is returned to |0> by every block, so
  S0 can skip it.

The tables are precomputed classically, and that is a real cost: 2**(address bits) evaluations
of each sub-model (drainage capacity over (C, G), burst runoff over (P24, P3, G)). It is far
smaller than the joint grid, but not negligible next to the classical enumeration cost of the
whole problem. README_multidriver.md discusses this.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from qiskit import QuantumCircuit, transpile
from qiskit.circuit.library import UCRYGate, grover_operator

from multidriver import Model


class _Alloc:
    def __init__(self) -> None:
        self.n = 0

    def take(self, k: int) -> list[int]:
        out = list(range(self.n, self.n + k))
        self.n += k
        return out


def load_rows(qc: QuantumCircuit, targets: list[int], ctrls: list[int], rows: np.ndarray) -> None:
    """Grover-Rudolph: amplitudes sqrt(rows[c, v]) on `targets` for each basis value c of `ctrls`."""
    n, nc = len(targets), len(ctrls)
    rows = np.asarray(rows, dtype=float).reshape(2**nc, 2**n)
    for k in range(n - 1, -1, -1):
        hi = n - 1 - k
        blocks = rows.reshape(2**nc, 2**hi, 2, 2**k).sum(axis=3)  # [ctrl, higher bits, this bit]
        angles = 2 * np.arctan2(np.sqrt(blocks[..., 1]), np.sqrt(blocks[..., 0]))  # [ctrl, higher]
        flat = angles.T.reshape(-1)  # index = ctrl + 2**nc * higher, ctrls are the low control bits
        controls = ctrls + targets[k + 1 :]
        if controls:
            qc.append(UCRYGate(flat.tolist()), [targets[k], *controls])
        else:
            qc.ry(float(flat[0]), targets[k])


def _maj(qc: QuantumCircuit, c: int, b: int, a: int) -> None:
    qc.cx(a, b)
    qc.cx(a, c)
    qc.ccx(c, b, a)


def _uma(qc: QuantumCircuit, c: int, b: int, a: int) -> None:
    qc.ccx(c, b, a)
    qc.cx(a, c)
    qc.cx(c, b)


def add_into(qc: QuantumCircuit, a: list[int], b: list[int], carry: int, pool: list[int]) -> None:
    """b <- a + b (len(b) >= len(a)), carry-out XORed into `carry`. Cuccaro et al. 2004 ripple
    adder; a is zero-padded with clean pool qubits, which (like the carry-in) come back to |0>."""
    pad = pool[: len(b) - len(a)]
    c0 = pool[len(b) - len(a)]
    aa = a + pad
    chain = [c0, *aa]
    for i in range(len(b)):
        _maj(qc, chain[i], b[i], aa[i])
    qc.cx(aa[-1], carry)
    for i in reversed(range(len(b))):
        _uma(qc, chain[i], b[i], aa[i])


def compare_geq(qc: QuantumCircuit, x: list[int], y: list[int], out: int, c0: int) -> None:
    """out ^= [x >= y] for equal-width registers: carry of x + ~y + 1, chain then un-chain."""
    for q in y:
        qc.x(q)
    qc.x(c0)
    chain = [c0, *y]
    for i in range(len(x)):
        _maj(qc, chain[i], x[i], y[i])
    qc.cx(y[-1], out)
    for i in reversed(range(len(x))):
        qc.ccx(chain[i], x[i], y[i])
        qc.cx(y[i], chain[i])
        qc.cx(y[i], x[i])
    qc.x(c0)
    for q in y:
        qc.x(q)


def qrom(qc: QuantumCircuit, addr: list[int], data: list[int], table: np.ndarray, anc: list[int]) -> None:
    """data ^= table[addr] by unary iteration; needs len(addr) - 1 clean ancillas, returned clean."""
    table = np.asarray(table, dtype=np.int64).reshape(-1)
    n = len(addr)
    if len(table) != 2**n:
        raise ValueError("table length must be 2**len(addr)")
    if n == 0:
        for j, q in enumerate(data):
            if (int(table[0]) >> j) & 1:
                qc.x(q)
        return

    def nonzero(level: int, prefix: int) -> bool:
        span = 2 ** (n - level)  # prefix = top `level` address bits, MSB first
        return bool(table[prefix * span : (prefix + 1) * span].any())

    def rec(ctrl: int, level: int, prefix: int) -> None:
        if level == n:
            v = int(table[prefix])
            for j, q in enumerate(data):
                if (v >> j) & 1:
                    qc.cx(ctrl, q)
            return
        a, t = addr[n - 1 - level], anc[level - 1]
        one, zero = nonzero(level + 1, 2 * prefix + 1), nonzero(level + 1, 2 * prefix)
        if one:
            qc.ccx(ctrl, a, t)
            rec(t, level + 1, 2 * prefix + 1)
            if zero:
                qc.cx(ctrl, t)
                rec(t, level + 1, 2 * prefix)
                qc.x(a)
                qc.ccx(ctrl, a, t)
                qc.x(a)
            else:
                qc.ccx(ctrl, a, t)
        elif zero:
            qc.x(a)
            qc.ccx(ctrl, a, t)
            rec(t, level + 1, 2 * prefix)
            qc.ccx(ctrl, a, t)
            qc.x(a)

    top = addr[n - 1]
    if nonzero(1, 1):
        rec(top, 1, 1)
    if nonzero(1, 0):
        qc.x(top)
        rec(top, 1, 0)
        qc.x(top)


class GateCounter:
    """Stands in for a QuantumCircuit to count A's logical gates without materializing it, so
    resolutions whose circuits would not fit in memory can still be costed. A UCRY with k
    controls costs 2**k CX (its standard multiplexor synthesis)."""

    def __init__(self) -> None:
        self.ccx = self.cx = self.x = self.ry = self.ucry_cx = 0


class _CountingSink:
    def __init__(self, c: GateCounter) -> None:
        self.c = c

    def cx(self, *_: int) -> None:
        self.c.cx += 1

    def ccx(self, *_: int) -> None:
        self.c.ccx += 1

    def x(self, *_: int) -> None:
        self.c.x += 1

    def ry(self, *_: object) -> None:
        self.c.ry += 1

    def append(self, gate: object, qargs: list[int]) -> None:
        self.c.ucry_cx += 2 ** (len(qargs) - 1)


def count_a(model: Model) -> dict:
    """Logical gate counts of A by the same emission code as build(), without building it.
    'cx_equiv' = CX + 6 per Toffoli + UCRY multiplexor CX (textbook decompositions)."""
    c = GateCounter()
    _, _, lay = build(model, sink=_CountingSink(c))
    return {"toffoli": c.ccx, "cx": c.cx, "x": c.x, "ucry_cx": c.ucry_cx,
            "cx_equiv": c.cx + 6 * c.ccx + c.ucry_cx, "qubits": lay["total_qubits"],
            "data_qubits": lay["data_qubits"], "t_addr_bits": lay["t_addr_bits"], "r_addr_bits": lay["r_addr_bits"]}  # fmt: skip


def build(model: Model, sink: Any = None) -> tuple[Any, Any, dict]:
    """(A, Q, layout) for this model. A.metadata["obj"] is the objective qubit. With `sink`
    (a gate counter), A's gates are emitted into it instead and Q is not built."""
    nb, cfg = model.nbits, model.cfg
    al = _Alloc()
    reg = {name: al.take(nb[name]) for name in ("W", "P24", "P3", "S", "O")}
    c_carry = al.take(1 if nb["S"] else 0)
    g_carry = al.take(1 if nb["S"] and nb["O"] else 0)
    t_reg, r_reg = al.take(cfg.n_k), al.take(cfg.n_k)
    obj = al.take(1)[0]
    c_bits = reg["W"] + c_carry
    if nb["S"] and nb["O"]:
        g_wide, g_narrow = (reg["S"], reg["O"]) if nb["S"] >= nb["O"] else (reg["O"], reg["S"])
        g_bits = g_wide + g_carry
    else:
        g_bits = reg["S"] or reg["O"]
    assert len(c_bits) == model.n_c and len(g_bits) == model.n_g, (len(c_bits), model.n_c, len(g_bits), model.n_g)
    t_addr = c_bits + g_bits
    r_addr = reg["P24"] + reg["P3"] + g_bits[model.g_shift :]
    adder_need = (nb["W"] - nb["S"] + 1) if nb["S"] else 0
    if nb["S"] and nb["O"]:
        adder_need = max(adder_need, len(g_wide) - len(g_narrow) + 1)
    pool = al.take(max(adder_need, len(t_addr) - 1, len(r_addr) - 1, 1))
    qc = sink if sink is not None else QuantumCircuit(al.n, name="A", metadata={"obj": obj})

    r = cfg.regime_bits
    load_rows(qc, reg["W"], [], model.pmf_w[None, :])
    load_rows(qc, reg["P24"], reg["W"][-r:], model.cond_p24)
    if nb["P3"]:
        load_rows(qc, reg["P3"], reg["P24"][-r:], model.cond_p3)
    if nb["S"]:
        load_rows(qc, reg["S"], [], model.pmf_s[None, :])
    if nb["O"]:
        load_rows(qc, reg["O"], [], model.pmf_o[None, :])
    if nb["S"]:
        add_into(qc, reg["S"], reg["W"], c_carry[0], pool)
    if nb["S"] and nb["O"]:
        add_into(qc, g_narrow, g_wide, g_carry[0], pool)
    qrom(qc, t_addr, t_reg, model.T.T.reshape(-1), pool)  # address = c + 2**n_c * g
    qrom(qc, r_addr, r_reg, model.R.transpose(2, 1, 0).reshape(-1), pool)  # p24 + 2**n24*(p3 + 2**n3*g)
    compare_geq(qc, r_reg, t_reg, obj, pool[0])
    layout = {"registers": {k: v for k, v in reg.items() if v}, "C": c_bits, "G": g_bits, "T": t_reg, "R": r_reg,
              "obj": obj, "pool": pool, "t_addr_bits": len(t_addr), "r_addr_bits": len(r_addr),
              "data_qubits": sum(nb.values()), "total_qubits": al.n}  # fmt: skip
    if sink is not None:
        return sink, None, layout

    oracle = QuantumCircuit(al.n)
    oracle.z(obj)
    keep = [q for q in range(al.n) if q not in set(pool)]
    q_circ = grover_operator(oracle, state_preparation=qc, reflection_qubits=keep)
    return qc, q_circ, layout


def resources(a_circ: QuantumCircuit, q_circ: QuantumCircuit) -> dict:
    """Logical counts. 'cx' after transpiling to {cx, u} with all-to-all connectivity (counting
    only; nothing here is run). 'toffoli' counts the CCX gates of our own construction before
    synthesis (QROM + adders + comparator), the figure fault-tolerant cost models start from."""
    out = {}
    for name, c in (("A", a_circ), ("Q", q_circ)):
        tc = transpile(c, basis_gates=["cx", "u"], optimization_level=1, seed_transpiler=0)
        ops = tc.count_ops()
        out[name] = {"qubits": c.num_qubits, "cx": int(ops.get("cx", 0)), "u": int(ops.get("u", 0)),
                     "depth": int(tc.depth())}  # fmt: skip
    tof = int(a_circ.count_ops().get("ccx", 0))
    out["A"]["toffoli"] = tof
    out["Q"]["toffoli_excl_S0"] = 2 * tof
    return out

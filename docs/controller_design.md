# Adaptive Decision Controller Design & Switching Optimization

## 1. Controller Architecture

The decision engine bridges machine learning predictions and database concurrency control execution. It evaluates continuous predictions against a utility model and transition cost matrix.

```
                    ┌─────────────────────────┐
                    │ Current System State    │
                    │ (Protocol, RTT, Conflict)
                    └───────────┬─────────────┘
                                │
┌────────────────────────┐      │      ┌─────────────────────────┐
│ Contention Predictor   ├──────┼─────►│ Adaptive Decision       │
│ (Conflict Rate @ t+h)  │      │      │ Controller              │
└────────────────────────┘      │      │ (src/controller/        │
                                │      │  decision_engine.py)    │
┌────────────────────────┐      │      └───────────┬─────────────┘
│ Network Predictor      ├──────┘                  │
│ (RTT @ t+h)            │                         │
└────────────────────────┘                         ▼
                                       ┌─────────────────────────┐
                                       │ Action:                 │
                                       │ MAINTAIN or SWITCH      │
                                       │ + Target Protocol       │
                                       └─────────────────────────┘
```

---

## 2. Utility Formulation & Switching Cost Model

Let $\mathcal{P} = \{\text{OCC}, \text{2PL}, \text{MVCC}\}$ denote the set of supported protocols.
Let $p_{\text{curr}} \in \mathcal{P}$ be the active protocol.

For each candidate protocol $p \in \mathcal{P}$, the controller calculates an expected suitability score:
$$S(p \mid \hat{C}_{t+h}, \hat{R}_{t+h}) \in [0.0, 1.0]$$

If $p \ne p_{\text{curr}}$, a transition penalty is subtracted based on the switching cost $C(p_{\text{curr}} \to p)$:
$$U(p) = \begin{cases} 
S(p) + \beta_{\text{stay}} & \text{if } p = p_{\text{curr}} \\
S(p) - \min\left(\frac{C(p_{\text{curr}} \to p)}{1000}, \alpha_{\text{cap}}\right) & \text{if } p \ne p_{\text{curr}}
\end{cases}$$
Where $\beta_{\text{stay}} = 0.05$ is an inertia bonus to reward stability, and $\alpha_{\text{cap}} = 0.30$ caps the penalty.

### Switching Threshold Condition
The optimal candidate protocol is:
$$p^* = \arg\max_{p \in \mathcal{P}} U(p)$$

A protocol switch from $p_{\text{curr}} \to p^*$ is triggered if and only if:
1. **Net Improvement Criterion:**
   $$U(p^*) - U(p_{\text{curr}}) \ge \theta_{\text{improvement}} \quad (\text{default: } 0.10)$$
2. **Hysteresis Criterion:**
   $$t_{\text{current}} - t_{\text{last\_switch}} \ge \Delta T_{\text{min}} \quad (\text{default: } 30\text{ seconds})$$

If either condition is violated, the controller outputs `action: maintain`.

---

## 3. Database Internals & Protocol Transition Semantics

Switching concurrency control protocols in a live distributed database cannot occur instantaneously. In a production engine, correctness requires addressing in-flight transactions:

1. **OCC to 2PL Transition:**
   - In-flight OCC transactions are permitted to reach validation.
   - New incoming transactions are queued until the lock manager is initialized.
   - Quiescent synchronization is established before 2PL lock acquisition begins to prevent isolation violations.
2. **2PL to OCC Transition:**
   - All currently held shared/exclusive locks must be released.
   - Long-running write transactions must commit or abort to prevent orphaned lock entries.
   - OCC validation timestamp structures and local read/write sets are allocated.
3. **MVCC Transitions:**
   - Snapshot isolation reads in progress can continue reading immutable older version records.
   - Active update chains must be consolidated to avoid lost updates during protocol handover.

> [!WARNING]
> While this research implements an algorithmic simulation of protocol transitions with explicit cost modeling, true zero-downtime hot switching in production distributed databases (e.g. CockroachDB or TiDB) requires specialized kernel support and transactional consensus.


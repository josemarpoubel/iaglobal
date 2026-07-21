# Topology Contract

## Objective

The architecture contract guarantees that the four representations of the pipeline remain synchronized.

Every structural change must preserve this contract. Validation is automated in `iaglobal/tests/test_topology_contract.py` via `audit_representations()`.

---

## Architecture Rationale

The pipeline is described by four distinct representations, each serving a different purpose. They are not accidental duplication — they are different projections of the same architecture:

| Representation | File | Purpose |
|---|---|---|
| `PIPELINE_SKILLS` | `pipeline_definition.py` | Operational order — the sequence in which nodes are dispatched at runtime |
| `RUN_NODE_NAMES` | `builder.py` | Executable graph — the set of nodes wired into the `ExecutionGraph` object |
| `PHASES` | `topology.py` | Architectural classification — which conceptual phase each node belongs to |
| `NODE_DEPENDENCIES` | `topology.py` | Causal precedence — which nodes must complete before a given node starts |

None of these representations is automatically derived from another. They are all separate sources of truth for different aspects of the architecture and must remain consistent with each other.

---

## Invariants

### Structure

| Check | What it validates |
|---|---|
| `no_cycles` | The dependency graph (`NODE_DEPENDENCIES`) is acyclic |
| `no_dangling_deps` | Every dependency referenced in `NODE_DEPENDENCIES` exists in at least one representation |

### Integrity

| Check | What it validates |
|---|---|
| `no_dependency_without_phase` | Every node referenced in `NODE_DEPENDENCIES` (key or value) belongs to a phase |
| `no_duplicate_phase_nodes` | No node appears in more than one phase in `PHASES` |

### Implementation

| Check | What it validates |
|---|---|
| `no_orphan_run_functions` | Every `run_*` function in `iaglobal/graphs/nodes/` has a registration in at least one representation |

### Classification

| Check | What it validates |
|---|---|
| `no_pipeline_without_phase` | Every node in `PIPELINE_SKILLS` has an architectural phase in `PHASES` |
| `no_builder_without_phase` | Every node in `RUN_NODE_NAMES` has an architectural phase in `PHASES` |

### Reachability

| Check | What it validates |
|---|---|
| `all_unreachable_exist` | Nodes not visited by DFS from all roots still exist in at least one representation (they are intentional isolates, not orphans) |

### Obtaining current counts

Exact counts are intentionally not documented here — they evolve as the pipeline grows. Use `audit_representations()` to obtain the current architectural baseline:

```python
from iaglobal.graphs.pipeline_definition import PIPELINE_SKILLS
from iaglobal.graphs.builder import RUN_NODE_NAMES
from iaglobal.graphs.topology import audit_representations

result = audit_representations(
    pipeline_nodes=set(n for n, _ in PIPELINE_SKILLS),
    builder_nodes=set(RUN_NODE_NAMES),
)
print(result["pipeline_count"], result["builder_count"], result["topology_count"])
```

---

## Process: Adding a new node

1. **Implement**: Create `iaglobal/graphs/nodes/no_<name>.py` with `async def run_<name>(ctx)`
2. **Register in pipeline**: Add entry to `PIPELINE_SKILLS` in `pipeline_definition.py`
3. **Register in builder**: Add `"<name>"` to `RUN_NODE_NAMES` in `builder.py`
4. **Classify**: Add `"<name>"` to the appropriate phase list in `PHASES` in `topology.py`
5. **Wire dependencies**: Add entry to `NODE_DEPENDENCIES` in `topology.py` if the node has prerequisites
6. **Validate**: Run `python -m pytest iaglobal/tests/test_topology_contract.py -v`

### Removing or renaming a node

1. Remove references from all four representations
2. Verify the physical file is deleted or renamed
3. Validate with `test_topology_contract.py`

---

## Files involved

```
iaglobal/graphs/pipeline_definition.py   — PIPELINE_SKILLS
iaglobal/graphs/builder.py               — RUN_NODE_NAMES
iaglobal/graphs/topology.py              — PHASES + NODE_DEPENDENCIES + audit_representations()
iaglobal/tests/test_topology_contract.py — 5 validation tests
```

---

## Relationship to other architecture documents

- `docs/architecture_analysis.md` — general architecture guidelines
- `docs/arquitetura_evolucao.md` — evolution-centric architecture perspective
- `AGENTS.md` — operational instructions for agents modifying the pipeline

This contract is the machine-verifiable layer of the architecture. It complements the higher-level design documents by providing automated regression protection.

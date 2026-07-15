# Model version control

Chat is **not** the source of truth. The BIM model is. Every meaningful edit must become a **committed version**.

## Concepts

| Term | Meaning |
|------|---------|
| **Working tree** | Current `model.llmbim.json` (may have uncommitted edits) |
| **Commit / version** | Full snapshot of the model + message + parent + content hash |
| **Journal** | Append-only log of every mutation (finer than commits) |
| **Tag** | Named pointer (`baseline`, `for_client`) → version id |
| **Diff** | Element-level added / removed / changed |

```text
output/my_project/
  model.llmbim.json          ← working tree
  .llmbim/
    HEAD                     ← current version id
    journal.jsonl            ← every op
    refs.json                ← tags
    versions/
      ver_abc….json          ← immutable snapshots
```

## Agent rules (mandatory)

1. After a batch of model edits, **`commit("why this change")`**.
2. Never present “done” if `status()` is dirty without committing or explaining.
3. Use **`diff()`** before commit when reviewing changes.
4. **`checkout(version)`** restores history — it drops uncommitted work.
5. Chat messages are not versions. Only commits are.

## Python

```python
from llmbim import Project

p = Project.create("Office")  # auto VCS under output/office/
p.add_level("L1", 0)
p.create_rect_shell(level="L1", x=0, y=0, w=12000, d=9000, height_mm=3500, thickness_mm=200, name_prefix="B")
p.commit("Add building shell")

p.place_door(host=..., offset_mm=2000, width_mm=900, height_mm=2100)
print(p.status())   # dirty
print(p.diff())     # HEAD vs working
p.commit("Add entry door")

print(p.log())
p.tag("baseline")
# later:
# p.checkout("ver_…") or p.checkout("baseline")
```

## CLI

```bash
# path = project directory (with .llmbim/) or model.llmbim.json beside .llmbim
llmbim status output/office
llmbim diff output/office
llmbim commit output/office -m "Add north windows"
llmbim log output/office
llmbim tag output/office for_review
llmbim checkout output/office ver_abc123
llmbim journal output/office
```

## Why not “just git”?

You **can** also git-commit the `output/` or project files. Model VCS adds:

- Element-aware **diff** (not line noise in 50k JSON)
- **Journal** of semantic ops (wall_create, not blob patches)
- **checkout** without leaving the agent workflow
- Content **hash** integrity per version

Git remains great for the **code** of llm-bim. Model VCS is for the **building**.

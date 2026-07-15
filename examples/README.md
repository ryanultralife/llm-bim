# Examples / test cases

| Script | Scale | Source | Outputs |
|--------|-------|--------|---------|
| `simple_house.py` | residential box | synthetic | walls/doors |
| **`intec_site.py`** | facility (m) | `intec_fusion_params.json` + INT-GA | plan, section, glTF |
| **`proto10_separator.py`** | equipment (mm) | Fusion MB-SEP-PROTO / RFQ | plan, section, envelopes |

## Run

```bash
pip install -e ".[dev,server]"
python examples/intec_site.py
python examples/proto10_separator.py
```

Artifacts land in `examples/output/intec/` and `examples/output/proto10/`.

## Honesty

Both cases are **ENGINEERING ESTIMATE** geometry for agent BIM testing:
- INTEC arrangement tracks Fusion/Revit site params (not a full CD set).
- Proto10 uses **axis-aligned envelopes** of the Fusion STEP parts (shell, flanges, yoke, magnets, cartridge) — not 118-body STEP fidelity.

Claude: IFC export of these models is a good WP-IFC acceptance fixture once claimed.

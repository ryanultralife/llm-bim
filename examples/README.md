# Examples / test cases

| Script | Scale | Source | Outputs |
|--------|-------|--------|---------|
| `simple_house.py` | residential box | synthetic | walls/doors |
| **`intec_site.py`** | facility (m) | `intec_fusion_params.json` + INT-GA | plan, section, glTF, CW copper takeoff |
| **`proto10_separator.py`** | equipment (mm) | Fusion MB-SEP-PROTO / RFQ | plan, section, parts assigned |
| **`plumbing_loop.py`** | room MEP | synthetic CW loop | **90° copper elbows by size** |
| **`multi_trade_catalog.py`** | all CSI trades | fire/process/steel/rebar/fixtures | `TRADE_ANSWERS.json` |
| **`module_machine_host.py`** | modules | skid → facility host | block + native + ports/connect |

## Run

```bash
pip install -e ".[dev,server]"
python examples/intec_site.py
python examples/proto10_separator.py
python examples/plumbing_loop.py
llmbim takeoff output/plumbing_loop --kind plumbing
```

Artifacts: `examples/output/intec/`, `examples/output/proto10/`, `output/plumbing_loop/` (incl. `COPPER_90_ELBOWS.json`, `materials/fitting_takeoff.csv`).

## Honesty

Both cases are **ENGINEERING ESTIMATE** geometry for agent BIM testing:
- INTEC arrangement tracks Fusion/Revit site params (not a full CD set).
- Proto10 uses **axis-aligned envelopes** of the Fusion STEP parts (shell, flanges, yoke, magnets, cartridge) — not 118-body STEP fidelity.

Claude: IFC export of these models is a good WP-IFC acceptance fixture once claimed.

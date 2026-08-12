# ⚛️ QAI V3 — Sonification / 13D Pattern Lab

A deterministic simulation/art analysis pipeline.

## Run

```bash
cd ~/QAI
source qai-env/bin/activate
python run_qai_v3.py
```

Requires NumPy. No GPU is required for this artifact generator.

## Outputs

`outputs/ghost/audio/circuit.wav` — logic + quantum-inspired gate sonification.

`outputs/ghost/audio/odd_chars_qubits.wav` — Unicode/symbol codepoints mapped to qubit-style Bloch parameters and pitch.

`outputs/ghost/audio/patterns_plasma_dark_rare.wav` — sonification of numerical gradient regions and negative graph links.

`outputs/ghost/inverted/inverted_field.wav` — phase-inverted synthetic field.

`outputs/ghost/circuits/gates.json` — detected synthetic gate motifs.

`outputs/ghost/13d/folded_13d.csv` — SHA-256-derived 13-dimensional embedding.

`outputs/ghost/hashes/spacetime_hash.json` — deterministic hash mapping metadata.

`outputs/ghost/kml/qai_hash_projection.kml` — Google Earth compatible projection of hash coordinates.

`outputs/ghost/patterns/pattern_report.json` — islands, high-gradient regions, negative graph links and rare clusters.

## Terminology

The pipeline deliberately uses expressive labels. `ghost` means an output namespace. `plasma` means high numerical gradient. `dark link` means a negative-weight edge in the synthetic graph. `exotic particle` means a rare statistical feature cluster. `spacetime` means a deterministic numerical hash projection. None of these labels constitutes detection of a physical phenomenon.

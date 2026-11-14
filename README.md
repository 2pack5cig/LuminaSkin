# LuminaSkin

**Explainable, multimodal skin-rash triage built for Indian and darker skin tones.**

Take up to 3 photos of a rash (close-up, angle, distance), tap a few yes/no questions, and LuminaSkin shows:

- the **3 most likely of 15 conditions**, with an "eczema family" grouping
- a **Grad-CAM++ heatmap** of where the AI looked
- **red-flag safety banners** from fixed clinical rules (independent of the AI)
- a strict **"don't self-medicate" banner** against over-the-counter steroid/combination creams and antibiotics
- **follow-up questions** chosen from the AI's top 3 that add hints and **"could also be"** cards (chickenpox, heat rash, drug reaction, leprosy…) without changing the AI's ranking
- a **scabies screen** from clinical criteria, a **leprosy (numb patch)** check, and steroid / child / pregnancy cards
- condition info, **Soothing Care** tips, a private **scan history** on the phone, and a detailed **doctor PDF**
- a **Spot tracker**: measure a mole or rash patch with a coin for scale (mm, area, colours, outline) and recheck it over
  time; growth, new colours or a more uneven outline are flagged (a measurement aid, not a skin-cancer test)

> ⚠️ **LuminaSkin is a triage aid, not a diagnosis.** It has not been clinically validated. Always consult a qualified doctor.

## Conditions (15)
Acne · Contact dermatitis · Eczema · Folliculitis · Herpes simplex · Herpes zoster (shingles) · Impetigo · Insect bite ·
Pityriasis rosea · Psoriasis · Scabies · Tinea (ringworm) · Tinea versicolor · Urticaria (hives) · Vitiligo

## How it works
```
Phone (Next.js PWA) ──/api──► FastAPI on the laptop
  1. photo quality gate (blur at fixed scale, darkness; glare = warning only), tuned on dermatologist-approved photos
  2. "not skin / unusual photo" gate: nearest-neighbour distance to real rash photos in Derm Foundation space
  3. Google Derm Foundation → 6,144-number embedding → logistic regression
  4. EfficientNet-B0 on pixels (+ Grad-CAM++ heatmap)
  5. symptom model (gradient-boosted trees on SCIN's yes/no questions)
  6. late fusion: weighted log-linear pool (works with or without symptoms) → "not confident" threshold
  7. fixed rules: red flags, self-medication warning, scabies screen, alerts → follow-up questions → hints
Spot tracker (/spots): coin detection (Hough circles) → lighting-corrected spot outline from the tapped point
  → size / area / colours / outline → compare with the previous check (+ Derm Foundation "same spot?" similarity)
```

## Results (v3, held-out test, split by patient, evaluated once)

| Test set | Cases | Top-3 correct | Top-1 | Macro recall |
|---|---|---|---|---|
| **All (SCIN + DermaCon-IN)** | 612 | **89.1%** | 66.7% | 63.9% |
| **Indian patients (DermaCon-IN)** | 305 | **90.8%** | 75.4% | 53.7% |
| Fitzpatrick IV–VI (brown/dark) | 303 | **89.1%** | 70.0% | 51.1% |
| Fitzpatrick I–III | 301 | 89.4% | 63.8% | 70.6% |

- **Before vs after adding Indian data** (same 235 Indian test cases, same 13 conditions): top-3 **69.4% → 90.6%**, top-1 **34.0% → 72.3%**; Fitzpatrick V–VI top-3 **71.2% → 94.2%**.
- On the older SCIN test set the new model is about equal overall (top-3 88.2% vs 88.9%) and slightly lower on SCIN dark-skin cases (82.9% vs 85.7%, 70 cases).
- Adding symptoms: macro recall 60.7% (photo only) → 63.9%.
- Negative-photo test (67 objects, look-alikes, other skin conditions, bad photos): confident wrong answers fell from **32 → 15** after replacing the out-of-distribution gate (non-skin: 13/23 → 2/23). These photos were also used to choose the gate, so treat as optimistic.
- **Limitations:** only 8 Fitzpatrick VI test cases; labels are dermatologist opinions from photos; other skin conditions (melasma, moles, warts…) can still get a confident answer; not clinically validated.
- The shipped model (`ml/models_v3_final`) is v3 retrained on 100% of the data; the scores above are v3's held-out results.

## Data
- **SCIN** (Google Research): dermatologist-labelled phone photos with patient-reported symptoms.
- **DermaCon-IN** (Madarkar et al., IIT Hyderabad, 2025; CC BY-NC-SA 4.0; doi:10.7910/DVN/W7OUZM): 3,352 photos from 1,950 South Indian patients used for our conditions (mapping in `ml/data/dermacon_map.json`).
- Experiments: Fitzpatrick17k (Groh et al., 2021; CC BY-NC-SA 3.0), tried and not shipped.
- Split: SCIN's original test cases kept for a fair comparison; everything else 70/15/15 by patient (`ml/data/v3/split_v3.json`).
- Photos and embeddings are **not** included in this repository.

## Run it
**Backend** (Python 3.11, macOS/Linux):
```bash
python3.11 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
echo "HF_TOKEN=<Hugging Face token with access to google/derm-foundation>" > backend/.env
cd backend && ../.venv/bin/uvicorn app.main:app --port 8000      # uses ml/models_v3_final by default
```
**Frontend**:
```bash
cd frontend && npm install && npm run dev -- -H 0.0.0.0
```
Open `http://<laptop-ip>:3000` (landing page) or `/scan` on a phone on the same Wi-Fi.

**Re-train v3:** `ml/v3_prepare.py` → `ml/v3_embed.py` → `ml/v3_train_effnet.py` → `ml/v3_fit.py` → `ml/v3_final.py`.

## Repository
```
frontend/   Next.js + Tailwind web app (landing page, scan flow, results, history, doctor PDF)
backend/    FastAPI: quality + OOD gates, models, Grad-CAM, red flags, medicine warning, follow-ups, spot tracker, disease info (kb/)
docs/       sources for the project summary + study guide (PDFs are generated locally, not committed)
ml/         data preparation, training and evaluation scripts; live model in ml/models_v3_final/
```

## Credits
SCIN dataset © Google. DermaCon-IN © Madarkar et al., IIT Hyderabad (CC BY-NC-SA 4.0). Fitzpatrick17k © Groh et al. (CC BY-NC-SA 3.0).
Derm Foundation by Google Health AI Developer Foundations. Negative test photos from Wikimedia Commons (licences listed in `ml/data/negatives/sources.csv`).

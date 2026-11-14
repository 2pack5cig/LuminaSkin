# LuminaSkin

**Explainable, multimodal skin-rash triage tuned for Indian and darker skin tones.**

Take up to 3 photos of a rash (close-up, angle, distance), answer a few yes/no questions, and LuminaSkin shows:

- the **3 most likely conditions** (13 common conditions), with an "eczema family" grouping
- a **Grad-CAM++ heatmap** of where the AI looked
- **urgent red-flag warnings** (fixed clinical rules, independent of the AI)
- a **scabies screen** based on clinical criteria (night itch, household contacts, typical sites)
- disease information, an **anti-steroid-misuse warning**, and **Soothing Care** tips
- a private **scan history** on the phone and a one-tap **doctor PDF**

> ⚠️ **LuminaSkin is a triage aid, not a diagnosis.** It has not been clinically validated. Always consult a qualified doctor.

## How it works

```
Phone (Next.js PWA) ──/api──► FastAPI on the laptop
                              1. photo quality gate (blur / dark / glare, OpenCV)
                              2. "not skin / unusual photo" gate (skin-colour ratio + Mahalanobis distance)
                              3. Google Derm Foundation → 6,144-number embedding → logistic regression
                              4. EfficientNet-B0 on pixels (+ Grad-CAM++ heatmap)
                              5. symptom model (gradient-boosted trees on SCIN's yes/no questions)
                              6. late fusion: weighted log-linear pool (works with or without symptoms)
                              7. "not confident" threshold, red-flag rules, scabies screen, disease info
```

## Results (held-out SCIN test set, 306 cases, evaluated once)

| | Top-3 correct | Top-3, Fitzpatrick IV–VI | Macro recall | Macro recall, IV–VI |
|---|---|---|---|---|
| **Combined (app)** | **88.9%** | **85.7%** | **59.7%** | **54.0%** |
| Photo only (symptoms skipped) | 88.2% | 84.3% | 55.2% | 49.1% |
| Symptoms only | 50.2% | 52.9% | 22.0% | 25.6% |

- Using **close-up + angle + distance** photos instead of one photo: top-3 82.8% → 89.2% (cases with 2+ photos).
- **Limitations:** few dark-skin examples in public data (only 2 Fitzpatrick VI test cases); labels are dermatologist opinions from photos; 13 conditions only.
- We tested adding 277 Fitzpatrick17k dark-skin images (v2): it did not beat the baseline on held-out data, so v1 is the default. See `ml/models*/report.json`.

## Data

- **SCIN** (Google Research, Skin Condition Image Network). 1,527 dermatologist-labelled cases across 13 conditions; split by patient case (no leakage), locked in `ml/data/split_v1.json`.
- **Fitzpatrick17k** (Groh et al., 2021; licence CC BY-NC-SA 3.0), dark-skin photos used for training experiments only; IDs listed in `ml/data/fitz/used_photos.csv`.
- Photos and embeddings are **not** included in this repository; scripts re-download them.

## Run it

**Backend** (Python 3.11, macOS/Linux):
```bash
python3.11 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
echo "HF_TOKEN=<your Hugging Face token with access to google/derm-foundation>" > backend/.env
cd backend && MODELS_DIR=../ml/models_v1_scin ../.venv/bin/uvicorn app.main:app --port 8000
```

**Frontend**:
```bash
cd frontend && npm install && npm run dev -- -H 0.0.0.0
```
Open `http://<laptop-ip>:3000` on a phone on the same Wi-Fi.

**Re-train** (in order): `ml/embed_scin.py audit` → `ml/prepare.py` → `ml/embed_scin.py final` → `ml/train_symptoms.py` → `ml/train_effnet.py` → `ml/fit_ensemble.py`.

## Repository

```
frontend/   Next.js + Tailwind web app (capture, questions, results, history, PDF)
backend/    FastAPI: quality gate, red flags, scabies screen, models, Grad-CAM, disease info (kb/)
ml/         data preparation, training and evaluation scripts; trained models in ml/models_v1_scin/
```

## Credits

SCIN dataset © Google. Fitzpatrick17k © Groh et al. (CC BY-NC-SA 3.0). Derm Foundation by Google Health AI Developer Foundations.

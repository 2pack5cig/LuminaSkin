# LuminaSkin

**A careful first look at a skin rash, built and tested for Indian and darker skin.**

Take a photo of a rash on your phone, tap a few yes/no questions, and LuminaSkin tells you the most likely conditions,
whether anything looks urgent, which medicines to avoid, and when to see a doctor. It can also track a mole over time.

> ⚠️ **LuminaSkin is a triage aid, not a diagnosis.** It has not been clinically validated. Always consult a qualified doctor.

---

## Why we built it

- Most skin AI is trained on **light skin**. On brown and dark skin, a rash often looks purple or brown instead of red, so these tools miss it.
- In India, people often buy **steroid creams over the counter**. On fungal infections (ringworm) these make the rash spread and harder to treat.
- Serious problems such as **leprosy (a numb patch)**, **shingles near the eye** or **severe allergic reactions** need a doctor fast.

## What it does

| Feature | What the user sees |
|---|---|
| **Rash check** | Up to 3 photos + quick questions → the **3 most likely of 15 conditions**, with a **heatmap** of where the AI looked |
| **Safety warnings** | Fixed medical rules (not AI) for emergencies, e.g. swollen lips, trouble breathing, rash near the eye, a numb patch |
| **Medicines to avoid** | A clear "don't use without a prescription" notice for steroid creams and antibiotics |
| **"Not confident"** | If the AI isn't sure, it hides its guesses and says *see a doctor* |
| **Not a rash?** | Photos that don't look like skin (a mug, a table) are refused |
| **Follow-up questions** | 2–4 extra questions that give hints and "could also be" cards (e.g. chickenpox), without changing the AI's answer |
| **Spot tracker** | Measure a mole with a coin for scale, recheck it over time, and get a **concern bar** based on the ABCDE warning signs doctors use |
| **Doctor PDF & history** | A report to show a doctor; past scans and tracked spots stay **on the phone** |

**The 15 conditions:** Acne · Contact dermatitis · Eczema · Folliculitis · Herpes simplex (cold sores) · Herpes zoster (shingles) ·
Impetigo · Insect bite · Pityriasis rosea · Psoriasis · Scabies · Tinea (ringworm) · Tinea versicolor · Urticaria (hives) · Vitiligo

## How well it works

Tested on **patients the model never saw** (split by patient, test set used once):

| | Right answer in the top 3 |
|---|---|
| Indian patients (305 cases) | **90.8%** |
| Brown / dark skin (Fitzpatrick IV–VI) | **89.1%**, the same as lighter skin (89.4%) |
| Indian patients, before → after adding Indian data | **69% → 91%** |

Limitations: only 8 test cases of the very darkest skin type, labels come from dermatologists looking at photos, and it is not clinically validated.

## How it works (in short)

```
 Phone browser  ──►  Website (Next.js)  ──►  Analysis server (Python, on our laptop)
                                              1. Is the photo sharp and bright enough?
                                              2. Does it look like a skin rash at all?
                                              3. Three AI models look at it and the answers:
                                                   • Google Derm Foundation (a skin-image model)
                                                   • EfficientNet (a small image model, gives the heatmap)
                                                   • a symptom model (uses the yes/no answers)
                                              4. Their answers are combined → top 3, or "not confident"
                                              5. Fixed safety rules + follow-up questions run alongside
```

**Privacy:** photos are analysed in memory and never saved on the server. The AI runs on our own machine (no cloud AI).
Scan history and tracked spots stay on the user's phone. There's no login and no tracking.

---

## What's in this repository

```
LuminaSkin/
├── frontend/            The website people use (Next.js + Tailwind)
│   ├── app/             Pages: scan, results history ("My scans"), spot tracker ("Spots")
│   ├── components/      Building blocks of the scan: photo step, questions, follow-ups, result screen
│   ├── lib/             Talking to the server, the question list, doctor PDF, on-phone storage
│   └── public/          Landing page (landing.html) and app icon settings
│
├── backend/             The analysis server (Python, FastAPI)
│   ├── app/
│   │   ├── main.py        The server: receives photos and answers, returns the result
│   │   ├── models.py      Loads and runs the three AI models + heatmap
│   │   ├── fusion.py      Combines the models' answers into one
│   │   ├── quality.py     Photo check: blurry or too dark?
│   │   ├── ood.py         "Is this even a rash?" check
│   │   ├── redflags.py    Fixed safety rules (emergencies, scabies screen, leprosy, pregnancy, children)
│   │   ├── medicines.py   "Medicines to avoid" notice
│   │   ├── followups.py   Follow-up questions and hints
│   │   ├── spot.py        Spot tracker: coin detection, mole measurement, ABCDE concern bar
│   │   └── features.py    The list of symptom questions the AI understands
│   └── kb/              Plain-language info for each condition (what it is, care tips, when to see a doctor)
│
├── ml/                  How the AI was trained
│   ├── v3_*.py          Current training steps: prepare data → image features → train → combine → final model
│   ├── models_v3_final/ The model the app uses
│   ├── models_v3/       Test results for the current model
│   ├── make_negatives.py  Builds the "not a rash" test photos
│   └── (other files)    Earlier versions, kept for reference
│
└── docs/src/            Source for the project summary and study guide (PDFs are made locally)
```

Training photos, image features and API keys are **not** included in this repository.

## Run it yourself

**You need:**
- **Python 3.11** (exactly 3.11, newer or older versions may not install the libraries)
- **Node.js** (version 18 or newer)
- A free **Hugging Face** account: open [google/derm-foundation](https://huggingface.co/google/derm-foundation), accept the terms,
  then create a token under *Settings → Access Tokens*
- About **5 GB** of free disk space. The first start downloads Google's skin model (~2 GB).

### Mac / Linux

**1. Analysis server**
```bash
python3.11 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
echo "HF_TOKEN=<your Hugging Face token>" > backend/.env
cd backend && ../.venv/bin/uvicorn app.main:app --port 8000
```

**2. Website** (in a second terminal)
```bash
cd frontend && npm install && npm run dev -- -H 0.0.0.0
```

### Windows

Use **Command Prompt** (search "cmd" in the Start menu) and run these from the project folder.

**1. Analysis server**
```bat
py -3.11 -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
echo HF_TOKEN=hf_YOURTOKEN> backend\.env
cd backend
..\.venv\Scripts\uvicorn app.main:app --port 8000
```

**2. Website** (open a second Command Prompt in the project folder)
```bat
cd frontend
npm install
npm run dev -- -H 0.0.0.0
```

Windows tips:
- No `py` command? Install Python 3.11 from [python.org](https://www.python.org/downloads/) and tick **"Add python.exe to PATH"**.
- In the `echo` line, replace `hf_YOURTOKEN` with your token, keeping **no space** before `>` (otherwise the token ends with a space).
- If Windows Firewall asks, click **Allow** so phones on your Wi-Fi can reach the site.
- On a normal laptop each scan takes a few seconds, because everything runs on the processor.

### Open it

Wait until the server window says **"Models ready"** and the website window says **"Ready"**, then open
`http://localhost:3000`. To use a phone on the same Wi-Fi, open `http://<laptop-ip>:3000`
(find the laptop's IP with `ipconfig` on Windows, or in Wi-Fi settings on a Mac).

<details>
<summary>Retraining the model (advanced)</summary>

Download the datasets (see below), then run in order:
`ml/v3_prepare.py` → `ml/v3_embed.py` → `ml/v3_train_effnet.py` → `ml/v3_fit.py` → `ml/v3_final.py`.
</details>

## Data and credits

- **SCIN** (Google Research): phone photos with patients' own symptom answers, labelled by dermatologists.
- **DermaCon-IN** (Madarkar et al., IIT Hyderabad, 2025; CC BY-NC-SA 4.0): photos from South Indian dermatology clinics, skin types III–VI.
- **Derm Foundation** by Google Health AI Developer Foundations.
- Fitzpatrick17k (Groh et al., 2021) was tried during development and **not** used in the final model.
- "Not a rash" test photos and demo photos: Wikimedia Commons (free licences).

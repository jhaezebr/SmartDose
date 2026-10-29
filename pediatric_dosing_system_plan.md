# Pediatric Medication Prescriber - Unified Architecture & Implementation Plan

A comprehensive, clinical-grade implementation plan combining an AI-powered **RAG Extraction Agent**, a **Deterministic Python Calculation Engine**, an integration with the **Belgian Recip-e / UHMEP FHIR Mock Server**, and a streamlined **Streamlit Clinician Dashboard**.

---

## 1. System Architecture & Information Flow

The system is designed around a fundamental safety principle: **AI extracts guidelines and cites sources, while deterministic Python code performs all clinical and mathematical calculations.**

```
                               +-------------------------------------------------------+
                               |               Streamlit Clinician UI                  |
                               |  - Patient Selector / ID Entry                        |
                               |  - Filters: Route (Oral, IV) & Intent (Proph / Ther)  |
                               |  - Substance / Brand Dropdown Autocomplete            |
                               |  - Safety Badges, Calculated Dosing, Syringe Guidance |
                               +---------------------------+---------------------------+
                                                           |
                          +--------------------------------+-------------------------------+
                          |                                                                |
                          v                                                                v
+-------------------------+-------------------------+            +-------------------------+-------------------------+
|     Patient & FHIR Data Integration Layer         |            |         Clinical Knowledge & RAG Pipeline       |
|  - Belgian Recip-e Mock Server (server.py)        |            |  - Sources: Kinderformularium.nl, PedMed.org,   |
|  - Patient Demographics: Age, Weight, Height, SCr |            |    UZ Gent PHO SCT Protocol, SAMv2              |
|  - Active Medication Reconciliation               |            |  - Vector DB (FAISS/ChromaDB) + Rich Metadata   |
|  - Allergies & Sensitivity Registry               |            |  - LLM Rule Extraction & Exact Source Citation |
+-------------------------+-------------------------+            +-------------------------+-------------------------+
                          |                                                                |
                          +--------------------------------+-------------------------------+
                                                           |
                                                           v
                               +-------------------------------------------------------+
                               |         Deterministic Python Calculation Engine       |
                               |  - BSA (Mosteller) & BMI Computation                  |
                               |  - Bedside Schwartz eGFR (k=0.413) & Renal Staging    |
                               |  - Exact Dose Computation (mg/kg, mg/m², Safety Caps) |
                               |  - Liquid Suspension Volume (ml) & Syringe Sizing     |
                               |  - DDI Traffic-Light Conflict & Allergy Checker       |
                               |  - Commercial SAM Brand & Magistral Compounding Map   |
                               +---------------------------+---------------------------+
                                                           |
                                                           v
                               +-------------------------------------------------------+
                               |             Prescription & Output Delivery            |
                               |  - Route-Specific Dosing (Filtered vs All Routes)     |
                               |  - Practical Caregiver Instructions (Food, Crushing)  |
                               |  - One-Click Push to Recip-e FHIR (ServiceRequest)    |
                               +-------------------------------------------------------+
```

---

## Phase 1: Data Preparation & Architecture

### 1.1 Clinical Knowledge Base Construction (RAG Pipeline)
- **Authoritative Sources**:
  - `background_information/medication_dosing_guidelines/`:
    - **UZ Gent PHO SCT Protocol (#906 v10)**: Prophylactic dosing for pediatric stem cell transplantation (Aciclovir, Fluconazole, SMZ-TMP, Ursodeoxycholzuur, Penicillin).
    - **Kinderformularium.nl**: Dutch/Belgian standard reference for pediatric pharmacotherapy.
    - **PedMed.org**: International pediatric dosing monographs and renal adjustment guidelines.
  - `background_information/medication_official_information/`:
    - **Belgian SAMv2 & Farmastatus**: Official packaging, CNK/AMPP codes, and current drug availability.
    - **TMF/FTM & Hospital Compounding Protocols**: Magistral formulations for pediatric suspensions.
- **Document Ingestion & Chunking with Rich Metadata**:
  - Split guidelines into clinically meaningful sections tagged with:
    - `substance`: Generic international nonproprietary name (e.g., `Aciclovir`).
    - `target_population`: Age intervals (`<6y`, `6-11y`, `≥12y`) and weight thresholds (`<40kg`, `≥40kg`).
    - `intent`: `prophylactic` vs `therapeutic`.
    - `route`: `oral`, `intravenous`, `intramuscular`.
    - `source_reference`: Document name, URL, table, and revision date.
- **Vector Indexing & Hybrid Retrieval**:
  - Embed chunks into a local vector store (e.g., FAISS or ChromaDB) combined with keyword/metadata filtering so queries retrieve strictly pediatric formulas from verified sources.

### 1.2 Patient Integration & Belgian FHIR Connection
- **Existing Mock Server Integration**:
  - Connect directly to the local **Belgian UHMEP v1.4 / Recip-e FHIR Mock Server** (`server.py` on `http://localhost:8000` backed by SQLite `uhmep_mock.db`).
- **Patient Profile Data Model**:
  - Patient ID (e.g. `pat-1001-jane-doe`, `pat-1002-marc-willems`).
  - Demographics: Age (years and months), Gender.
  - Biometrics: Weight ($kg$), Height ($cm$).
  - Renal Labs: Serum Creatinine ($\text{SCr}$ in $mg/dL$).
  - Clinical History: Allergies (e.g., Penicillin, NSAIDs), G-6-PD deficiency status.
  - Active Medications: Retrieved live via `POST /ServiceRequest/_search?patient={id}&status=active`.

---

## Phase 2: AI & Calculation Engine

### 2.1 The RAG Extraction Agent
- **Structured LLM Extraction (Gemini)**:
  Extracts dosing rules into a validated JSON schema without doing any math:
  ```json
  {
    "substance": "Aciclovir",
    "intent": "prophylactic",
    "routes": {
      "oral": {
        "rules": [
          {"weight_max_kg": 40, "formula": "3 x 250 mg/m2 / day", "rate_mg_m2": 250, "doses_per_day": 3},
          {"weight_min_kg": 40, "formula": "2 x 250 mg/m2 / day", "rate_mg_m2": 250, "doses_per_day": 2}
        ],
        "max_dose_mg_kg_day": 80,
        "max_absolute_dose_mg_day": 4000,
        "renal_adjustment": [
          {"crcl_min": 25, "crcl_max": 50, "instruction": "Give recommended dose Q12H"},
          {"crcl_min": 10, "crcl_max": 25, "instruction": "Give recommended dose Q24H"},
          {"crcl_max": 10, "instruction": "Reduce recommended dose by 50% and give Q24H"}
        ]
      },
      "intravenous": {
        "rules": [
          {"weight_max_kg": 40, "formula": "3 x 250 mg/m2 / dose IV", "rate_mg_m2": 250, "doses_per_day": 3},
          {"weight_min_kg": 40, "formula": "2 x 250 mg/m2 / dose IV", "rate_mg_m2": 250, "doses_per_day": 2}
        ],
        "max_dose_mg_kg_day": 60
      }
    },
    "instructions": [
      "Ensure adequate hydration to prevent renal tubule crystallization.",
      "Tablets may be divided along score line."
    ],
    "source_citation": {
      "title": "UZ Gent PHO SCT Richtlijn 906 v10 / Kinderformularium",
      "url": "https://www.kinderformularium.nl/geneesmiddel/25414/aciclovir"
    }
  }
  ```

### 2.2 Deterministic Python Calculation Engine
All clinical calculations are evaluated deterministically in Python:

1. **Body Surface Area (BSA) - Mosteller Equation**:
   $$\text{BSA}\,(m^2) = \sqrt{\frac{\text{Height}\,(\text{cm}) \times \text{Weight}\,(\text{kg})}{3600}}$$
2. **Body Mass Index (BMI)**:
   $$\text{BMI} = \frac{\text{Weight}\,(\text{kg})}{\left(\frac{\text{Height}\,(\text{cm})}{100}\right)^2}$$
3. **Renal Clearance - Pediatric Bedside Schwartz Equation**:
   $$\text{eGFR}\,(\text{ml/min}/1.73\,\text{m}^2) = \frac{0.413 \times \text{Height}\,(\text{cm})}{\text{Serum Creatinine}\,(\text{mg/dL})}$$
   - Compares calculated eGFR against the drug's tiered renal thresholds and modifies the dose or interval accordingly.
4. **Exact Dosage & Daily Safety Caps**:
   - Computes weight-based ($mg/kg$) or BSA-based ($mg/m^2$) dose.
   - Enforces double upper bounds:
     $$\text{Dose}_{\text{final}} = \min(\text{Dose}_{\text{calculated}}, \text{MaxDose}_{\text{weight-capped}}, \text{MaxDose}_{\text{adult}})$$
5. **Liquid Formulation & Syringe Safety Calculator (Preventing 10x Errors)**:
   - Evaluates:
     $$\text{Volume}\,(ml) = \frac{\text{Single Dose}\,(\text{mg})}{\text{Suspension Strength}\,(\text{mg/ml})}$$
   - Recommends the exact oral syringe barrel size:
     - For volumes $<1.0\,\text{ml}$: Recommend **$1\,\text{ml}$ oral syringe with $0.01\,\text{ml}$ gradations** (prevents the slide 11 clinical error of giving $3\,\text{ml}$ instead of $0.3\,\text{ml}$).
     - For volumes $1.0\text{--}3.0\,\text{ml}$: Recommend **$3\,\text{ml}$ syringe**.
     - For volumes $>3.0\,\text{ml}$: Recommend **$5\,\text{ml}$ or $10\,\text{ml}$ syringe**.

### 2.3 Drug-Drug Interaction (DDI) & Conflict Checker
- Reconciles candidate substance against patient active medications from FHIR and patient allergies:
  - **Traffic Light System**:
    - 🔴 **Red (Contraindication / Allergy Alert)**: Direct interaction (e.g., prescribing Amoxicillin with known Penicillin allergy; serious CYP3A4 inhibitors). Suggests pre-calculated safe alternatives from guidelines (e.g., Azithromycin / Clarithromycin).
    - 🟡 **Amber (Warning / Monitoring)**: Synergistic nephrotoxicity or immunosuppressive interactions requiring closer lab monitoring.
    - 🟢 **Green (Safe)**: No documented adverse interactions.

### 2.4 Brand Mapping & Magistral Compounding Engine
- **Belgian SAM / CNK Mapping**:
  - Maps generic substances to marketed Belgian commercial packages (e.g., *Zovirax 200mg / 800mg comp*, *Zovirax 400mg/5ml suspension 100ml*).
- **Magistral Compounding Recommendations**:
  - Automatically triggered if commercial packages cannot provide the micro-dose or if the tablet formulation cannot be crushed:
    - E.g., *Ursodeoxycholzuur* $\rightarrow$ Ursochol $30\,\text{mg/ml}$ magistral oral suspension.
    - E.g., Posaconazole crushed tablet suspension preparation under hospital pharmacist supervision.

---

## Phase 3: Streamlit Clinician UI Design

The UI is streamlined to minimize clinician clicks, replacing free-text prompts with fast, intuitive dropdowns.

### 3.1 Patient Entry & Context Header
- **Patient Selector**: Dropdown pre-populated with active clinic patients (`pat-1001-jane-doe`, `pat-1002-marc-willems`, `pat-1003-elena-vandenberg`), with an option for manual ID lookup.
- **Biometric Summary Card**:
  - Age, Gender, Weight, Height.
  - Calculated **BSA** ($m^2$) and **BMI** ($kg/m^2$).
  - Renal status: **Serum Creatinine** and computed **Schwartz eGFR**.
  - Current Active Medications & Allergy warning chips.

### 3.2 Medication Search & Filter Panel
- **Dropdown Pre-selection**:
  - **Administration Route**: Multi-select dropdown (`Oral`, `IV / Injection`, `Intramuscular`, `Topical`, `Inhalation`). Can select one, multiple, or leave empty (`All`).
  - **Clinical Intent**: Dropdown (`Prophylactic`, `Therapeutic`).
- **Substance / Brand Autocomplete**:
  - Searchable dropdown recommending approved substances and commercial brand synonyms as the doctor types.

### 3.3 Results & Decision Support Dashboard
- **DDI & Safety Status Banner**: Immediate Red / Amber / Green visual alert.
- **Dosing Recommendation Cards**:
  - **Doctor Route Preference Selected**: Displays only the requested route (e.g. Oral syrup).
  - **No Preference Selected**: Displays side-by-side cards comparing all available administration routes (Oral vs IV vs IM).
  - **Mathematical Transparency**: Displays the exact deterministic formula, patient parameters substituted, and intermediate steps.
  - **Syringe & Liquid Guidance**: Clear instruction badge: *"Give 2.25 ml of 400 mg/5 ml oral suspension using a 3 ml syringe"*.
- **Commercial Brands & Magistral Options**:
  - Available commercial packages with CNK codes and reimbursement status.
  - Magistral compounding recipe if standard package is unsuitable.
- **Clinical Instructions & Restrictions**:
  - "Take with food", "Do not crush tablet", "Hydration instructions".
- **Source Citation Expander**:
  - Expandable panel (`st.expander`) with the exact source guideline title, section, and web citation link.

### 3.4 One-Click Prescription Submission (Recip-e FHIR)
- **"Generate & Push to Recip-e" Action**:
  - Automatically constructs a Belgian UHMEP FHIR `ServiceRequest` payload containing patient SSIN pseudonym, AMPP/CNK drug code, calculated dosage text, and prescriber NIHII reference.
  - Transmits via `POST http://localhost:8000/ServiceRequest`.
  - Displays the generated Recip-e prescription identifier (e.g., `BE-RECIPE-20261029-XXXX`).

---

## Phase 4: Testing, Validation & Verification

1. **Clinical Golden Test Cases**:
   - **Case 1: Aciclovir Prophylaxis in SCT (<40kg)**: Verify $3 \times 250\,\text{mg/m}^2/\text{dose}$ calculation, $80\,\text{mg/kg/day}$ safety cap, oral syrup volume, and syringe size recommendation.
   - **Case 2: Renal Impairment Adjustment**: Verify that an eGFR of $35\,\text{ml/min}$ modifies dosing to Q12H interval.
   - **Case 3: Drug-Drug Interaction & Allergy**: Verify system blocks Amoxicillin when Penicillin allergy is flagged, suggesting Azithromycin / Clarithromycin.
   - **Case 4: Magistral Compounding**: Verify Ursodeoxycholzuur triggers magistral suspension recipe.
2. **FHIR Round-Trip Verification**:
   - Verify that prescriptions created in the Streamlit app appear in `GET /ServiceRequest/_search` and generate corresponding fulfillment `Task` resources on the mock server.
3. **UI Usability Audit**:
   - Ensure the workflow from patient selection to prescription generation can be executed in under 30 seconds using dropdown selections.

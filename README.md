# 👶 Pediatric Medication Prescriber - Clinical Decision Support System

An intelligent, safety-first clinical decision support platform and prescribing assistant built for pediatricians. It automates precise pediatric dosage calculations, enforces safety guardrails (renal/hepatic adjustments, excipient toxicities, and drug-drug interactions), and bridges hospital protocols directly to the **Belgian Recip-e FHIR** prescribing network.

---

## 📌 Problem It Solves

Prescribing for pediatric patients carries substantial clinical risks that general Electronic Health Record (EHR) systems fail to prevent:

1. **"Children are not small adults"**:
   - Dosing is not flat; it must be calculated dynamically based on **Body Surface Area (BSA)** or **weight ($mg/kg$)**, scaled against strict daily and single-dose maximums (e.g. adult ceilings).
   - Organ function changes rapidly; standard adult clearance tables do not apply to pediatric renal maturation.
2. **Administration and Calculation Errors**:
   - Liquid oral medications require translating milligram dosages into exact liquid volume ($mL$) matching specific commercial concentrations (e.g. $40\text{ mg/mL}$ or $80\text{ mg/mL}$).
   - Selecting the wrong dispenser (e.g. measuring $0.3\text{ mL}$ in a $10\text{ mL}$ syringe) is a frequent cause of fatal pediatric under/overdosing.
3. **Hidden Excipient & Formulation Hazards**:
   - Inactive ingredients safe for adults (e.g. propylene glycol, benzyl alcohol, sodium benzoate, sorbitol) cause severe toxicities in neonates and young infants (such as gasping syndrome, kernicterus, lactic acidosis, and hyperosmolality).
   - Commercial solid dosage forms (tablets, capsules) frequently cannot be swallowed by infants or crushed without destroying modified-release delivery mechanisms.
4. **Fragmentation of Specialized Pediatric Formularies**:
   - Official protocols (e.g. **Kinderformularium.nl**, **PedMed.org**, and hospital-specific guidelines like **UZ Gent PHO SCT Guideline #906**) are scattered across external portals, leading to manual lookups and transcription errors.

---

## ⚙️ How the App Works

The system enforces a fundamental safety architecture: **Authoritative guidelines inform the system, while a deterministic Python engine performs all mathematical calculations and clinical safety evaluations.**

```
                                +-------------------------------------------------------+
                                |               Streamlit Clinician UI                  |
                                |  - Patient Cohort Selector / Custom SSIN              |
                                |  - Route (PO, IV, IM) & Clinical Intent Filters       |
                                |  - Autocomplete Substance, Synonym & Brand Search    |
                                |  - Trust Badges, Dosage Cards & Recip-e FHIR Dispatch |
                                +---------------------------+---------------------------+
                                                            |
                           +--------------------------------+-------------------------------+
                           |                                                                |
                           v                                                                v
+-------------------------+-------------------------+            +-------------------------+-------------------------+
|     Patient & FHIR Data Integration Layer         |            |         Clinical Knowledge & Ingestion Layer     |
|  - Belgian UHMEP / Recip-e Mock Server            |            |  - SQLite DB (pediatric_knowledge.db)            |
|  - Patient Demographics: Age, Weight, Height, SCr |            |  - Seeded Protocols (UZ Gent #906, SAMv2, TMF)   |
|  - Live Active Medication Reconciliation          |            |  - Live Kinderformularium 938-monograph catalog  |
|  - Known Drug Allergy & Sensitivity Registry      |            |  - Clinician Approval Workflow for Ingestions    |
+-------------------------+-------------------------+            +-------------------------+-------------------------+
                                                            |
                                                            v
                                +-------------------------------------------------------+
                                |         Deterministic Python Calculation Engine       |
                                |  - BSA (Mosteller) & BMI Computation                  |
                                |  - Bedside Schwartz eGFR (k=0.413) & Renal Staging    |
                                |  - Milligram & Volume Calculations (mg/kg or mg/m²)   |
                                |  - Pediatric Syringe Sizing & Measuring Guidance      |
                                |  - DDI Traffic-Light Conflict & Allergy Checker       |
                                |  - Excipient Age Checks & Hepatic Safety Notes        |
                                +---------------------------+---------------------------+
                                                            |
                                                            v
                                +-------------------------------------------------------+
                                |             Prescription & Output Delivery            |
                                |  - Exact Dosing Breakdown & Administration Guidance   |
                                |  - Commercial SAMv2 Brands (CNK) vs Magistral (TMF)   |
                                |  - One-Click Push to Belgian Recip-e FHIR Barcode     |
                                +-------------------------------------------------------+
```

### 1. Patient Profile & Biometric Derivation
- Select an existing pre-loaded patient from hospital records or enter a custom SSIN.
- Deterministic biometrics computed in real time:
  - **Body Surface Area (BSA)**: Mosteller formula $\text{BSA} = \sqrt{\frac{\text{Height (cm)} \times \text{Weight (kg)}}{3600}}$.
  - **Body Mass Index (BMI)**: $\text{BMI} = \frac{\text{Weight (kg)}}{(\text{Height (m)})^2}$.
  - **Pediatric Renal Function (eGFR)**: Bedside Schwartz equation $\text{eGFR} = \frac{0.413 \times \text{Height (cm)}}{\text{Serum Creatinine (mg/dL)}}$.

### 2. Dual-Layer Knowledge Base & Ingestion
- **Local Clinical Formulary (`pediatric_knowledge.db`)**: Pre-seeded with clinically verified baseline guidelines (UZ Gent Guideline #906, Kinderformularium, PedMed).
- **Search Autocomplete**: Prescribers can search by:
  - **Generic Substance Name** (e.g. *Aciclovir*, *Sulfamethoxazole-Trimethoprim*, *Ursodeoxycholzuur*)
  - **Clinical Synonyms** (e.g. *Cotrimoxazol*, *UDCA*, *Acetaminophen*)
  - **Commercial Brand Names** (e.g. *Bactrim*, *Zovirax*, *Clamoxyl*, *Diflucan*, *Losec*, *Dafalgan*, *Nurofen*, *Rocephin*, *Noxafil*)
- **On-Demand Monograph Ingestion**:
  - Direct integration with all **938 official Kinderformularium monographs**.
  - Ingests structured dosing schedules (`schema.org` microdata), excipient warnings, and organ adjustments.
  - Tagged initially as `🟠 Ingested Monograph — Pending Clinical Validation`, with an in-app **"Approve for Clinic"** workflow allowing clinicians to promote it to `🟢 Clinically Verified Protocol`.

### 3. Safety Screening & Drug-Drug Interactions (DDI)
- **Allergy Guardrails**: Instant contraindication alerts if a prescribed substance conflicts with patient allergies (e.g. Penicillin allergy triggering amoxicillin blocks and recommending safe alternatives like *Azithromycin*).
- **Drug-Drug Interactions (DDI)**: Traffic-light screening against active medications (e.g. Azole antifungals + Tacrolimus/Cyclosporine triggering severe CYP3A4 inhibition alerts and recommending therapeutic drug monitoring).
- **Excipient Toxicity Screening**: Evaluates patient age against formulation excipients (e.g. flagging sorbitol/propylene glycol in *Bactrim* oral suspension for neonates < 2 months and suggesting hospital magistral TMF syrup).
- **Renal Impairment Adjustments**: Dynamically stages eGFR and applies dosing interval extensions or dose factor reductions according to guideline thresholds.

### 4. Deterministic Dosing & Syringe Sizing
- Calculates single doses and total daily doses.
- For oral liquid forms, converts milligrams into milliliters ($mL$) based on commercial or magistral concentrations.
- **Syringe Guidance**: Recommends the exact measuring device to use (e.g., $1.0\text{ mL}$ precision syringe for volumes $<1\text{ mL}$; $3\text{ mL}$, $5\text{ mL}$, or $10\text{ mL}$ oral syringes).

### 5. Belgian Recip-e FHIR Prescribing
- Formats the calculated prescription into a **FHIR R4 `ServiceRequest` / `MedicationRequest`**.
- Submits the prescription to the Belgian **UHMEP / Recip-e Mock Server** (`http://localhost:8000`), generating a validated Belgian prescription barcode (e.g. `BE-RECIPE-XXXXXXXXXXXX`).

---

## 📥 Input Requirements

The system processes two main categories of inputs:

### 1. Patient Data (FHIR / EHR Context)
| Parameter | Unit / Type | Clinical Significance |
| :--- | :--- | :--- |
| **Patient ID / SSIN** | String | Links prescription to patient EHR record. |
| **Age** | Years & Months | Critical for pediatric maturation, age-band dosing, and excipient safety thresholds. |
| **Weight** | Kilograms ($kg$) | Primary basis for $mg/kg$ dosage calculations. |
| **Height** | Centimeters ($cm$) | Required for Mosteller BSA ($m^2$) and Schwartz eGFR calculations. |
| **Gender** | `male` / `female` | Patient identification and demographic reconciliation. |
| **Serum Creatinine** | $mg/dL$ | Used to compute Bedside Schwartz clearance ($mL/min$). |
| **Registered Allergies** | List of strings | Screened for severe immune-mediated contraindications (e.g. `penicillin`). |
| **Active Medications** | List of strings | Screened live for metabolic and pharmacodynamic interactions. |
| **Preferred Route** | `oral`, `iv`, `im` | Doctor or patient route preference. |

### 2. Prescriber Selections (UI Controls)
- **Administration Route**: Multi-select filter (`Oral`, `Intravenous`, `Intramuscular`, or empty for *All Routes*).
- **Clinical Intent**: Dropdown filter (`All`, `Prophylactic`, `Therapeutic`).
- **Medication Query / Selection**: Autocomplete selector matching generic substance, synonym, or brand name.
- **Kinderformularium Ingestion (Optional)**: Selection from the 938-drug catalog or custom URL input to fetch new monographs.

---

## 🚀 Getting Started & Execution

### Prerequisites
- Python 3.10+ (or [Nix](https://nixos.org/) package manager)
- SQLite3

### Quick Start (Single Command)
Run the provided unified launch script, which boots the Belgian Recip-e FHIR Mock Server and the Streamlit app inside the configured environment:

```bash
./run.sh
```

### Manual Execution Steps
If running components individually:

1. **Start the Belgian Recip-e Mock Server**:
   ```bash
   nix-shell --run "python 'Case_Info/2. Pediatric Prescriber/server.py' --port 8000"
   ```
2. **Launch the Streamlit Prescriber Application**:
   ```bash
   nix-shell --run "streamlit run app.py --server.port 8501"
   ```
3. Open your browser at **`http://localhost:8501`**.

---

## 🧪 Automated Testing

The application includes an automated test suite verifying biometrics, renal staging, excipient safety, DDI screening, Kinderformularium parsing, and FHIR integration:

```bash
nix-shell --run "python -m unittest discover -s tests -p 'test_*.py' -v"
```

---

## 📁 Repository Structure

```
├── app.py                            # Main Streamlit clinical dashboard
├── run.sh                            # One-click startup script (Mock server + Streamlit)
├── shell.nix                         # Nix environment specification
├── pediatric_knowledge.db            # Persistent SQLite database for formulary monographs
├── kf_index_cache.json               # Cached 938-drug Kinderformularium catalog index
├── pediatric_dosing_system_plan.md   # Architectural design and project plan
├── src/
│   ├── calculators.py                # Deterministic math: BSA, BMI, Schwartz eGFR, Syringe sizer
│   ├── ddi_engine.py                 # Drug-Drug Interaction and allergy screening engine
│   ├── fhir_client.py                # Belgian Recip-e / UHMEP FHIR API client & patient database
│   ├── knowledge_base.py             # Curated clinical protocols (UZ Gent #906, SAMv2, TMF)
│   ├── knowledge_db.py               # SQLite storage layer, synonym resolver & label formatter
│   ├── models.py                     # Dataclasses (Patient, DrugInfo, DosingRule, CalculationResult)
│   └── scraper.py                    # Kinderformularium 938-drug catalog scraper & microdata parser
├── tests/
│   └── test_prescriber.py            # Comprehensive unit test suite (16 tests)
└── Case_Info/
    └── 2. Pediatric Prescriber/
        ├── server.py                 # Belgian UHMEP / Recip-e Mock Server
        └── Solve - Use case - ...    # Clinical case study documentation
```

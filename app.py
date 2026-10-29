"""Pediatric Medication Prescriber - Streamlit Clinical Application
Designed for pediatricians to calculate exact, safe dosages, avoid administration
errors, screen drug interactions, and push prescriptions to Belgian Recip-e FHIR.
"""

import streamlit as st
from src.calculators import (
    calculate_bsa_mosteller,
    calculate_bmi,
    calculate_bedside_schwartz_egfr,
    evaluate_dosing_rule,
)
from src.ddi_engine import screen_drug_safety
from src.fhir_client import (
    PRELOADED_PATIENTS,
    get_patient_profile,
    push_prescription_to_recipe,
)
from src.knowledge_base import get_clinical_knowledge_base, search_drugs
from src.models import Patient, CalculationResult, DrugInfo, DosingRule

# Page configuration
st.set_page_config(
    page_title="Pediatric Prescriber - Clinical Decision Support",
    page_icon="👶",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for clinical styling and badges
st.markdown(
    """
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #4B5563;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px;
        text-align: center;
    }
    .dose-card {
        background-color: #F0FDF4;
        border: 1px solid #BBF7D0;
        border-radius: 10px;
        padding: 18px;
        margin-bottom: 15px;
    }
    .dose-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: #166534;
        margin-bottom: 8px;
    }
    .syringe-box {
        background-color: #FEF3C7;
        border-left: 4px solid #F59E0B;
        padding: 10px 14px;
        border-radius: 4px;
        margin-top: 10px;
        font-size: 0.95rem;
    }
    .formula-box {
        background-color: #EFF6FF;
        border-left: 4px solid #3B82F6;
        padding: 10px 14px;
        border-radius: 4px;
        margin-top: 10px;
        font-family: monospace;
        font-size: 0.95rem;
    }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">👶 Pediatric Medication Prescriber</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Intelligent Pediatric Dosing, Administration Safety & Belgian Recip-e FHIR Prescribing</div>',
    unsafe_allow_html=True,
)

# -----------------------------------------------------------------------------
# 1. PATIENT ENTRY & CLINICAL PROFILE HEADER
# -----------------------------------------------------------------------------
st.markdown("### 1. Patient Identification & Clinical Biometrics")

col_pat_select, col_pat_custom = st.columns([2, 1])

patient_options = list(PRELOADED_PATIENTS.keys())
with col_pat_select:
    selected_pat_id = st.selectbox(
        "Select Patient ID (Pre-loaded Hospital Cohort):",
        options=patient_options,
        format_func=lambda pid: f"{pid} — {PRELOADED_PATIENTS[pid].name} ({PRELOADED_PATIENTS[pid].weight_kg} kg, {PRELOADED_PATIENTS[pid].age_years}y)",
        index=0,
    )

with col_pat_custom:
    custom_id = st.text_input("Or enter custom Patient SSIN / ID:", placeholder="e.g. pat-custom-007")

effective_patient_id = custom_id.strip() if custom_id else selected_pat_id
patient: Patient = get_patient_profile(effective_patient_id)

# Calculate Biometrics deterministically
bsa_val = calculate_bsa_mosteller(patient.height_cm, patient.weight_kg)
bmi_val = calculate_bmi(patient.height_cm, patient.weight_kg)
egfr_val = calculate_bedside_schwartz_egfr(patient.height_cm, patient.serum_creatinine_mg_dl)

# Render Patient Biometric Dashboard
c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Age", f"{patient.age_years} yrs ({patient.age_months} mo)")
c2.metric("Weight", f"{patient.weight_kg} kg")
c3.metric("Height", f"{patient.height_cm} cm")
c4.metric("BSA (Mosteller)", f"{bsa_val} m²")
c5.metric("BMI", f"{bmi_val} kg/m²")
c6.metric(
    "eGFR (Schwartz)",
    f"{egfr_val} mL/min",
    delta="Normal" if egfr_val >= 60 else "Impaired",
    delta_color="normal" if egfr_val >= 60 else "inverse",
)

# Patient Context Badges
context_cols = st.columns([2, 2])
with context_cols[0]:
    if patient.allergies:
        st.error(f"⚠️ **Registered Allergies / Sensitivities:** {', '.join(patient.allergies).upper()}")
    else:
        st.success("✅ **Allergies:** No known drug allergies (NKDA)")

with context_cols[1]:
    if patient.active_medications:
        st.info(f"💊 **Current Active Medications:** {', '.join(patient.active_medications)}")
    else:
        st.info("💊 **Current Active Medications:** None recorded")

st.divider()

# -----------------------------------------------------------------------------
# 2. SEARCH & CLINICAL INTENT PRE-SELECTION (DROPDOWNS ONLY)
# -----------------------------------------------------------------------------
st.markdown("### 2. Medication Search & Route Preselection")

search_col1, search_col2, search_col3 = st.columns([1.5, 1.5, 2])

with search_col1:
    route_options = ["oral", "intravenous", "intramuscular"]
    selected_routes = st.multiselect(
        "Type of Administration (Leave empty for ALL routes):",
        options=route_options,
        default=[patient.preferred_route] if (patient.preferred_route and patient.preferred_route in route_options) else [],
        format_func=lambda r: {
            "oral": "Oral (PO) - Syrups / Tablets",
            "intravenous": "Intravenous (IV) - Infusions / Vials",
            "intramuscular": "Intramuscular (IM) - Depot Injections",
        }.get(r, r),
        help="Select doctor preference. If none selected, all administration forms will be calculated.",
    )

with search_col2:
    intent_choice = st.selectbox(
        "Clinical Intent:",
        options=["all", "prophylactic", "therapeutic"],
        format_func=lambda i: {
            "all": "All Indications",
            "prophylactic": "Prophylactic (Preventive)",
            "therapeutic": "Therapeutic (Curative)",
        }.get(i, i),
        index=1,
    )

kb = get_clinical_knowledge_base()
drug_names = [drug.substance for drug in kb.values()]

with search_col3:
    selected_substance_name = st.selectbox(
        "Prescribe Substance / Medication (Autocomplete Recommended):",
        options=drug_names,
        index=0,
        help="Type or select generic substance. Commercial brand packaging is mapped automatically below.",
    )

st.divider()

# -----------------------------------------------------------------------------
# 3. RESULTS & DECISION SUPPORT DASHBOARD
# -----------------------------------------------------------------------------
if selected_substance_name:
    drug_key = selected_substance_name.lower().replace(" ", "-")
    drug = kb.get(drug_key)

    if not drug:
        # Fallback search
        matches = search_drugs(selected_substance_name)
        drug = matches[0] if matches else None

    if drug:
        # 3.1 DDI & SAFETY SCREENING BANNER
        st.markdown(f"### 3. Safety Screening: {drug.substance}")
        screen_result = screen_drug_safety(patient, drug)

        if screen_result.status == "CONTRAINDICATED":
            for alert in screen_result.alerts:
                st.error(f"🛑 **{alert['category']}:** {alert['detail']}")
            if screen_result.recommended_alternatives:
                st.warning(
                    f"💡 **Recommended Safe Pediatric Alternatives:** {', '.join(screen_result.recommended_alternatives)}"
                )
        elif screen_result.status == "WARNING":
            for alert in screen_result.alerts:
                st.warning(f"⚠️ **{alert['category']}:** {alert['detail']}")
        else:
            st.success("✅ **Safety Screen Passed:** No contraindications or adverse drug interactions detected.")

        # 3.2 DOSAGE CALCULATION RESULTS
        st.markdown(f"#### 📐 Calculated Dosages for {drug.substance} ({drug.therapeutic_category})")

        # Filter rules based on route preference
        applicable_rules = []
        for r in drug.dosing_rules:
            # Route check
            if selected_routes and r.route.lower() not in [sr.lower() for sr in selected_routes]:
                continue
            # Weight band check
            if r.weight_max_kg and patient.weight_kg > r.weight_max_kg:
                continue
            if r.weight_min_kg and patient.weight_kg <= r.weight_min_kg:
                continue
            # Age band check
            if r.age_max_months and patient.age_months > r.age_max_months:
                continue
            if r.age_min_months and patient.age_months <= r.age_min_months:
                continue
            applicable_rules.append(r)

        if not applicable_rules:
            st.info(f"No specific rule found for selected filters. Displaying standard available routes for {drug.substance}.")
            applicable_rules = drug.dosing_rules

        # Render Dosing Cards (Side-by-side or stacked)
        cols = st.columns(len(applicable_rules)) if len(applicable_rules) <= 3 else [st.container()] * len(applicable_rules)

        for idx, rule in enumerate(applicable_rules):
            calc: CalculationResult = evaluate_dosing_rule(
                patient=patient,
                drug=drug,
                rule=rule,
                bsa=bsa_val,
                egfr=egfr_val,
            )

            target_col = cols[idx] if len(applicable_rules) <= 3 else cols[0]
            with target_col:
                st.markdown(
                    f"""
                <div class="dose-card">
                    <div class="dose-title">📍 {calc.route.upper()} — {calc.form_type.title()}</div>
                    <div style="font-size: 1.5rem; font-weight: 700; color: #1E293B;">
                        {calc.single_dose} {calc.unit}
                    </div>
                    <div style="color: #475569; font-weight: 500;">
                        Schedule: {calc.frequency_text}
                    </div>
                    <div style="color: #64748B; font-size: 0.9rem;">
                        Total Daily Dose: <b>{calc.total_daily_dose} {calc.unit}/day</b>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

                # Syringe & Volume Guidance (Slide 11 error prevention)
                if calc.liquid_volume_ml is not None:
                    st.markdown(
                        f"""
                    <div class="syringe-box">
                        🥄 <b>Liquid Volume to Administer:</b> <span style="font-size: 1.1rem; font-weight: bold; color: #92400E;">{calc.liquid_volume_ml} mL</span> per dose<br>
                        💉 <b>Device Guidance:</b> {calc.recommended_syringe}
                    </div>
                    """,
                        unsafe_allow_html=True,
                    )

                # Deterministic formula breakdown
                st.markdown(
                    f"""
                <div class="formula-box">
                    <b>Rule:</b> {calc.formula_used}<br>
                    <b>Calculation:</b> {calc.math_breakdown}
                </div>
                """,
                    unsafe_allow_html=True,
                )

                # Renal adjustment notice
                if calc.renal_status_note:
                    st.warning(f"⚠️ {calc.renal_status_note}")

                # Quick Prescribe Button for this specific calculated dosage
                btn_key = f"prescribe_{rule.rule_id}_{idx}"
                if st.button(f"📝 Prescribe {calc.single_dose} {calc.unit} {calc.route.title()} (Recip-e)", key=btn_key):
                    # Get primary brand or substance
                    brand_str = calc.commercial_brands[0]["name"] if calc.commercial_brands else calc.substance
                    cnk_str = calc.commercial_brands[0]["cnk"] if calc.commercial_brands else "0042895"
                    dose_summary = f"{calc.single_dose} {calc.unit} {calc.frequency_text}"
                    if calc.liquid_volume_ml:
                        dose_summary += f" ({calc.liquid_volume_ml} mL)"

                    res = push_prescription_to_recipe(
                        patient=patient,
                        substance=calc.substance,
                        calculated_dose_text=dose_summary,
                        brand_name=brand_str,
                        cnk_code=cnk_str,
                        instructions="; ".join(calc.administration_instructions[:2]),
                    )
                    if res["success"]:
                        st.success(
                            f"🎉 **Prescription Generated & Pushed to Recip-e!**\n\n"
                            f"- **Recip-e Barcode:** `{res['recipe_barcode']}`\n"
                            f"- **FHIR ID:** `{res['fhir_id']}`\n"
                            f"- **Status:** `{res['status']}`"
                        )

        st.divider()

        # 3.3 COMMERCIAL BRANDS & MAGISTRAL FORMULATIONS
        col_brands, col_instructions = st.columns([1, 1])

        with col_brands:
            st.markdown("#### 🏢 Commercial Packaging (Belgian SAMv2 / CNK)")
            if drug.brands:
                for b in drug.brands:
                    st.markdown(
                        f"- **{b['name']}**  \n"
                        f"  *CNK:* `{b.get('cnk', 'N/A')}` | *Form:* {b.get('form', 'Standard')} | *Strength:* {b.get('strength', 'N/A')}"
                    )
            else:
                st.info("No direct commercial packaging registered. Hospital magistral preparation required.")

            if drug.magistral_formula:
                st.markdown("#### 🧪 Magistral Formulation (TMF / Hospital Pharmacy)")
                st.markdown(
                    f"""
                > **Hospital Compounding Protocol:**  
                > {drug.magistral_formula}  
                > *(Recommended when commercial packaging cannot deliver pediatric micro-dosing or cannot be swallowed whole)*
                """
                )

        with col_instructions:
            st.markdown("#### 📋 Administration Restrictions & Instructions")
            for inst in drug.administration_instructions:
                st.markdown(f"- ℹ️ {inst}")

            if drug.cautions:
                st.markdown("##### ⚠️ Special Cautions")
                for c in drug.cautions:
                    st.markdown(f"- {c}")

        # 3.4 EXPANDABLE SOURCE CITATION
        with st.expander("📚 Clinical Source Citation & Guideline Traceability"):
            st.markdown(f"**Guideline Title:** {drug.source_citation.get('title', 'Clinical Protocol')}")
            st.markdown(f"**Evidence Level:** {drug.source_citation.get('evidence_level', 'Hospital Validated Guideline')}")
            url = drug.source_citation.get("url")
            if url:
                st.markdown(f"**Official Reference Link:** [{url}]({url})")
            st.caption("Extracted and verified from authoritative pediatric formularies for clinical transparency.")

# Sidebar Information
with st.sidebar:
    st.image("https://img.icons8.com/color/96/pediatrician.png", width=64)
    st.markdown("### Belgian eHealth FHIR Status")
    st.info("Connected to **UHMEP v1.4 Mock Server** (localhost:8000)")
    st.markdown(
        """
    **Active Integrations:**
    - ✅ **Recip-e FHIR R4 ServiceRequest**
    - ✅ **Mosteller BSA & BMI Calculators**
    - ✅ **Bedside Schwartz eGFR (k=0.413)**
    - ✅ **UZ Gent PHO SCT Guideline 906 v10**
    - ✅ **Belgian SAM / CNK Drug Database**
    - ✅ **Syringe Safety Scale Sizer**
    """
    )
    st.divider()
    st.markdown("**Role Simulation:** `prescriber` (Dr. Jean Dupont)")

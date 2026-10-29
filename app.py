"""Pediatric Medication Prescriber - Streamlit Clinical Application
Designed for pediatricians to calculate exact, safe dosages, avoid administration
errors, screen drug interactions, and push prescriptions to Belgian Recip-e FHIR.
"""

import streamlit as st
from typing import Optional, List, Dict
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
from src.knowledge_db import (
    init_db,
    get_drug_from_db,
    list_drugs_from_db,
    get_all_substance_names_from_db,
    approve_drug_in_db,
    format_drug_search_label,
)
from src.scraper import crawl_and_ingest_drug, fetch_kinderformularium_index
from src.models import Patient, CalculationResult, DrugInfo, DosingRule

# Initialize SQLite database on app load
init_db()

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

search_col1, search_col2, search_col3 = st.columns([1.3, 1.2, 2.5])

with search_col1:
    route_options = ["oral", "intravenous", "intramuscular"]
    pref_hint = f" (Patient preferred: {patient.preferred_route.upper()})" if patient.preferred_route else ""
    selected_routes = st.multiselect(
        f"Type of Administration{pref_hint}:",
        options=route_options,
        default=[],
        placeholder="All routes (PO, IV, IM)",
        format_func=lambda r: {
            "oral": "Oral (PO) - Syrups / Tablets",
            "intravenous": "Intravenous (IV) - Infusions / Vials",
            "intramuscular": "Intramuscular (IM) - Depot Injections",
        }.get(r, r),
        help="Filter formulary and dosing calculations by administration route. Leave empty to show all routes.",
    )

with search_col2:
    intent_choice = st.selectbox(
        "Clinical Intent:",
        options=["all", "prophylactic", "therapeutic"],
        format_func=lambda i: {
            "all": "All Indications (Prophylactic & Therapeutic)",
            "prophylactic": "Prophylactic (Preventive)",
            "therapeutic": "Therapeutic (Curative)",
        }.get(i, i),
        index=0,
    )

# Dynamically filter drugs from SQLite database by route and clinical intent
filtered_drugs = list_drugs_from_db(
    route_filter=selected_routes if selected_routes else None,
    intent_filter=intent_choice,
)
if not filtered_drugs:
    st.warning("No local medications match the selected route/intent filters. Showing all formulary substances.")
    filtered_drugs = list_drugs_from_db()

db_substances = [d.substance for d in filtered_drugs]
drug_label_map = {d.substance: format_drug_search_label(d) for d in filtered_drugs}

# Maintain selected substance across reruns (e.g. after ingesting a new drug)
default_sub_idx = 0
if "selected_substance" in st.session_state and st.session_state["selected_substance"] in db_substances:
    default_sub_idx = db_substances.index(st.session_state["selected_substance"])

with search_col3:
    selected_substance_name = st.selectbox(
        "Search by Generic Substance, Synonym, or Commercial Brand:",
        options=db_substances,
        index=default_sub_idx if db_substances else None,
        format_func=lambda s: drug_label_map.get(s, s),
        help="Type any substance (e.g., Aciclovir), synonym (e.g., Cotrimoxazol, UDCA), or brand (e.g., Bactrim, Zovirax, Dafalgan, Nurofen, Clamoxyl, Diflucan).",
    )
    if selected_substance_name:
        st.session_state["selected_substance"] = selected_substance_name


@st.cache_data(ttl=3600, show_spinner=False)
def get_cached_kf_catalog() -> List[Dict]:
    return fetch_kinderformularium_index()


# Dynamic on-demand crawler / ingestion section with full 938-drug Kinderformularium catalog
with st.expander("🌐 Search & Ingest New Substance from Kinderformularium (938 Pediatric Monographs)"):
    st.caption(
        "Search all 938 official Kinderformularium pediatric monographs by generic substance or brand name, or paste a direct URL:"
    )
    kf_catalog = get_cached_kf_catalog()
    kf_col1, kf_col2 = st.columns([3, 1])

    with kf_col1:
        if kf_catalog:
            kf_options = [
                f"{item.get('generic_name', '')}"
                + (f" — Brands: {item.get('branded_name')}" if item.get("branded_name") else "")
                for item in kf_catalog
            ]
            selected_kf_idx = st.selectbox(
                "1️⃣ Select from Kinderformularium Catalog (Type Generic or Brand Name):",
                options=range(len(kf_catalog)),
                format_func=lambda i: kf_options[i],
                index=0,
                key="kf_catalog_selectbox",
            )
        else:
            selected_kf_idx = None
        new_drug_input = st.text_input(
            "2️⃣ Or type a custom drug name / Kinderformularium URL:",
            placeholder="e.g. Azitromycine, Zithromax, Augmentin, Ventolin, or https://www.kinderformularium.nl/geneesmiddel/...",
        )

    with kf_col2:
        st.write("")
        if kf_catalog and st.button("📥 Ingest Selected Catalog Drug", use_container_width=True):
            chosen_entry = kf_catalog[selected_kf_idx]
            target_name = chosen_entry.get("generic_name", "")
            with st.spinner(f"Crawling & parsing {target_name} from Kinderformularium..."):
                ingested = crawl_and_ingest_drug(target_name)
                if ingested:
                    st.session_state["selected_substance"] = ingested.substance
                    st.success(f"✓ Ingested **{ingested.substance}** as `AI_EXTRACTED`!")
                    st.rerun()
                else:
                    st.error(f"Could not fetch or parse '{target_name}'.")

        if st.button("📥 Ingest Custom Name / URL", use_container_width=True):
            if new_drug_input.strip():
                with st.spinner(f"Crawling & parsing '{new_drug_input.strip()}'..."):
                    ingested = crawl_and_ingest_drug(new_drug_input.strip())
                    if ingested:
                        st.session_state["selected_substance"] = ingested.substance
                        st.success(f"✓ Ingested **{ingested.substance}** as `AI_EXTRACTED`!")
                        st.rerun()
                    else:
                        st.error(f"Could not find or parse '{new_drug_input.strip()}' on Kinderformularium.")
            else:
                st.warning("Enter a drug name or URL in box 2️⃣ above, or use button 1️⃣.")

st.divider()

# -----------------------------------------------------------------------------
# 3. RESULTS & DECISION SUPPORT DASHBOARD
# -----------------------------------------------------------------------------
if selected_substance_name:
    drug: Optional[DrugInfo] = get_drug_from_db(selected_substance_name)

    if drug:
        # 3.0 TRUST & TRANSPARENCY VERIFICATION BANNER
        st.markdown(f"### 3. Safety Screening: {drug.substance}")

        if drug.verification_status == "CLINICALLY_VERIFIED":
            st.markdown(
                f"""
                <div style="background-color: #F0FDF4; border: 1px solid #86EFAC; border-left: 5px solid #22C55E; padding: 12px 16px; border-radius: 6px; margin-bottom: 15px;">
                    <b style="color: #166534; font-size: 1.05rem;">🟢 Clinically Verified Protocol</b><br>
                    <span style="color: #15803D; font-size: 0.9rem;">
                        Verified by: <b>{drug.verified_by or 'Hospital Clinical Pharmacist'}</b> |
                        Verified at: <i>{drug.verified_at or 'Hospital Protocol'}</i> |
                        Source: <i>{drug.source_citation.get('title', 'Clinical Formulary')}</i>
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            col_v1, col_v2 = st.columns([3, 1])
            with col_v1:
                st.markdown(
                    f"""
                    <div style="background-color: #FFFBEB; border: 1px solid #FCD34D; border-left: 5px solid #F59E0B; padding: 12px 16px; border-radius: 6px; margin-bottom: 15px;">
                        <b style="color: #92400E; font-size: 1.05rem;">🟠 Ingested Monograph — Pending Clinical Validation</b><br>
                        <span style="color: #B45309; font-size: 0.9rem;">
                            Extracted automatically by Kinderformularium crawler. Dosing and limits must be verified by prescriber prior to dispensing.
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with col_v2:
                if st.button("✅ Approve for Clinic", key=f"btn_approve_{drug.substance}", use_container_width=True):
                    approve_drug_in_db(drug.substance, "Dr. Jean Dupont (Attending Pediatrician)")
                    st.success("Protocol clinically approved!")
                    st.rerun()

        # 3.1 DDI & SAFETY SCREENING
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

                # Excipient toxicity warning (Neonatal / Infant safety)
                if calc.excipient_alerts:
                    for exc in calc.excipient_alerts:
                        st.error(
                            f"🚫 **Toxic Excipient Alert ({exc['excipient']}):** {exc['risk']}  \n"
                            f"👉 *Action:* {exc['action']}"
                        )

                # Hepatic guidance notice
                if calc.hepatic_status_note:
                    st.info(f"🩺 **Hepatic Guidance:** {calc.hepatic_status_note}")

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

            if drug.hepatic_adjustments:
                st.markdown("##### 🩺 Hepatic Impairment Adjustments")
                for h in drug.hepatic_adjustments:
                    st.markdown(f"- **{h.get('condition')}:** {h.get('instruction')}")

            if drug.excipient_warnings:
                st.markdown("##### 🧪 Pediatric Excipient Safety Registry")
                for ex in drug.excipient_warnings:
                    min_age = ex.get('min_age_months', 0)
                    st.markdown(f"- **{ex.get('excipient')}:** {ex.get('risk')} *(Contraindicated in age < {min_age} months)*")

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

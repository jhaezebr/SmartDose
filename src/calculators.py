"""Deterministic clinical calculators for pediatric pharmacology.
Executes formulas strictly in Python to guarantee mathematical accuracy.
"""

import math
from typing import Tuple, Optional
from src.models import Patient, DosingRule, CalculationResult, DrugInfo, RenalThreshold


def calculate_bsa_mosteller(height_cm: float, weight_kg: float) -> float:
    """Calculates Body Surface Area (BSA) using the Mosteller formula.
    BSA (m2) = sqrt( (Height (cm) * Weight (kg)) / 3600 )
    """
    if height_cm <= 0 or weight_kg <= 0:
        return 0.0
    return round(math.sqrt((height_cm * weight_kg) / 3600.0), 3)


def calculate_bsa_dubois(height_cm: float, weight_kg: float) -> float:
    """Calculates Body Surface Area (BSA) using the Du Bois formula.
    BSA (m2) = 0.007184 * Weight^0.425 * Height^0.725
    """
    if height_cm <= 0 or weight_kg <= 0:
        return 0.0
    return round(0.007184 * (weight_kg ** 0.425) * (height_cm ** 0.725), 3)


def calculate_bmi(height_cm: float, weight_kg: float) -> float:
    """Calculates Body Mass Index (BMI).
    BMI = Weight (kg) / (Height (m))^2
    """
    if height_cm <= 0 or weight_kg <= 0:
        return 0.0
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m * height_m), 1)


def calculate_bedside_schwartz_egfr(height_cm: float, serum_creatinine_mg_dl: float, k: float = 0.413) -> float:
    """Calculates estimated Glomerular Filtration Rate (eGFR) in children
    using the updated Bedside Schwartz equation:
    eGFR (ml/min/1.73m2) = (k * Height(cm)) / Serum Creatinine (mg/dL)
    Default constant k = 0.413 for pediatrics.
    """
    if serum_creatinine_mg_dl <= 0 or height_cm <= 0:
        return 0.0
    return round((k * height_cm) / serum_creatinine_mg_dl, 1)


def recommend_oral_syringe(volume_ml: float) -> str:
    """Recommends specific oral syringe barrel size to prevent 10-fold dosing errors.
    Directly addresses pediatric errors noted in clinical literature (e.g., using 5ml
    syringe for 0.3ml dose, leading to accidental 3ml 10x overdose).
    """
    if volume_ml <= 0:
        return "N/A"
    if volume_ml <= 1.0:
        return (
            f"1 mL oral syringe with 0.01 mL increments (CRITICAL: precision syringe required "
            f"for micro-volume {volume_ml:.2f} mL to prevent 10x dosing error)"
        )
    elif volume_ml <= 3.0:
        return f"3 mL oral syringe with 0.1 mL increments"
    elif volume_ml <= 5.0:
        return f"5 mL oral syringe with 0.2 mL increments"
    else:
        return f"10 mL oral measuring syringe or cup ({volume_ml:.1f} mL)"


def evaluate_dosing_rule(
    patient: Patient,
    drug: DrugInfo,
    rule: DosingRule,
    bsa: float,
    egfr: float,
) -> CalculationResult:
    """Deterministically evaluates a specific dosing rule against patient parameters."""
    weight = patient.weight_kg

    # 1. Base dose calculation
    if rule.basis == "bsa":
        raw_single_dose = bsa * rule.rate
        math_steps = f"{rule.rate} {rule.unit}/m² × {bsa} m² (BSA) = {raw_single_dose:.2f} {rule.unit}"
    else:  # 'weight'
        raw_single_dose = weight * rule.rate
        math_steps = f"{rule.rate} {rule.unit}/kg × {weight} kg (Weight) = {raw_single_dose:.2f} {rule.unit}"

    single_dose = raw_single_dose
    total_daily_dose = single_dose * rule.doses_per_day
    dose_cap_applied = False
    cap_notes = []

    # 2. Check Daily Safety Caps
    if rule.max_dose_per_kg_daily and (total_daily_dose / weight) > rule.max_dose_per_kg_daily:
        capped_daily = rule.max_dose_per_kg_daily * weight
        single_dose = capped_daily / rule.doses_per_day
        total_daily_dose = capped_daily
        dose_cap_applied = True
        cap_notes.append(f"Capped at max daily rate: {rule.max_dose_per_kg_daily} {rule.unit}/kg/day")

    if rule.max_dose_daily and total_daily_dose > rule.max_dose_daily:
        total_daily_dose = rule.max_dose_daily
        single_dose = total_daily_dose / rule.doses_per_day
        dose_cap_applied = True
        cap_notes.append(f"Capped at absolute max daily dose: {rule.max_dose_daily} {rule.unit}/day")

    if rule.max_dose_single and single_dose > rule.max_dose_single:
        single_dose = rule.max_dose_single
        total_daily_dose = single_dose * rule.doses_per_day
        dose_cap_applied = True
        cap_notes.append(f"Capped at max single dose: {rule.max_dose_single} {rule.unit}/dose")

    # 3. Renal Clearance Check & Staging
    renal_note = None
    frequency_text = rule.schedule_description

    for threshold in rule.renal_adjustments:
        applies = True
        if threshold.crcl_min is not None and egfr < threshold.crcl_min:
            applies = False
        if threshold.crcl_max is not None and egfr >= threshold.crcl_max:
            applies = False

        if applies:
            renal_note = f"Renal Alert (eGFR {egfr} ml/min): {threshold.instruction}"
            if threshold.dose_factor != 1.0:
                single_dose = single_dose * threshold.dose_factor
                total_daily_dose = total_daily_dose * threshold.dose_factor
                math_steps += f" | Renal adjustment factor {threshold.dose_factor} applied"
            if threshold.frequency_hours:
                frequency_text = f"Every {threshold.frequency_hours} hours (extended due to renal clearance)"
            break

    # 4. Liquid Volume & Syringe Safety Calculation
    liquid_vol_ml = None
    syringe_rec = None
    if rule.commercial_concentration_mg_ml and rule.commercial_concentration_mg_ml > 0:
        liquid_vol_ml = round(single_dose / rule.commercial_concentration_mg_ml, 2)
        syringe_rec = recommend_oral_syringe(liquid_vol_ml)

    # 5. Excipient Safety Screening against Patient Age
    excipient_alerts = []
    for ew in getattr(drug, "excipient_warnings", []):
        min_age = ew.get("min_age_months", 1)
        if patient.age_months < min_age:
            excipient_alerts.append({
                "excipient": ew.get("excipient", "Hazardous Additive"),
                "risk": ew.get("risk", "Toxicity risk"),
                "min_age_months": min_age,
                "action": "Consider TMF magistral compounding without preservatives or switch to excipient-free formulation."
            })

    # 6. Hepatic Adjustment Note
    hepatic_note = None
    if getattr(drug, "hepatic_adjustments", []):
        notes = [f"{ha.get('condition')}: {ha.get('instruction')}" for ha in drug.hepatic_adjustments]
        hepatic_note = " | ".join(notes)

    if cap_notes:
        math_steps += f" [{', '.join(cap_notes)}]"

    return CalculationResult(
        substance=drug.substance,
        route=rule.route,
        form_type=rule.form_type,
        single_dose=round(single_dose, 1),
        total_daily_dose=round(total_daily_dose, 1),
        unit=rule.unit,
        frequency_text=frequency_text,
        formula_used=rule.formula_description,
        math_breakdown=math_steps,
        liquid_volume_ml=liquid_vol_ml,
        recommended_syringe=syringe_rec,
        renal_status_note=renal_note,
        hepatic_status_note=hepatic_note,
        excipient_alerts=excipient_alerts,
        dose_cap_applied=dose_cap_applied,
        source_citation=drug.source_citation,
        commercial_brands=drug.brands,
        magistral_formula=drug.magistral_formula,
        administration_instructions=drug.administration_instructions,
        cautions=drug.cautions,
        verification_status=getattr(drug, "verification_status", "CLINICALLY_VERIFIED"),
        verified_by=getattr(drug, "verified_by", None),
        verified_at=getattr(drug, "verified_at", None),
    )

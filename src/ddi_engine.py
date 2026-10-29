"""Drug-Drug Interaction (DDI) & Allergy Screening Engine.
Provides traffic-light safety assessments for pediatric prescriptions.
"""

from typing import List
from src.models import Patient, DrugInfo, DDIScreenResult


def screen_drug_safety(patient: Patient, drug: DrugInfo) -> DDIScreenResult:
    """Evaluates potential drug-drug interactions, patient allergies, and contraindications."""
    alerts = []
    recommended_alternatives = []
    substance_lower = drug.substance.lower()

    # 1. ALLERGY SCREENING (RED - CONTRAINDICATION)
    patient_allergies = [a.lower() for a in patient.allergies]

    if "penicillin" in patient_allergies or "penicilline" in patient_allergies:
        if substance_lower in ["penicilline", "amoxicilline", "ampicilline", "augmentin"]:
            alerts.append({
                "severity": "RED",
                "category": "Allergy Alert",
                "detail": (
                    f"STRICT CONTRAINDICATION: Patient has a documented Penicillin / Beta-lactam allergy! "
                    f"Prescribing {drug.substance} carries high risk of severe hypersensitivity / anaphylaxis."
                )
            })
            recommended_alternatives.extend([
                "Azithromycine (10 mg/kg 3x/week P.O.)",
                "Clarithromycine (7.5 mg/kg 1x/day P.O. - max 500 mg/dose)",
                "Levofloxacine (500 mg 1x/day if adolescent)"
            ])

    if "sulfa" in patient_allergies or "sulfonamide" in patient_allergies:
        if substance_lower in ["sulfamethoxazole-trimethoprim", "cotrimoxazol", "bactrim"]:
            alerts.append({
                "severity": "RED",
                "category": "Allergy Alert",
                "detail": (
                    "STRICT CONTRAINDICATION: Documented Sulfonamide allergy! "
                    "Cannot administer Bactrim / Sulfamethoxazole-Trimethoprim."
                )
            })
            recommended_alternatives.append("Dapsone 2 mg/kg/day in 1 single dose (verify G-6-PD status first)")

    if "nsaid" in patient_allergies or "ibuprofen" in patient_allergies:
        if substance_lower in ["ibuprofen", "brufen", "ketorolac", "diclofenac"]:
            alerts.append({
                "severity": "RED",
                "category": "Allergy Alert",
                "detail": "Patient has documented NSAID sensitivity. Avoid prescribing NSAIDs."
            })
            recommended_alternatives.append("Paracetamol (15 mg/kg/dose Q6H)")

    # 2. DRUG-DRUG INTERACTIONS (ACTIVE MEDICATIONS)
    active_meds = [m.lower() for m in patient.active_medications]

    # Azoles (Fluconazole, Posaconazole) CYP3A4 interactions
    if substance_lower in ["fluconazole", "posaconazole"]:
        for med in active_meds:
            if any(term in med for term in ["tacrolimus", "prograf", "ciclosporin", "sandimmun", "sirolimus"]):
                alerts.append({
                    "severity": "AMBER",
                    "category": "CYP3A4 Inhibition Warning",
                    "detail": (
                        f"Potent CYP3A4 interaction with {med}. Azoles significantly increase calcineurin "
                        f"inhibitor plasma levels. Close therapeutic drug monitoring (TDM trough levels) required."
                    )
                })
            if any(term in med for term in ["corticosteroid", "prednisolone", "medrol", "dexamethasone"]):
                alerts.append({
                    "severity": "AMBER",
                    "category": "Pharmacodynamic Interaction",
                    "detail": (
                        f"Concomitant use with {med}. Prophylactic antifungal duration is extended during "
                        f"immunosuppressive corticosteroid therapy (UZ Gent Protocol 6.2.2)."
                    )
                })

    # Nephrotoxicity Synergism
    if substance_lower in ["aciclovir", "vancomycine", "gentamicine", "tobramycine"]:
        for med in active_meds:
            if any(nephro in med for nephro in ["ibuprofen", "brufen", "amikacine", "gentamicine", "cisplatin"]):
                alerts.append({
                    "severity": "AMBER",
                    "category": "Nephrotoxicity Synergy",
                    "detail": (
                        f"Combined nephrotoxic burden with {med}. Maintain vigorous hydration and monitor "
                        f"serum creatinine / eGFR closely."
                    )
                })

    # SMZ-TMP and Methotrexate interaction
    if substance_lower == "sulfamethoxazole-trimethoprim":
        for med in active_meds:
            if "methotrexaat" in med or "methotrexate" in med:
                alerts.append({
                    "severity": "RED",
                    "category": "Severe Toxicity Risk",
                    "detail": (
                        "CO-ADMINISTRATION HAZARD: SMZ-TMP displaces Methotrexate from albumin binding sites "
                        "and decreases renal excretion, risking lethal bone marrow aplasia. Do not combine."
                    )
                })

    # Determine overall status
    if any(a["severity"] == "RED" for a in alerts):
        overall_status = "CONTRAINDICATED"
    elif any(a["severity"] == "AMBER" for a in alerts):
        overall_status = "WARNING"
    else:
        overall_status = "SAFE"

    return DDIScreenResult(
        status=overall_status,
        alerts=alerts,
        recommended_alternatives=recommended_alternatives
    )

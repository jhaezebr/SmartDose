"""Authoritative Clinical Knowledge Base for Pediatric Medication Dosing.
Ingested directly from:
1. UZ Gent PHO SCT Richtlijn #906 v10 (Pediatrische Hemato-Oncologie)
2. Kinderformularium.nl (Dutch/Belgian Pediatric Formularies)
3. PedMed.org (Paediatric Clinical Reference Monographs)
4. Belgian SAMv2 & APB (Belgian Drug Database & CNK Codes)
"""

from typing import Dict, List, Optional
from src.models import DrugInfo, DosingRule, RenalThreshold


def get_clinical_knowledge_base() -> Dict[str, DrugInfo]:
    """Returns the comprehensive clinical database of pediatric drugs."""
    db: Dict[str, DrugInfo] = {}

    # 1. ACICLOVIR (ZOVIRAX)
    db["aciclovir"] = DrugInfo(
        substance="Aciclovir",
        atc_code="J05AB01",
        therapeutic_category="Antiviral (HSV & VZV Prophylaxis / Treatment)",
        intent="both",
        brands=[
            {"name": "Zovirax 400 mg / 5 mL Suspensie", "cnk": "0042887", "form": "Oral suspension (100 mL flacon)", "strength": "80 mg/mL"},
            {"name": "Zovirax 200 mg / 5 mL Suspensie", "cnk": "0042879", "form": "Oral suspension (100 mL flacon)", "strength": "40 mg/mL"},
            {"name": "Zovirax 200 mg Comprimés (deelbaar)", "cnk": "0042853", "form": "Divisible tablets (box of 25)", "strength": "200 mg"},
            {"name": "Zovirax 800 mg Comprimés (deelbaar)", "cnk": "0801233", "form": "Divisible tablets (box of 35)", "strength": "800 mg"},
            {"name": "Zovirax 250 mg Flacon IV", "cnk": "0042861", "form": "Powder for IV infusion (vial)", "strength": "250 mg/flacon"},
            {"name": "Aciclovir Sandoz 800 mg", "cnk": "1542109", "form": "Generisch tablet", "strength": "800 mg"}
        ],
        magistral_formula="Aciclovir 200 mg/5 mL orale suspensie TMF (bij onbeschikbaarheid van commerciële Zovirax suspensie)",
        administration_instructions=[
            "Drink plenty of fluids during treatment to prevent precipitation and crystal formation in renal tubules.",
            "Oral suspension should be shaken well before use.",
            "Can be taken with or without food. If stomach upset occurs, administer with meals.",
            "Divisible tablets can be halved or crushed and dispersed in water for children unable to swallow whole pills."
        ],
        cautions=[
            "Nephrotoxicity risk increases when combined with other nephrotoxic agents (aminoglycosides, tacrolimus, cyclosporine).",
            "Adjust dosage interval in renal insufficiency based on creatinine clearance (eGFR)."
        ],
        source_citation={
            "title": "UZ Gent Richtlijn 906 v10 (PHO SCT) / Kinderformularium.nl / PedMed.org",
            "url": "https://www.kinderformularium.nl/geneesmiddel/105/aciclovir-oraal-en-intraveneus",
            "evidence_level": "Level 1A - Hospital Protocol & International Pediatric Formularies"
        },
        excipient_warnings=[
            {"excipient": "Sorbitol & Parabens (Zovirax suspensie)", "risk": "GI intolerance and hyperosmolality in young neonates", "min_age_months": 1}
        ],
        hepatic_adjustments=[
            {"condition": "Severe hepatic dysfunction", "instruction": "No primary dose reduction required; monitor for neurotoxicity in advanced hepatic encephalopathy"}
        ],
        dosing_rules=[
            # Oral - Prophylactic (Children < 40 kg)
            DosingRule(
                rule_id="aciclovir-oral-proph-lt40kg",
                route="oral",
                form_type="syrup/suspension",
                formula_description="3 × 250 mg/m² / dose P.O. (Weight < 40 kg)",
                basis="bsa",
                rate=250.0,
                unit="mg",
                doses_per_day=3,
                schedule_description="3 times daily (every 8 hours) orally",
                weight_max_kg=40.0,
                max_dose_per_kg_daily=80.0,
                max_dose_daily=4000.0,
                commercial_concentration_mg_ml=80.0,  # Zovirax 400mg/5ml = 80 mg/ml
                available_strengths=["400 mg / 5 mL (80 mg/mL)", "200 mg / 5 mL (40 mg/mL)"],
                renal_adjustments=[
                    RenalThreshold(crcl_min=25, crcl_max=50, instruction="Dose Q12H (every 12 hours) instead of Q8H", frequency_hours=12, dose_factor=1.0),
                    RenalThreshold(crcl_min=10, crcl_max=25, instruction="Dose Q24H (every 24 hours) instead of Q8H", frequency_hours=24, dose_factor=1.0),
                    RenalThreshold(crcl_max=10, instruction="Give 50% of recommended dose every 24 hours", frequency_hours=24, dose_factor=0.5)
                ]
            ),
            # Oral - Prophylactic (Adolescents & Adults > 40 kg)
            DosingRule(
                rule_id="aciclovir-oral-proph-gt40kg",
                route="oral",
                form_type="tablet/capsule",
                formula_description="2 × 250 mg/m² / dose P.O. (Weight > 40 kg)",
                basis="bsa",
                rate=250.0,
                unit="mg",
                doses_per_day=2,
                schedule_description="2 times daily (every 12 hours) orally",
                weight_min_kg=40.0,
                max_dose_per_kg_daily=80.0,
                max_dose_daily=4000.0,
                available_strengths=["200 mg comp", "800 mg comp"],
                renal_adjustments=[
                    RenalThreshold(crcl_min=25, crcl_max=50, instruction="Dose Q12H", frequency_hours=12, dose_factor=1.0),
                    RenalThreshold(crcl_min=10, crcl_max=25, instruction="Dose Q24H", frequency_hours=24, dose_factor=1.0),
                    RenalThreshold(crcl_max=10, instruction="Give 50% of recommended dose every 24 hours", frequency_hours=24, dose_factor=0.5)
                ]
            ),
            # IV - Conditioning / Prophylactic (< 40 kg)
            DosingRule(
                rule_id="aciclovir-iv-proph-lt40kg",
                route="intravenous",
                form_type="injection",
                formula_description="3 × 250 mg/m² / dose IV (Weight < 40 kg)",
                basis="bsa",
                rate=250.0,
                unit="mg",
                doses_per_day=3,
                schedule_description="3 times daily (every 8 hours) IV infusion over 1 hour",
                weight_max_kg=40.0,
                max_dose_per_kg_daily=60.0,
                available_strengths=["Flacon IV 250 mg"],
                renal_adjustments=[
                    RenalThreshold(crcl_min=25, crcl_max=50, instruction="Give recommended dose every 12 hours", frequency_hours=12, dose_factor=1.0),
                    RenalThreshold(crcl_min=10, crcl_max=25, instruction="Give recommended dose every 24 hours", frequency_hours=24, dose_factor=1.0),
                    RenalThreshold(crcl_max=10, instruction="Give 50% of recommended dose every 24 hours", frequency_hours=24, dose_factor=0.5)
                ]
            ),
            # IV - Conditioning / Prophylactic (> 40 kg)
            DosingRule(
                rule_id="aciclovir-iv-proph-gt40kg",
                route="intravenous",
                form_type="injection",
                formula_description="2 × 250 mg/m² / dose IV (Weight > 40 kg)",
                basis="bsa",
                rate=250.0,
                unit="mg",
                doses_per_day=2,
                schedule_description="2 times daily (every 12 hours) IV infusion over 1 hour",
                weight_min_kg=40.0,
                max_dose_per_kg_daily=60.0,
                available_strengths=["Flacon IV 250 mg"],
                renal_adjustments=[
                    RenalThreshold(crcl_min=25, crcl_max=50, instruction="Give recommended dose every 12 hours", frequency_hours=12, dose_factor=1.0),
                    RenalThreshold(crcl_min=10, crcl_max=25, instruction="Give recommended dose every 24 hours", frequency_hours=24, dose_factor=1.0),
                    RenalThreshold(crcl_max=10, instruction="Give 50% of recommended dose every 24 hours", frequency_hours=24, dose_factor=0.5)
                ]
            )
        ]
    )

    # 2. FLUCONAZOLE (DIFLUCAN)
    db["fluconazole"] = DrugInfo(
        substance="Fluconazole",
        atc_code="J02AC01",
        therapeutic_category="Antifungal (Azole)",
        intent="both",
        brands=[
            {"name": "Diflucan 200 mg / 5 mL Orale Suspensie", "cnk": "1456383", "form": "Poeder voor orale suspensie", "strength": "40 mg/mL"},
            {"name": "Diflucan 50 mg / 5 mL Orale Suspensie", "cnk": "0045120", "form": "Poeder voor orale suspensie", "strength": "10 mg/mL"},
            {"name": "Diflucan 50 mg Capsules", "cnk": "0045096", "form": "Gelules (box of 10)", "strength": "50 mg"},
            {"name": "Diflucan 200 mg Capsules", "cnk": "0045104", "form": "Gelules (box of 20)", "strength": "200 mg"},
            {"name": "Diflucan 2 mg/mL Flacon IV (100 mL)", "cnk": "0045138", "form": "Infusion solution", "strength": "200 mg/flacon"},
            {"name": "Fluconazole Sandoz 200 mg", "cnk": "2019487", "form": "Generic capsules", "strength": "200 mg"}
        ],
        magistral_formula="Fluconazole 10 mg/mL siroop TMF (bij slikproblemen of lage gewichten)",
        administration_instructions=[
            "Can be taken with or without food.",
            "Shake oral suspension thoroughly for 10 seconds before administering.",
            "Once reconstituted, suspension is stable for 14 days at room temperature."
        ],
        cautions=[
            "Significant CYP3A4 inhibitor: monitor concomitant medications (calcineurin inhibitors, vincristine, steroids).",
            "Prolongs QT interval: caution with other QT-prolonging drugs."
        ],
        source_citation={
            "title": "UZ Gent Richtlijn 906 v10 PHO SCT / Kinderformularium.nl",
            "url": "https://www.kinderformularium.nl/geneesmiddel/92/fluconazol",
            "evidence_level": "Level 1A Guideline Protocol"
        },
        excipient_warnings=[
            {"excipient": "Sodium benzoate (Diflucan poeder voor suspensie)", "risk": "Bilirubin displacement from albumin / risk of kernicterus in neonates", "min_age_months": 1}
        ],
        hepatic_adjustments=[
            {"condition": "Significant hepatic impairment (Child-Pugh B/C or Bilirubin > 3x ULN)", "instruction": "Reduce daily maintenance dose by 50% and closely monitor transaminases"}
        ],
        dosing_rules=[
            # Oral / IV: Children 6 months to 13 years
            DosingRule(
                rule_id="fluconazole-po-iv-6m-13y",
                route="oral",
                form_type="syrup/suspension",
                formula_description="6 mg/kg/day in 1 single daily dose (PO or IV)",
                basis="weight",
                rate=6.0,
                unit="mg",
                doses_per_day=1,
                schedule_description="Once daily in 1 single dose",
                age_min_months=6,
                age_max_months=156,  # 13 years
                max_dose_daily=400.0,
                commercial_concentration_mg_ml=40.0,  # 200mg/5ml = 40mg/ml
                available_strengths=["200 mg / 5 mL (40 mg/mL)", "50 mg / 5 mL (10 mg/mL)"],
                renal_adjustments=[
                    RenalThreshold(crcl_min=11, crcl_max=50, instruction="Reduce daily dose by 50%", dose_factor=0.5),
                    RenalThreshold(crcl_max=10, instruction="Reduce daily dose by 50% and monitor trough levels", dose_factor=0.5)
                ]
            ),
            # Oral / IV: Adolescents > 13 years
            DosingRule(
                rule_id="fluconazole-po-iv-gt13y",
                route="oral",
                form_type="tablet/capsule",
                formula_description="400 mg once daily (Adolescents > 13 years)",
                basis="weight",
                rate=0.0,  # Fixed dose evaluated in logic
                unit="mg",
                doses_per_day=1,
                schedule_description="Once daily",
                age_min_months=156,
                max_dose_daily=400.0,
                available_strengths=["200 mg caps (2 capsules)", "50 mg caps"],
                renal_adjustments=[
                    RenalThreshold(crcl_min=11, crcl_max=50, instruction="Reduce daily dose to 200 mg/day (50%)", dose_factor=0.5),
                    RenalThreshold(crcl_max=10, instruction="Reduce daily dose to 200 mg/day (50%)", dose_factor=0.5)
                ]
            ),
            # IV Infusion
            DosingRule(
                rule_id="fluconazole-iv",
                route="intravenous",
                form_type="injection",
                formula_description="6 mg/kg/day IV (Max 400 mg/day)",
                basis="weight",
                rate=6.0,
                unit="mg",
                doses_per_day=1,
                schedule_description="Once daily IV infusion over 30-60 minutes",
                max_dose_daily=400.0,
                available_strengths=["Diflucan 2 mg/mL flacon IV"]
            )
        ]
    )

    # 3. SULFAMETHOXAZOLE + TRIMETHOPRIM (SMZ-TMP / BACTRIM / EUSAPRIM)
    db["sulfamethoxazole-trimethoprim"] = DrugInfo(
        substance="Sulfamethoxazole-Trimethoprim",
        atc_code="J01EE01",
        therapeutic_category="Antibacterial (Pneumocystis jirovecii Prophylaxis)",
        intent="both",
        brands=[
            {"name": "Bactrim Suspensie 200mg/40mg per 5 mL", "cnk": "0040576", "form": "Oral suspension (100 mL)", "strength": "40 mg SMZ + 8 mg TMP / mL"},
            {"name": "Bactrim Forte Comprimés (800mg SMZ / 160mg TMP)", "cnk": "0040568", "form": "Tablets (box of 30)", "strength": "160 mg TMP"},
            {"name": "Eusaprim Suspensie 200mg/40mg per 5 mL", "cnk": "0046276", "form": "Oral suspension", "strength": "40 mg SMZ + 8 mg TMP / mL"}
        ],
        magistral_formula="Co-trimoxazol siroop conform TMF",
        administration_instructions=[
            "Administer on 2 consecutive days per week (e.g., Saturday and Sunday) for prophylaxis.",
            "Take with plenty of fluid to minimize crystal precipitation.",
            "Shake suspension well before measuring."
        ],
        cautions=[
            "Contraindicated in severe sulfa allergy or proven G-6-PD deficiency.",
            "In renal failure: Ccr <30 ml/min -> half dose; Ccr <15 ml/min -> STOP Bactrim.",
            "If allergy or intolerance occurs, switch to Dapsone 2 mg/kg/day (after G-6-PD screening)."
        ],
        source_citation={
            "title": "UZ Gent Richtlijn 906 v10 PHO SCT (Pneumocystis Prophylaxis)",
            "url": "https://www.kinderformularium.nl/geneesmiddel/314/cotrimoxazol-sulfamethoxazol-trimethoprim",
            "evidence_level": "Level 1A Guideline Protocol"
        },
        excipient_warnings=[
            {"excipient": "Sorbitol & Propylene glycol (Bactrim suspensie)", "risk": "Hyperosmolality, lactic acidosis, and sulfonamide-induced kernicterus in neonates", "min_age_months": 2}
        ],
        hepatic_adjustments=[
            {"condition": "Severe acute hepatitis / severe hepatic parenchyma necrosis", "instruction": "CONTRAINDICATED"}
        ],
        dosing_rules=[
            DosingRule(
                rule_id="smz-tmp-oral-proph",
                route="oral",
                form_type="syrup/suspension",
                formula_description="5 mg (TMP)/kg/day in 2 divided doses on 2 consecutive days/week (e.g. Sat-Sun)",
                basis="weight",
                rate=2.5,  # 2.5 mg TMP per dose x 2 doses = 5 mg TMP/kg/day
                unit="mg TMP",
                doses_per_day=2,
                schedule_description="Twice daily on 2 consecutive days per week (Sat & Sun)",
                max_dose_daily=320.0,  # Max 320 mg TMP/day (equiv to 2 Bactrim Forte)
                commercial_concentration_mg_ml=8.0,  # Bactrim suspension has 40mg SMZ + 8mg TMP per ml
                available_strengths=["Bactrim siroop (8 mg TMP / mL)", "Bactrim Forte comp (160 mg TMP)"],
                renal_adjustments=[
                    RenalThreshold(crcl_min=15, crcl_max=30, instruction="Reduce dose by 50% (CrCl 15-30 ml/min)", dose_factor=0.5),
                    RenalThreshold(crcl_max=15, instruction="CONTRAINDICATED / STOP Bactrim (CrCl < 15 ml/min)", dose_factor=0.0)
                ]
            )
        ]
    )
    db["cotrimoxazol"] = db["sulfamethoxazole-trimethoprim"]

    # 4. URSODEOXYCHOLZUUR (URSOFALK / URSOCHOL)
    db["ursodeoxycholzuur"] = DrugInfo(
        substance="Ursodeoxycholzuur",
        atc_code="A05AA02",
        therapeutic_category="Hepatoprotective (VOD / SOS Prophylaxis in SCT)",
        intent="prophylactic",
        brands=[
            {"name": "Ursofalk 250 mg Capsules", "cnk": "0049213", "form": "Hard capsules (box of 50)", "strength": "250 mg"},
            {"name": "Ursofalk 500 mg Comprimés pelliculés", "cnk": "2498269", "form": "Tablets (box of 50)", "strength": "500 mg"},
            {"name": "Ursochol 150 mg Comprimés", "cnk": "0049205", "form": "Divisible tablets", "strength": "150 mg"}
        ],
        magistral_formula="Ursochol Orale Suspensie 30 mg/mL (Magistrale bereiding ziekenhuisapotheek TMF - essentieel voor kinderen < 20 kg die geen capsules kunnen slikken)",
        administration_instructions=[
            "Administer with meals or milk to improve tolerability and absorption.",
            "Capsules must not be chewed. For young children, use magistral 30 mg/mL oral suspension.",
            "Treatment continues from start of conditioning up to 3 months post-transplant."
        ],
        cautions=[
            "Monitor liver enzymes (bilirubin, ALAT, ASAT) periodically.",
            "Do not administer concomitantly with aluminum hydroxide antacids (reduces absorption)."
        ],
        source_citation={
            "title": "UZ Gent Richtlijn 906 v10 PHO SCT (Sectie 6.2.6)",
            "url": "https://www.kinderformularium.nl/geneesmiddel/54/ursodeoxycholzuur",
            "evidence_level": "Level 1A Pediatric Protocol"
        },
        excipient_warnings=[],
        hepatic_adjustments=[
            {"condition": "Complete biliary tract obstruction / Acute cholecystitis", "instruction": "CONTRAINDICATED"}
        ],
        dosing_rules=[
            DosingRule(
                rule_id="urso-oral-sct-proph",
                route="oral",
                form_type="syrup/suspension",
                formula_description="150 mg/m²/day in 2 divided doses P.O.",
                basis="bsa",
                rate=75.0,  # 75 mg/m2 per dose x 2 doses = 150 mg/m2/day
                unit="mg",
                doses_per_day=2,
                schedule_description="Twice daily (morning and evening with food)",
                commercial_concentration_mg_ml=30.0,  # Magistral 30 mg/ml
                available_strengths=["Magistrale suspensie 30 mg/mL", "Ursofalk 250 mg caps", "Ursochol 150 mg comp"]
            )
        ]
    )

    # 5. PENICILLINE (FENOXYMETHYLPENICILLINE / BENZATHINE PENICILLINE)
    db["penicilline"] = DrugInfo(
        substance="Penicilline",
        atc_code="J01CE02",
        therapeutic_category="Antibacterial (Pneumococcal Prophylaxis Post-SCT)",
        intent="prophylactic",
        brands=[
            {"name": "Infectocillin 500.000 IE / 5 mL Siroop", "cnk": "0456123", "form": "Oral solution (100 mL)", "strength": "100.000 IE/mL"},
            {"name": "Peni-Oral 1.000.000 IE Comprimés", "cnk": "0043125", "form": "Tablets (box of 20)", "strength": "1.000.000 IE"},
            {"name": "Penadur LA (Benzathine Penicilline) 1.200.000 IE Flacon IM", "cnk": "0042994", "form": "Depot injection IM", "strength": "1.200.000 IE/vial"}
        ],
        magistral_formula="Fenoxymethylpenicilline kalium siroop TMF",
        administration_instructions=[
            "Take oral penicillin 1 hour before or 2 hours after meals with water.",
            "Shake syrup well before administration.",
            "For IM depot injection (Penadur LA): administer strictly deep intramuscularly in gluteal muscle (NOT intravenously)."
        ],
        cautions=[
            "STRICT CONTRAINDICATION in confirmed Penicillin / Beta-lactam IgE allergy.",
            "Allergy Alternative: Switch to Azithromycine (10 mg/kg 3x/week) or Clarithromycine (7.5 mg/kg 1x/day)."
        ],
        source_citation={
            "title": "UZ Gent Richtlijn 906 v10 PHO SCT (Sectie 6.3 Penicilline)",
            "url": "https://www.kinderformularium.nl/geneesmiddel/32935/fenoxymethylpenicilline",
            "evidence_level": "Level 1A Protocol"
        },
        excipient_warnings=[
            {"excipient": "Potassium salts & Sodium benzoate (Infectocillin siroop)", "risk": "Electrolyte load in neonates < 1 month", "min_age_months": 1}
        ],
        hepatic_adjustments=[
            {"condition": "Combined severe hepatic and renal impairment", "instruction": "Extend dosing intervals; primary excretion is renal but hepatic pathway becomes rate-limiting"}
        ],
        dosing_rules=[
            # Oral Penicillin: 50,000 IE/kg/day in 3 doses
            DosingRule(
                rule_id="penicillin-oral-sct",
                route="oral",
                form_type="syrup/suspension",
                formula_description="50.000 IE/kg/day in 3 divided doses P.O.",
                basis="weight",
                rate=16666.7,  # 50,000 / 3 per dose
                unit="IE",
                doses_per_day=3,
                schedule_description="3 times daily (every 8 hours) on an empty stomach",
                commercial_concentration_mg_ml=100000.0,  # 500,000 IE per 5 ml = 100,000 IE/ml
                available_strengths=["Infectocillin 500.000 IE / 5 mL", "Peni-Oral 1.000.000 IE comp"]
            ),
            # IM Long-acting (< 12 years / < 30 kg): 1/2 flacon = 600,000 IE per 4 weeks
            DosingRule(
                rule_id="penicillin-im-lt12y",
                route="intramuscular",
                form_type="injection",
                formula_description="600.000 IE IM every 4 weeks (1/2 flacon Penadur LA) for < 12y or < 30 kg",
                basis="weight",
                rate=0.0,  # Fixed dose
                unit="IE",
                doses_per_day=1,
                schedule_description="Once every 4 weeks strictly deep intramuscularly",
                weight_max_kg=30.0,
                age_max_months=144,
                available_strengths=["Penadur LA 1.200.000 IE (half flacon = 600.000 IE)"]
            ),
            # IM Long-acting (> 12 years / > 30 kg): 1 flacon = 1,200,000 IE per 4 weeks
            DosingRule(
                rule_id="penicillin-im-gt12y",
                route="intramuscular",
                form_type="injection",
                formula_description="1.200.000 IE IM every 4 weeks (1 flacon Penadur LA) for > 12y or > 30 kg",
                basis="weight",
                rate=0.0,
                unit="IE",
                doses_per_day=1,
                schedule_description="Once every 4 weeks strictly deep intramuscularly",
                weight_min_kg=30.0,
                available_strengths=["Penadur LA 1.200.000 IE flacon"]
            )
        ]
    )

    # 6. AMOXICILLINE (CLAMOXYL / AMOXICILLINE SANDOZ)
    db["amoxicilline"] = DrugInfo(
        substance="Amoxicilline",
        atc_code="J01CA04",
        therapeutic_category="Antibacterial (Penicillin Alternative / Prophylaxis)",
        intent="both",
        brands=[
            {"name": "Clamoxyl 250 mg / 5 mL Orale Suspensie", "cnk": "0042796", "form": "Powder for oral suspension (100 mL)", "strength": "50 mg/mL"},
            {"name": "Clamoxyl 500 mg / 5 mL Orale Suspensie", "cnk": "0042804", "form": "Powder for oral suspension (100 mL)", "strength": "100 mg/mL"},
            {"name": "Amoxicilline Sandoz 1000 mg Comprimés (deelbaar)", "cnk": "0042895", "form": "Dispersible/divisible tablets", "strength": "1000 mg"},
            {"name": "Amoxicilline EG 500 mg Gélules", "cnk": "1689405", "form": "Capsules", "strength": "500 mg"}
        ],
        magistral_formula="Amoxicilline 50 mg/mL siroop TMF",
        administration_instructions=[
            "Can be taken with or without food.",
            "Reconstituted suspension must be kept in refrigerator and discarded after 10-14 days.",
            "Tablets can be dissolved in water or divided along score lines."
        ],
        cautions=[
            "CONTRAINDICATED in patients with verified penicillin / beta-lactam hypersensitivity.",
            "Adjust dose in severe renal impairment."
        ],
        source_citation={
            "title": "UZ Gent Richtlijn 906 v10 / Kinderformularium.nl",
            "url": "https://www.kinderformularium.nl/geneesmiddel/7/amoxicilline",
            "evidence_level": "Level 1A Guideline Protocol"
        },
        excipient_warnings=[
            {"excipient": "Sodium benzoate (Clamoxyl poeder voor suspensie)", "risk": "Bilirubin displacement in neonates < 1 month", "min_age_months": 1}
        ],
        hepatic_adjustments=[
            {"condition": "Hepatic dysfunction / History of amoxicillin-associated jaundice", "instruction": "Monitor hepatic enzymes carefully"}
        ],
        dosing_rules=[
            # Standard Prophylaxis Children < 6y: 10 mg/kg 2x/day
            DosingRule(
                rule_id="amoxicillin-proph-lt6y",
                route="oral",
                form_type="syrup/suspension",
                formula_description="10 mg/kg 2x/day P.O. (Children < 6 years)",
                basis="weight",
                rate=10.0,
                unit="mg",
                doses_per_day=2,
                schedule_description="Twice daily (morning and evening)",
                age_max_months=72,  # 6 years
                max_dose_daily=500.0,
                commercial_concentration_mg_ml=50.0,  # Clamoxyl 250mg/5ml
                available_strengths=["Clamoxyl 250 mg / 5 mL (50 mg/mL)"]
            ),
            # Standard Prophylaxis Children 6-11y: 250 mg 2x/day
            DosingRule(
                rule_id="amoxicillin-proph-6-11y",
                route="oral",
                form_type="tablet/capsule",
                formula_description="250 mg 2x/day P.O. (Children 6-11 years)",
                basis="weight",
                rate=0.0,  # Fixed
                unit="mg",
                doses_per_day=2,
                schedule_description="Twice daily (morning and evening)",
                age_min_months=72,
                age_max_months=143,
                available_strengths=["Amoxicilline 500 mg (1/2 comp 2x/d)", "Clamoxyl 250 mg / 5 mL"]
            ),
            # Adolescents & Adults ≥ 12y: 500 mg 2x/day
            DosingRule(
                rule_id="amoxicillin-proph-gt12y",
                route="oral",
                form_type="tablet/capsule",
                formula_description="500 mg 2x/day P.O. (Adolescents & Adults)",
                basis="weight",
                rate=0.0,  # Fixed
                unit="mg",
                doses_per_day=2,
                schedule_description="Twice daily",
                age_min_months=144,
                available_strengths=["Amoxicilline 500 mg comp", "Amoxicilline 1000 mg (1/2 comp)"]
            )
        ]
    )

    # 7. POSACONAZOLE (NOXAFIL)
    db["posaconazole"] = DrugInfo(
        substance="Posaconazole",
        atc_code="J02AC04",
        therapeutic_category="Broad-Spectrum Antifungal Prophylaxis",
        intent="both",
        brands=[
            {"name": "Noxafil 100 mg Gastro-resistant Tablets", "cnk": "3145679", "form": "Gastro-resistant tablets", "strength": "100 mg"},
            {"name": "Noxafil 40 mg/mL Oral Suspension", "cnk": "2389120", "form": "Oral suspension (unregistered in BE, pediatric convention reimbursement)", "strength": "40 mg/mL"},
            {"name": "Noxafil 300 mg Concentrate for IV Infusion", "cnk": "3145687", "form": "Vial IV", "strength": "300 mg/flacon"}
        ],
        magistral_formula="Posaconazole verpulverde tabletten suspensie (Ziekenhuisapotheek protocol: wetenschappelijke studies tonen bruikbare plasmaspiegels in kinderen ondanks officiële SPC restrictie)",
        administration_instructions=[
            "Tablets MUST be swallowed whole with food or a nutritional supplement.",
            "DO NOT crush or chew standard commercial gastro-resistant tablets in ambulatory care.",
            "If child cannot swallow tablets: obtain Noxafil 40 mg/mL oral suspension via Pediatric Oncology Convention or specialized hospital compounding."
        ],
        cautions=[
            "Strong CYP3A4 inhibitor: severe interaction with vinca alkaloids, tacrolimus, cyclosporine, sirolimus.",
            "Therapeutic drug monitoring (TDM trough levels) recommended."
        ],
        source_citation={
            "title": "Case Study Slide 8 / Pediatric Oncology Convention / Kinderformularium.nl",
            "url": "https://www.kinderformularium.nl/geneesmiddel/3113/posaconazol",
            "evidence_level": "Level 1B Expert Consensus"
        },
        excipient_warnings=[
            {"excipient": "Sodium benzoate & Polysorbate 80 (Noxafil suspensie)", "risk": "Not recommended in infants < 3 months; risk of displacement of bilirubin and accumulation", "min_age_months": 3}
        ],
        hepatic_adjustments=[
            {"condition": "Child-Pugh Class B or C (Moderate to Severe Hepatic Impairment)", "instruction": "Posaconazole exposure is increased; monitor TDM plasma trough concentrations and liver function enzymes frequently"}
        ],
        dosing_rules=[
            DosingRule(
                rule_id="posaconazole-tablet-proph",
                route="oral",
                form_type="tablet/capsule",
                formula_description="300 mg once daily (Day 1: 300 mg BID loading dose)",
                basis="weight",
                rate=0.0,
                unit="mg",
                doses_per_day=1,
                schedule_description="Once daily with food",
                weight_min_kg=35.0,
                available_strengths=["Noxafil 100 mg gastro-resistant tablets (3 tablets OD)"]
            )
        ]
    )

    # 8. ESOMEPRAZOLE / OMEPRAZOLE
    db["omeprazole"] = DrugInfo(
        substance="Omeprazole",
        atc_code="A02BC01",
        therapeutic_category="Proton Pump Inhibitor (Gastric Protection)",
        intent="prophylactic",
        brands=[
            {"name": "Omeprazol Sandoz 20 mg Capsules", "cnk": "1654326", "form": "Enteric-coated capsules", "strength": "20 mg"},
            {"name": "Losec Mups 20 mg Comprimés", "cnk": "1512391", "form": "Dispersible tablets", "strength": "20 mg"}
        ],
        magistral_formula="Omeprazole 2 mg/mL orale suspensie met natriumbicarbonaat TMF (voor jonge kinderen en toediening via maagsonde)",
        administration_instructions=[
            "Administer 30 minutes before breakfast.",
            "Capsules may be opened and pellets mixed with apple sauce or water, but NEVER crushed or chewed.",
            "For gastric tube administration: use magistral sodium bicarbonate suspension to prevent clogging."
        ],
        cautions=["Prolonged use may decrease absorption of iron and vitamin B12."],
        source_citation={
            "title": "UZ Gent Richtlijn 906 v10 PHO SCT (Sectie 6.2.3)",
            "url": "https://www.kinderformularium.nl/geneesmiddel/56/omeprazol",
            "evidence_level": "Level 1A Protocol"
        },
        excipient_warnings=[
            {"excipient": "Sucrose / Lactose pellets (Omeprazol capsules)", "risk": "Check for rare hereditary fructose or galactose intolerance in neonates", "min_age_months": 1}
        ],
        hepatic_adjustments=[
            {"condition": "Severe hepatic impairment (Child-Pugh Class C)", "instruction": "Elimination half-life prolonged (approx 3h); maximum daily dose of 10-20 mg/day is recommended"}
        ],
        dosing_rules=[
            DosingRule(
                rule_id="omeprazole-oral-susp",
                route="oral",
                form_type="syrup/suspension",
                formula_description="1 mg/kg once daily P.O.",
                basis="weight",
                rate=1.0,
                unit="mg",
                doses_per_day=1,
                schedule_description="Once daily before morning feeding",
                max_dose_daily=40.0,
                commercial_concentration_mg_ml=2.0,  # Magistral 2mg/ml
                available_strengths=["Magistrale suspensie 2 mg/mL", "Omeprazol 20 mg caps (pellets)"]
            ),
            DosingRule(
                rule_id="omeprazole-iv-lt40kg",
                route="intravenous",
                form_type="injection",
                formula_description="0.5 mg/kg once daily IV (Weight < 40 kg)",
                basis="weight",
                rate=0.5,
                unit="mg",
                doses_per_day=1,
                schedule_description="Once daily IV injection over 5 minutes",
                weight_max_kg=40.0,
                max_dose_daily=20.0,
                available_strengths=["Omeprazol 40 mg flacon IV"]
            ),
            DosingRule(
                rule_id="omeprazole-iv-gt40kg",
                route="intravenous",
                form_type="injection",
                formula_description="20 mg once daily IV (Weight > 40 kg)",
                basis="weight",
                rate=0.0,
                unit="mg",
                doses_per_day=1,
                schedule_description="Once daily IV injection",
                weight_min_kg=40.0,
                max_dose_daily=20.0,
                available_strengths=["Omeprazol 40 mg flacon IV"]
            )
        ]
    )

    return db


def search_drugs(query: str, route_filter: Optional[List[str]] = None, intent_filter: Optional[str] = None) -> List[DrugInfo]:
    """Searches the knowledge base with optional route and intent filters."""
    kb = get_clinical_knowledge_base()
    q = query.strip().lower() if query else ""
    matches = []
    seen = set()

    for key, drug in kb.items():
        if drug.substance in seen:
            continue
        # Match substance name or brand names
        name_match = (q in drug.substance.lower()) or (q in drug.therapeutic_category.lower())
        if not name_match:
            for b in drug.brands:
                if q in b["name"].lower():
                    name_match = True
                    break

        if not name_match and q != "":
            continue

        # Intent filter
        if intent_filter and intent_filter.lower() != "all":
            if drug.intent != "both" and drug.intent.lower() != intent_filter.lower():
                continue

        # Route filter
        if route_filter and len(route_filter) > 0:
            drug_routes = {rule.route.lower() for rule in drug.dosing_rules}
            req_routes = {r.lower() for r in route_filter}
            if not drug_routes.intersection(req_routes):
                continue

        seen.add(drug.substance)
        matches.append(drug)

    return matches

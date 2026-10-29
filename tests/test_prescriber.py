"""Automated test suite for Pediatric Prescriber calculations, DDI, and FHIR integration."""

import unittest
from src.calculators import (
    calculate_bsa_mosteller,
    calculate_bsa_dubois,
    calculate_bmi,
    calculate_bedside_schwartz_egfr,
    recommend_oral_syringe,
    evaluate_dosing_rule,
)
from src.ddi_engine import screen_drug_safety
from src.fhir_client import get_patient_profile, push_prescription_to_recipe
from src.knowledge_base import get_clinical_knowledge_base, search_drugs


class TestPediatricCalculators(unittest.TestCase):

    def test_bsa_mosteller(self):
        # 112 cm, 18.5 kg -> sqrt(112 * 18.5 / 3600) = sqrt(2072 / 3600) = sqrt(0.57555) = 0.759 m2
        bsa = calculate_bsa_mosteller(112.0, 18.5)
        self.assertAlmostEqual(bsa, 0.759, places=2)

    def test_bmi(self):
        # 18.5 kg, 1.12 m -> 18.5 / (1.12^2) = 14.7 kg/m2
        bmi = calculate_bmi(112.0, 18.5)
        self.assertAlmostEqual(bmi, 14.7, places=1)

    def test_bedside_schwartz_egfr(self):
        # Normal child: 112 cm, 0.45 mg/dL -> 0.413 * 112 / 0.45 = 102.8 ml/min
        egfr_normal = calculate_bedside_schwartz_egfr(112.0, 0.45)
        self.assertGreater(egfr_normal, 90.0)

        # Impaired child (Elena): 98 cm, 1.15 mg/dL -> 0.413 * 98 / 1.15 = 35.2 ml/min
        egfr_impaired = calculate_bedside_schwartz_egfr(98.0, 1.15)
        self.assertAlmostEqual(egfr_impaired, 35.2, places=1)

    def test_syringe_recommendation(self):
        # Micro volume < 1 ml should require 1 ml precision syringe
        s1 = recommend_oral_syringe(0.3)
        self.assertIn("1 mL oral syringe", s1)
        self.assertIn("CRITICAL: precision syringe required", s1)

        # 2.3 ml should require 3 ml syringe
        s2 = recommend_oral_syringe(2.3)
        self.assertIn("3 mL oral syringe", s2)

        # 4.5 ml should require 5 ml syringe
        s3 = recommend_oral_syringe(4.5)
        self.assertIn("5 mL oral syringe", s3)


class TestClinicalDosingEngine(unittest.TestCase):

    def setUp(self):
        self.kb = get_clinical_knowledge_base()

    def test_aciclovir_prophylaxis_calculation(self):
        patient = get_patient_profile("pat-1001-jane-doe")
        self.assertIsNotNone(patient)

        drug = self.kb["aciclovir"]
        rule = drug.dosing_rules[0]  # Oral < 40 kg

        bsa = calculate_bsa_mosteller(patient.height_cm, patient.weight_kg)
        egfr = calculate_bedside_schwartz_egfr(patient.height_cm, patient.serum_creatinine_mg_dl)

        res = evaluate_dosing_rule(patient, drug, rule, bsa, egfr)

        # Dose = 250 mg/m2 * ~0.759 m2 = ~189.7 mg
        self.assertAlmostEqual(res.single_dose, 189.7, delta=5.0)
        self.assertEqual(res.unit, "mg")
        # Liquid volume = ~189.7 / 80 mg/ml = ~2.37 ml
        self.assertIsNotNone(res.liquid_volume_ml)
        self.assertAlmostEqual(res.liquid_volume_ml, 2.37, delta=0.2)
        # Syringe should be 3 mL
        self.assertIn("3 mL", res.recommended_syringe)

    def test_renal_adjustment_staging(self):
        # Elena has renal impairment (eGFR ~35 ml/min)
        patient = get_patient_profile("pat-1003-elena-vandenberg")
        drug = self.kb["aciclovir"]
        rule = drug.dosing_rules[0]

        bsa = calculate_bsa_mosteller(patient.height_cm, patient.weight_kg)
        egfr = calculate_bedside_schwartz_egfr(patient.height_cm, patient.serum_creatinine_mg_dl)

        res = evaluate_dosing_rule(patient, drug, rule, bsa, egfr)
        # Should have renal alert adjusting to Q12H
        self.assertIsNotNone(res.renal_status_note)
        self.assertIn("Q12H", res.renal_status_note)


class TestDDIScreening(unittest.TestCase):

    def setUp(self):
        self.kb = get_clinical_knowledge_base()

    def test_penicillin_allergy_contraindication(self):
        # Marc Willems has penicillin allergy
        patient = get_patient_profile("pat-1002-marc-willems")
        drug = self.kb["amoxicilline"]

        screen = screen_drug_safety(patient, drug)
        self.assertEqual(screen.status, "CONTRAINDICATED")
        self.assertTrue(any("Penicillin" in a["detail"] for a in screen.alerts))
        # Should recommend alternatives: Azithromycin or Clarithromycin
        self.assertTrue(any("Azithromycine" in alt for alt in screen.recommended_alternatives))

    def test_cyp3a4_interaction_warning(self):
        # Emma Peeters is on Tacrolimus; prescribing Fluconazole should yield CYP3A4 warning
        patient = get_patient_profile("pat-1005-emma-peeters")
        drug = self.kb["fluconazole"]

        screen = screen_drug_safety(patient, drug)
        self.assertEqual(screen.status, "WARNING")
        self.assertTrue(any("CYP3A4" in a["category"] for a in screen.alerts))


class TestRecipeFHIRPrescription(unittest.TestCase):

    def test_push_prescription(self):
        patient = get_patient_profile("pat-1001-jane-doe")
        result = push_prescription_to_recipe(
            patient=patient,
            substance="Aciclovir",
            calculated_dose_text="190 mg TID PO (2.4 mL)",
            brand_name="Zovirax 400 mg / 5 mL Suspensie",
            cnk_code="0042887",
            instructions="Shake well. Keep well hydrated.",
        )
        self.assertTrue(result["success"])
        self.assertTrue(result["recipe_barcode"].startswith("BE-RECIPE-"))
        self.assertIsNotNone(result["fhir_id"])


class TestOfficialReferenceLinks(unittest.TestCase):

    def test_canonical_kinderformularium_urls(self):
        kb = get_clinical_knowledge_base()
        expected_urls = {
            "cotrimoxazol": "https://www.kinderformularium.nl/geneesmiddel/314/cotrimoxazol-sulfamethoxazol-trimethoprim",
            "aciclovir": "https://www.kinderformularium.nl/geneesmiddel/105/aciclovir-oraal-en-intraveneus",
            "fluconazole": "https://www.kinderformularium.nl/geneesmiddel/92/fluconazol",
            "ursodeoxycholzuur": "https://www.kinderformularium.nl/geneesmiddel/54/ursodeoxycholzuur",
            "penicilline": "https://www.kinderformularium.nl/geneesmiddel/32935/fenoxymethylpenicilline",
            "amoxicilline": "https://www.kinderformularium.nl/geneesmiddel/7/amoxicilline",
            "posaconazole": "https://www.kinderformularium.nl/geneesmiddel/3113/posaconazol",
            "omeprazole": "https://www.kinderformularium.nl/geneesmiddel/56/omeprazol",
        }
        for drug_key, expected_url in expected_urls.items():
            self.assertIn(drug_key, kb, f"Drug key {drug_key} missing in KB")
            citation = kb[drug_key].source_citation
            self.assertIsNotNone(citation)
            self.assertEqual(
                citation.get("url"),
                expected_url,
                f"URL mismatch for {drug_key}: got {citation.get('url')}, expected {expected_url}"
            )


if __name__ == "__main__":
    unittest.main()

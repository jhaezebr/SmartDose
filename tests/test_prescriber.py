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


class TestKnowledgeDBAndLifecycle(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
        from src.knowledge_db import init_db
        init_db(self.temp_db)

    def tearDown(self):
        import os
        if os.path.exists(self.temp_db):
            os.remove(self.temp_db)

    def test_db_seeding_and_retrieval(self):
        from src.knowledge_db import get_drug_from_db, list_drugs_from_db, get_all_substance_names_from_db
        drugs = list_drugs_from_db(db_path=self.temp_db)
        self.assertGreaterEqual(len(drugs), 8)

        names = get_all_substance_names_from_db(db_path=self.temp_db)
        self.assertIn("Aciclovir", names)
        self.assertIn("Sulfamethoxazole-Trimethoprim", names)

        drug = get_drug_from_db("Aciclovir", db_path=self.temp_db)
        self.assertIsNotNone(drug)
        self.assertEqual(drug.substance, "Aciclovir")
        self.assertEqual(drug.verification_status, "CLINICALLY_VERIFIED")

    def test_approval_lifecycle(self):
        from src.knowledge_db import save_drug_to_db, get_drug_from_db, approve_drug_in_db
        from src.scraper import crawl_and_ingest_drug

        # Ingest an unverified drug
        ingested = crawl_and_ingest_drug("paracetamol", db_path=self.temp_db)
        self.assertIsNotNone(ingested)
        self.assertEqual(ingested.verification_status, "AI_EXTRACTED")

        # Doctor approves drug
        success = approve_drug_in_db("Paracetamol", "Dr. Jean Dupont", db_path=self.temp_db)
        self.assertTrue(success)

        # Check updated status in DB
        approved_drug = get_drug_from_db("Paracetamol", db_path=self.temp_db)
        self.assertEqual(approved_drug.verification_status, "CLINICALLY_VERIFIED")
        self.assertEqual(approved_drug.verified_by, "Dr. Jean Dupont")
        self.assertIsNotNone(approved_drug.verified_at)

    def test_synonym_and_brand_search(self):
        from src.knowledge_db import get_drug_from_db, list_drugs_from_db, format_drug_search_label

        # Synonym lookup: Cotrimoxazol -> Sulfamethoxazole-Trimethoprim
        cotrim = get_drug_from_db("Cotrimoxazol", db_path=self.temp_db)
        self.assertIsNotNone(cotrim)
        self.assertEqual(cotrim.substance, "Sulfamethoxazole-Trimethoprim")

        # Brand lookup: Bactrim -> Sulfamethoxazole-Trimethoprim, Zovirax -> Aciclovir
        bactrim = get_drug_from_db("Bactrim", db_path=self.temp_db)
        self.assertIsNotNone(bactrim)
        self.assertEqual(bactrim.substance, "Sulfamethoxazole-Trimethoprim")

        zovirax = get_drug_from_db("Zovirax", db_path=self.temp_db)
        self.assertIsNotNone(zovirax)
        self.assertEqual(zovirax.substance, "Aciclovir")

        # List search by synonym and brand
        matches_syn = list_drugs_from_db(query="cotrimoxazol", db_path=self.temp_db)
        self.assertEqual(len(matches_syn), 1)
        self.assertEqual(matches_syn[0].substance, "Sulfamethoxazole-Trimethoprim")

        matches_brand = list_drugs_from_db(query="Clamoxyl", db_path=self.temp_db)
        self.assertEqual(len(matches_brand), 1)
        self.assertEqual(matches_brand[0].substance, "Amoxicilline")

        # Formatted label contains substance, synonym, and brand
        label = format_drug_search_label(cotrim)
        self.assertIn("Sulfamethoxazole-Trimethoprim", label)
        self.assertIn("Cotrimoxazol", label)
        self.assertIn("Bactrim", label)

    def test_route_and_intent_filtering(self):
        from src.knowledge_db import list_drugs_from_db

        im_drugs = list_drugs_from_db(route_filter=["intramuscular"], db_path=self.temp_db)
        self.assertTrue(any(d.substance == "Penicilline" for d in im_drugs))
        self.assertFalse(any(d.substance == "Ursodeoxycholzuur" for d in im_drugs))

        proph_drugs = list_drugs_from_db(intent_filter="prophylactic", db_path=self.temp_db)
        self.assertTrue(any(d.substance == "Ursodeoxycholzuur" for d in proph_drugs))

    def test_kinderformularium_html_parser(self):
        from src.scraper import parse_kinderformularium_html

        sample_kf_html = """
        <html>
        <body>
            <h3>Azitromycine</h3>
            <h3>Azitromycine</h3>
            <h3>MACROLIDEN</h3>
            <h4>Beschikbare toedieningsvormen/sterktes</h4>
            <p>Poeder voor orale suspensie 40 mg/ml, Tablet 250 mg, 500 mg</p>
            <h4>Ongewenste hulpstoffen</h4>
            <p>Bevat propyleenglycol en natriumbenzoaat in sommige dranken.</p>
            <h4>Doseringen</h4>
            <table class="large-12 medium-12 small-12 dosage">
              <thead>
                <tr itemscope itemtype="http://schema.org/MedicalIndication">
                  <th><span itemprop="name">Luchtweginfectie</span></th>
                </tr>
              </thead>
              <tbody>
                <tr><td><ul>
                  <li><strong itemprop="administrationRoute">Oraal</strong>
                    <ul>
                      <li itemscope itemtype="http://schema.org/DoseSchedule">
                        <strong><div itemprop="targetPopulation">1 maand tot 18 jaar</div></strong>
                        <ul>
                          <li>
                            <span itemprop="doseValue">10</span>
                            <span itemprop="doseUnit">mg/kg/dag,</span>
                            <span itemprop="frequency">in 1 dosis. Maximaal 500 mg per dag.</span>
                          </li>
                        </ul>
                      </li>
                    </ul>
                  </li>
                </ul></td></tr>
              </tbody>
            </table>
            <h4>Contraindicaties bij kinderen</h4>
            <p>Ernstige leverfunctiestoornis.</p>
        </body>
        </html>
        """
        parsed = parse_kinderformularium_html(
            sample_kf_html,
            "https://www.kinderformularium.nl/geneesmiddel/21/azitromycine",
            index_entry={"id": 21, "generic_name": "Azitromycine", "branded_name": "Zithromax"},
        )
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.substance, "Azitromycine")
        self.assertTrue(any("Zithromax" in b["name"] for b in parsed.brands))
        self.assertEqual(len(parsed.dosing_rules), 1)
        rule = parsed.dosing_rules[0]
        self.assertEqual(rule.route, "oral")
        self.assertEqual(rule.rate, 10.0)
        self.assertEqual(rule.doses_per_day, 1)
        self.assertEqual(rule.max_dose_daily, 500.0)
        self.assertEqual(rule.commercial_concentration_mg_ml, 40.0)
        self.assertTrue(len(parsed.excipient_warnings) >= 1)


class TestPediatricExcipientAndHepaticSafety(unittest.TestCase):

    def test_neonatal_excipient_screening(self):
        from src.models import Patient
        from src.knowledge_base import get_clinical_knowledge_base

        kb = get_clinical_knowledge_base()
        cotrimoxazol = kb["sulfamethoxazol-trimethoprim"] if "sulfamethoxazol-trimethoprim" in kb else kb["sulfamethoxazole-trimethoprim"]
        rule = cotrimoxazol.dosing_rules[0]

        # 1-month-old neonate (contraindicated for Bactrim excipients: sorbitol / propylene glycol)
        neonate = Patient(
            id="pat-neonate-001",
            name="Baby Lucas",
            age_years=0,
            age_months=1,
            weight_kg=3.8,
            height_cm=52.0,
            gender="male",
            serum_creatinine_mg_dl=0.3
        )

        res_neonate = evaluate_dosing_rule(neonate, cotrimoxazol, rule, bsa=0.23, egfr=71.5)
        self.assertTrue(len(res_neonate.excipient_alerts) > 0)
        self.assertIn("TMF magistral", res_neonate.excipient_alerts[0]["action"])

        # 5-year-old child (60 months) -> above excipient minimum age threshold (2 months)
        older_child = Patient(
            id="pat-child-002",
            name="Noah",
            age_years=5,
            age_months=60,
            weight_kg=19.0,
            height_cm=110.0,
            gender="male",
            serum_creatinine_mg_dl=0.45
        )
        res_older = evaluate_dosing_rule(older_child, cotrimoxazol, rule, bsa=0.76, egfr=100.9)
        self.assertEqual(len(res_older.excipient_alerts), 0)


if __name__ == "__main__":
    unittest.main()


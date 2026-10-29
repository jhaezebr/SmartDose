#!/usr/bin/env python3
"""Batch Ingestion script for Pediatric Knowledge Database.

Initializes pediatric_knowledge.db with clinically verified protocols from UZ Gent Richtlijn 906
and crawls/ingests additional formulary monographs from Kinderformularium.
"""

import sys
import os

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.knowledge_db import init_db, list_drugs_from_db, approve_drug_in_db
from src.scraper import crawl_and_ingest_drug, KNOWN_KF_REGISTRY


def main():
    print("=" * 60)
    print("Pediatric Formulary Batch Ingestion Engine")
    print("=" * 60)

    print("\n[1/3] Initializing and Seeding SQLite Database with Baseline Guidelines...")
    init_db()

    drugs = list_drugs_from_db()
    print(f"✓ Database initialized. Baseline drugs count: {len(drugs)}")
    for d in drugs:
        print(f"  - [{d.verification_status}] {d.substance} ({len(d.dosing_rules)} rules, {len(d.excipient_warnings)} excipient alerts, {len(d.hepatic_adjustments)} hepatic rules)")

    print("\n[2/3] Ingesting Additional Monographs from Kinderformularium...")
    for slug in KNOWN_KF_REGISTRY.keys():
        print(f"  -> Ingesting {slug}...")
        drug = crawl_and_ingest_drug(slug)
        if drug:
            print(f"     ✓ Successfully ingested: {drug.substance} (Status: {drug.verification_status})")
        else:
            print(f"     ✗ Failed to ingest: {slug}")

    all_drugs = list_drugs_from_db()
    print(f"\n[3/3] Total Substances in pediatric_knowledge.db: {len(all_drugs)}")
    print("Summary:")
    for d in all_drugs:
        status_icon = "🟢" if d.verification_status == "CLINICALLY_VERIFIED" else "🟠"
        print(f"  {status_icon} {d.substance:30} | {d.verification_status:20} | Verified by: {d.verified_by or 'None'}")

    print("\nDatabase initialization complete.")


if __name__ == "__main__":
    main()

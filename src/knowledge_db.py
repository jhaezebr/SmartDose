"""Persistent SQLite Knowledge Database for Pediatric Formulary with JSON1 document storage."""

import json
import sqlite3
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
from src.models import DrugInfo
from src.knowledge_base import get_clinical_knowledge_base

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "pediatric_knowledge.db")

# Clinical synonyms mapping substance -> list of known synonyms/aliases for search & display
SUBSTANCE_SYNONYMS: Dict[str, List[str]] = {
    "Sulfamethoxazole-Trimethoprim": ["Cotrimoxazol", "Co-trimoxazol", "Cotrimoxazole", "SMZ-TMP", "TMP-SMX"],
    "Aciclovir": ["Acyclovir"],
    "Fluconazole": ["Fluconazol"],
    "Ursodeoxycholzuur": ["UDCA", "Ursodiol", "Ursodeoxycholic acid"],
    "Penicilline": ["Fenoxymethylpenicilline", "Benzathine penicilline", "Penicillin V", "Penicillin G"],
    "Amoxicilline": ["Amoxicillin"],
    "Posaconazole": ["Posaconazol"],
    "Omeprazole": ["Omeprazol", "Esomeprazole", "Esomeprazol"],
    "Paracetamol": ["Acetaminophen", "APAP"],
    "Ceftriaxon": ["Ceftriaxone"],
    "Ibuprofen": ["NSAID"],
}


def get_synonyms_for_substance(substance_name: str) -> List[str]:
    """Returns clinical synonyms for a given canonical substance name."""
    for k, syns in SUBSTANCE_SYNONYMS.items():
        if k.lower() == substance_name.lower():
            return syns
    return []


def format_drug_search_label(drug: DrugInfo) -> str:
    """Formats a DrugInfo into a rich searchable dropdown label including generic name, synonyms, and brands."""
    badge = "🟢" if drug.verification_status == "CLINICALLY_VERIFIED" else "🟠"
    syns = get_synonyms_for_substance(drug.substance)
    syn_part = f" / {', '.join(syns[:2])}" if syns else ""

    # Extract concise commercial brand prefixes
    brand_names = []
    for b in drug.brands:
        raw_b = b.get("name", "").strip()
        if not raw_b:
            continue
        # Take first 1-2 words or before strength numbers
        short_b = re.split(r"\s+\d|\s+\(", raw_b)[0].strip()
        if short_b and short_b.lower() != drug.substance.lower() and short_b not in brand_names:
            brand_names.append(short_b)

    brand_part = f" — Brands: {', '.join(brand_names[:4])}" if brand_names else ""
    atc_part = f" [{drug.atc_code}]" if drug.atc_code and drug.atc_code != "N/A" else ""
    return f"{badge} {drug.substance}{syn_part}{brand_part}{atc_part}"


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initializes the database schema and seeds with baseline clinical guidelines if empty."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drugs (
            substance_id TEXT PRIMARY KEY,
            substance_name TEXT NOT NULL,
            atc_code TEXT,
            therapeutic_category TEXT,
            intent TEXT,
            verification_status TEXT DEFAULT 'CLINICALLY_VERIFIED',
            verified_by TEXT,
            verified_at TEXT,
            raw_source_url TEXT,
            data_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_drugs_name ON drugs(substance_name);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_drugs_status ON drugs(verification_status);")
    conn.commit()

    # Check if empty, seed if so
    cursor.execute("SELECT COUNT(*) FROM drugs;")
    count = cursor.fetchone()[0]
    if count == 0:
        seed_db(db_path)
    conn.close()


def seed_db(db_path: Optional[str] = None) -> None:
    """Seeds the SQLite database from the verified baseline knowledge base."""
    kb = get_clinical_knowledge_base()
    conn = get_connection(db_path)
    cursor = conn.cursor()

    seen = set()
    for key, drug in kb.items():
        if drug.substance in seen:
            continue
        seen.add(drug.substance)
        substance_id = key.lower().replace(" ", "-")
        data_json = json.dumps(drug.to_dict(), ensure_ascii=False)
        url = drug.source_citation.get("url", "")
        cursor.execute("""
            INSERT OR REPLACE INTO drugs (
                substance_id, substance_name, atc_code, therapeutic_category,
                intent, verification_status, verified_by, verified_at,
                raw_source_url, data_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
        """, (
            substance_id,
            drug.substance,
            drug.atc_code,
            drug.therapeutic_category,
            drug.intent,
            "CLINICALLY_VERIFIED",
            "Clinical Protocol UZ Gent Richtlijn 906",
            "2026-01-01T00:00:00Z",
            url,
            data_json,
        ))

    conn.commit()
    conn.close()


def save_drug_to_db(drug: DrugInfo, db_path: Optional[str] = None) -> None:
    """Inserts or updates a drug document in the database."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    substance_id = drug.substance.lower().replace(" ", "-")
    data_json = json.dumps(drug.to_dict(), ensure_ascii=False)
    url = drug.source_citation.get("url", "")

    cursor.execute("""
        INSERT OR REPLACE INTO drugs (
            substance_id, substance_name, atc_code, therapeutic_category,
            intent, verification_status, verified_by, verified_at,
            raw_source_url, data_json, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
    """, (
        substance_id,
        drug.substance,
        drug.atc_code,
        drug.therapeutic_category,
        drug.intent,
        drug.verification_status,
        drug.verified_by,
        drug.verified_at,
        url,
        data_json,
    ))
    conn.commit()
    conn.close()


def approve_drug_in_db(substance_name_or_id: str, doctor_name: str, db_path: Optional[str] = None) -> bool:
    """Promotes an unverified drug to CLINICALLY_VERIFIED with doctor stamp."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    now_str = datetime.now(timezone.utc).isoformat()

    # Find existing record
    cursor.execute("""
        SELECT substance_id, data_json FROM drugs
        WHERE substance_id = ? OR LOWER(substance_name) = LOWER(?);
    """, (substance_name_or_id, substance_name_or_id))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return False

    substance_id = row["substance_id"]
    data = json.loads(row["data_json"])
    data["verification_status"] = "CLINICALLY_VERIFIED"
    data["verified_by"] = doctor_name
    data["verified_at"] = now_str
    updated_json = json.dumps(data, ensure_ascii=False)

    cursor.execute("""
        UPDATE drugs
        SET verification_status = 'CLINICALLY_VERIFIED',
            verified_by = ?,
            verified_at = ?,
            data_json = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE substance_id = ?;
    """, (doctor_name, now_str, updated_json, substance_id))
    conn.commit()
    conn.close()
    return True


def get_drug_from_db(substance_name_or_id: str, db_path: Optional[str] = None) -> Optional[DrugInfo]:
    """Retrieves a drug by substance name, ID, synonym, or commercial brand name."""
    if not substance_name_or_id or not substance_name_or_id.strip():
        return None
    q = substance_name_or_id.strip()

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT data_json FROM drugs
        WHERE substance_id = LOWER(?) OR LOWER(substance_name) = LOWER(?);
    """, (q.replace(" ", "-"), q))
    row = cursor.fetchone()
    conn.close()
    if row:
        return DrugInfo.from_dict(json.loads(row["data_json"]))

    # Check synonyms map
    q_lower = q.lower()
    for canonical, syns in SUBSTANCE_SYNONYMS.items():
        if q_lower in [s.lower() for s in syns]:
            return get_drug_from_db(canonical, db_path=db_path)

    # Fallback: search by brand / substring
    matches = list_drugs_from_db(query=q, db_path=db_path)
    if matches:
        return matches[0]
    return None


def list_drugs_from_db(
    query: str = "",
    route_filter: Optional[List[str]] = None,
    intent_filter: Optional[str] = None,
    db_path: Optional[str] = None,
) -> List[DrugInfo]:
    """Queries drugs from database matching substance name, synonym, brand name, ATC code, and route/intent filters."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT data_json FROM drugs ORDER BY substance_name ASC;")
    rows = cursor.fetchall()
    conn.close()

    q = query.strip().lower() if query else ""
    matches = []

    for row in rows:
        drug_dict = json.loads(row["data_json"])
        drug = DrugInfo.from_dict(drug_dict)

        if q != "":
            syns = [s.lower() for s in get_synonyms_for_substance(drug.substance)]
            name_match = (
                (q in drug.substance.lower())
                or (q in drug.therapeutic_category.lower())
                or (q in (drug.atc_code or "").lower())
                or any(q in s for s in syns)
            )
            if not name_match:
                for b in drug.brands:
                    if q in b.get("name", "").lower():
                        name_match = True
                        break
            if not name_match:
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

        matches.append(drug)

    return matches


def get_all_substance_names_from_db(db_path: Optional[str] = None) -> List[str]:
    """Returns sorted list of all unique substance names present in the database."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT substance_name FROM drugs ORDER BY substance_name ASC;")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

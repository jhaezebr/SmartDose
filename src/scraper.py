"""Kinderformularium and Guideline Scraper / Ingestion Engine.

Fetches and extracts drug information, dosing rules, excipient safety alerts,
and organ impairment guidance from Kinderformularium pages, generating
DrugInfo records tagged as 'AI_EXTRACTED' for clinical review and verification.
"""

import json
import logging
import os
import re
import urllib.request
import urllib.parse
from html import unescape
from typing import Dict, List, Optional, Tuple

from src.models import DrugInfo, DosingRule, RenalThreshold
from src.knowledge_db import save_drug_to_db, get_drug_from_db

logger = logging.getLogger(__name__)

KF_INDEX_URL = "https://www.kinderformularium.nl/geneesmiddelen.json"
KF_CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "kf_index_cache.json",
)
_KF_INDEX_MEM_CACHE: Optional[List[Dict]] = None

# Known registry mapping query/slug to Kinderformularium URLs and rich fallback definitions
KNOWN_KF_REGISTRY: Dict[str, Dict] = {
    "paracetamol": {
        "url": "https://www.kinderformularium.nl/geneesmiddel/47/paracetamol",
        "substance": "Paracetamol",
        "atc_code": "N02BE01",
        "category": "Analgesic & Antipyretic",
        "intent": "therapeutic",
        "brands": [
            {"name": "Dafalgan Siroop 30 mg/mL", "strength": "30 mg/mL", "form": "Syrup", "cnk": "0041236"},
            {"name": "Perfalgan 10 mg/mL IV", "strength": "10 mg/mL", "form": "Vial IV", "cnk": "2134500"},
            {"name": "Paracetamol Sandoz 500 mg comp", "strength": "500 mg", "form": "Tablets", "cnk": "1548908"},
        ],
        "magistral": "Paracetamol siroop 20-40 mg/mL TMF",
        "instructions": ["Max 4 doses in 24 hours. Minimum interval 4 to 6 hours between doses."],
        "cautions": ["Hepatotoxicity at cumulative doses > 60 mg/kg/day or with glutathione depletion."],
        "excipient_warnings": [
            {"excipient": "Sorbitol (Dafalgan siroop)", "risk": "Osmotic diarrhea and discomfort in infants", "min_age_months": 1}
        ],
        "hepatic_adjustments": [
            {"condition": "Mild to Moderate Hepatic Impairment", "instruction": "Reduce daily dose to max 30-40 mg/kg/day"},
            {"condition": "Severe Hepatic Failure / Acute Hepatitis", "instruction": "CONTRAINDICATED"},
        ],
        "rules": [
            DosingRule(
                rule_id="paracetamol-oral-standard",
                route="oral",
                form_type="syrup/suspension",
                formula_description="15 mg/kg every 6 hours P.O. (Max 60 mg/kg/day, adult max 1000 mg/dose)",
                basis="weight",
                rate=15.0,
                unit="mg",
                doses_per_day=4,
                schedule_description="Every 6 hours P.O.",
                max_dose_single=1000.0,
                max_dose_daily=4000.0,
                commercial_concentration_mg_ml=30.0,
                available_strengths=["Dafalgan 30 mg/mL siroop", "Paracetamol 500 mg comp"],
            ),
            DosingRule(
                rule_id="paracetamol-iv-standard",
                route="intravenous",
                form_type="injection",
                formula_description="15 mg/kg every 6 hours IV (> 10 kg) or 7.5 mg/kg IV (< 10 kg)",
                basis="weight",
                rate=15.0,
                unit="mg",
                doses_per_day=4,
                schedule_description="IV infusion over 15 minutes every 6 hours",
                weight_min_kg=10.0,
                max_dose_single=1000.0,
                max_dose_daily=2000.0,
                commercial_concentration_mg_ml=10.0,
                available_strengths=["Perfalgan 10 mg/mL flacon IV"],
            ),
        ],
    },
    "ceftriaxon": {
        "url": "https://www.kinderformularium.nl/geneesmiddel/28/ceftriaxon",
        "substance": "Ceftriaxon",
        "atc_code": "J01DD04",
        "category": "Third-Generation Cephalosporin Antibiotic",
        "intent": "both",
        "brands": [
            {"name": "Rocephin 1g Flacon IV/IM", "strength": "1000 mg/flacon", "form": "Powder for injection", "cnk": "0089128"},
            {"name": "Ceftriaxone Sandoz 2g Flacon", "strength": "2000 mg/flacon", "form": "Powder for infusion", "cnk": "1782341"},
        ],
        "magistral": "Not applicable (commercial lyophilized vial)",
        "instructions": [
            "DO NOT co-administer or mix with calcium-containing IV solutions (e.g., Ringer-Lactate) due to risk of fatal ceftriaxone-calcium salt precipitation in lungs and kidneys."
        ],
        "cautions": [
            "CONTRAINDICATED in hyperbilirubinemic neonates and premature infants (displaces bilirubin from albumin -> kernicterus)."
        ],
        "excipient_warnings": [
            {"excipient": "Calcium incompatibility & Bilirubin displacement", "risk": "Fatal precipitation with IV calcium; severe kernicterus in neonates < 28 days", "min_age_months": 1}
        ],
        "hepatic_adjustments": [
            {"condition": "Combined severe renal and hepatic impairment", "instruction": "Monitor plasma levels; reduce daily dose by 50%"}
        ],
        "rules": [
            DosingRule(
                rule_id="ceftriaxone-iv-severe-infections",
                route="intravenous",
                form_type="injection",
                formula_description="50-100 mg/kg once daily IV (Max 4000 mg/day)",
                basis="weight",
                rate=50.0,
                unit="mg",
                doses_per_day=1,
                schedule_description="Once daily IV infusion over 30 minutes",
                age_min_months=1,
                max_dose_daily=4000.0,
                available_strengths=["Rocephin 1 g flacon", "Rocephin 2 g flacon"],
            )
        ],
    },
    "ibuprofen": {
        "url": "https://www.kinderformularium.nl/geneesmiddel/38/ibuprofen",
        "substance": "Ibuprofen",
        "atc_code": "M01AE01",
        "category": "Non-Steroidal Anti-Inflammatory Drug (NSAID)",
        "intent": "therapeutic",
        "brands": [
            {"name": "Nurofen voor Kinderen 100 mg / 5 mL Siroop", "strength": "20 mg/mL", "form": "Oral suspension", "cnk": "1423110"},
            {"name": "Nurofen 200 mg / 400 mg Comprimés", "strength": "200 mg / 400 mg", "form": "Tablets", "cnk": "0891234"},
        ],
        "magistral": "Ibuprofen siroop 20 mg/mL TMF",
        "instructions": ["Administer with or after food. Ensure adequate hydration."],
        "cautions": ["Avoid in active bleeding, severe renal failure, or active gastrointestinal ulcer."],
        "excipient_warnings": [
            {"excipient": "Maltitol & Sodium (Nurofen siroop)", "risk": "Laxative effect; contraindicated in neonates < 3 months or < 5 kg", "min_age_months": 3}
        ],
        "hepatic_adjustments": [
            {"condition": "Severe Hepatic Impairment", "instruction": "CONTRAINDICATED due to impaired metabolism and bleeding diathesis"}
        ],
        "rules": [
            DosingRule(
                rule_id="ibuprofen-oral-analgesic",
                route="oral",
                form_type="syrup/suspension",
                formula_description="10 mg/kg 3 times daily (Max 30 mg/kg/day or 1200 mg/day)",
                basis="weight",
                rate=10.0,
                unit="mg",
                doses_per_day=3,
                schedule_description="Every 8 hours with meals",
                age_min_months=3,
                weight_min_kg=5.0,
                max_dose_daily=1200.0,
                commercial_concentration_mg_ml=20.0,
                available_strengths=["Nurofen voor Kinderen 20 mg/mL siroop"],
            )
        ],
    },
}


def fetch_kinderformularium_page(url: str) -> Optional[str]:
    """Fetches HTML or JSON page from Kinderformularium via HTTP GET."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "nl,en-US;q=0.7,en;q=0.3",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status == 200:
                return response.read().decode("utf-8", errors="ignore")
    except Exception as e:
        logger.warning(f"Failed to fetch Kinderformularium URL {url}: {e}")
    return None


def fetch_kinderformularium_index() -> List[Dict]:
    """Fetches and caches the complete 938-drug Kinderformularium JSON index."""
    global _KF_INDEX_MEM_CACHE
    if _KF_INDEX_MEM_CACHE is not None:
        return _KF_INDEX_MEM_CACHE

    if os.path.exists(KF_CACHE_PATH):
        try:
            with open(KF_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and len(data) > 0:
                    _KF_INDEX_MEM_CACHE = data
                    return data
        except Exception as e:
            logger.warning(f"Failed to read cached KF index: {e}")

    raw_json = fetch_kinderformularium_page(KF_INDEX_URL)
    if raw_json:
        try:
            data = json.loads(raw_json)
            if isinstance(data, list) and len(data) > 0:
                _KF_INDEX_MEM_CACHE = data
                try:
                    with open(KF_CACHE_PATH, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False)
                except Exception:
                    pass
                return data
        except Exception as e:
            logger.warning(f"Failed to parse KF index JSON: {e}")

    return []


def build_kf_monograph_url(entry: Dict) -> str:
    """Constructs the canonical Kinderformularium monograph URL from an index entry."""
    drug_id = entry["id"]
    generic_name = entry.get("generic_name", "geneesmiddel")
    slug = re.sub(r"[^a-z0-9]+", "-", generic_name.lower()).strip("-")
    return f"https://www.kinderformularium.nl/geneesmiddel/{drug_id}/{slug}"


def _normalize_variants(query: str) -> List[str]:
    """Generates Dutch/English pharmaceutical spelling variants for resilient matching."""
    q = query.strip().lower()
    variants = {q, q.replace("-", ""), q.replace(" ", "")}

    # Common EN -> NL translations
    synonyms = {
        "acetaminophen": "paracetamol",
        "co-trimoxazole": "cotrimoxazol",
        "cotrimoxazole": "cotrimoxazol",
        "sulfamethoxazole-trimethoprim": "cotrimoxazol",
        "smz-tmp": "cotrimoxazol",
        "acyclovir": "aciclovir",
        "ursodeoxycholic acid": "ursodeoxycholzuur",
        "ursodiol": "ursodeoxycholzuur",
        "phenoxymethylpenicillin": "fenoxymethylpenicilline",
        "penicillin": "penicilline",
    }
    if q in synonyms:
        variants.add(synonyms[q])

    # Morphological rules (EN -> NL)
    # e.g. fluconazole -> fluconazol, ceftriaxone -> ceftriaxon, amoxicillin -> amoxicilline, azithromycin -> azitromycine
    if q.endswith("azole"):
        variants.add(q[:-1])  # -> azol
    if q.endswith("one"):
        variants.add(q[:-1])  # -> on
    if q.endswith("ine") and not q.endswith("mycine"):
        variants.add(q[:-1])  # e.g. prednisolone -> prednisolon
    if not q.endswith("e"):
        variants.add(q + "e")  # e.g. amoxicillin -> amoxicilline, vancomycin -> vancomycine
    if "th" in q:
        variants.add(q.replace("th", "t"))
        if not q.endswith("e"):
            variants.add(q.replace("th", "t") + "e")
    if "ph" in q:
        variants.add(q.replace("ph", "f"))

    return [v for v in variants if v]


def search_kinderformularium_index(query: str, max_results: int = 15) -> List[Dict]:
    """Searches the 938-drug Kinderformularium catalog by generic name, synonym, or brand name."""
    if not query or not query.strip():
        return []

    index = fetch_kinderformularium_index()
    if not index:
        return []

    variants = _normalize_variants(query)
    scored: List[Tuple[int, Dict]] = []

    for item in index:
        gen = (item.get("generic_name") or "").strip()
        gen_lower = gen.lower()
        gen_primary = gen_lower.split("(")[0].strip()
        brand = (item.get("branded_name") or "").strip()
        brand_lower = brand.lower()

        best_score = 0
        for v in variants:
            if gen_lower == v or gen_primary == v:
                best_score = max(best_score, 100)
            elif gen_primary.startswith(v) or gen_lower.startswith(v):
                best_score = max(best_score, 85)
            elif v in [b.strip() for b in re.split(r"[,;/()]+", brand_lower) if b.strip()]:
                best_score = max(best_score, 80)
            elif v in gen_lower:
                best_score = max(best_score, 65)
            elif v in brand_lower:
                best_score = max(best_score, 55)

        if best_score > 0:
            scored.append((best_score, item))

    scored.sort(key=lambda x: (-x[0], len(x[1].get("generic_name", ""))))
    return [item for _, item in scored[:max_results]]


def clean_html_text(text: str) -> str:
    """Strips tags, unescapes HTML entities, and collapses whitespace."""
    no_tags = re.sub(r"<[^>]+>", " ", text)
    unescaped = unescape(no_tags)
    return " ".join(unescaped.split())


def extract_h4_section(html: str, heading_keyword: str) -> Tuple[str, str]:
    """Extracts (raw_html, clean_text) of a specific <h4> section in Kinderformularium."""
    pattern = rf"<h4[^>]*>[^<]*?{heading_keyword}[^<]*?</h4>"
    m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    if not m:
        return "", ""
    start_pos = m.end()
    m_next = re.search(r"<h4[^>]*>", html[start_pos:], re.IGNORECASE)
    end_pos = start_pos + m_next.start() if m_next else start_pos + 12000
    raw_block = html[start_pos:end_pos]
    return raw_block, clean_html_text(raw_block)


def _map_dutch_route(route_str: str) -> Tuple[str, str]:
    """Maps Dutch Kinderformularium route strings to (internal_route, default_form_type)."""
    r = route_str.strip().lower()
    if any(k in r for k in ["intraveneus", "infuus", "parenteraal"]):
        return "intravenous", "injection"
    if any(k in r for k in ["intramusculair", "subcutaan"]):
        return "intramuscular", "injection"
    if "rectaal" in r:
        return "oral", "suppository (rectaal)"
    if "inhalatie" in r:
        return "oral", "inhalation / nebulizer"
    return "oral", "syrup/suspension"


def _parse_doses_per_day(freq_text: str) -> int:
    """Extracts number of doses per day from Dutch frequency string."""
    f = freq_text.lower()
    if "éénmalig" in f or "eenmalig" in f or "1 keer per dag" in f or "1 dd" in f:
        return 1
    m_hours = re.search(r"elke\s+(\d+)\s*uur", f)
    if m_hours:
        hrs = int(m_hours.group(1))
        if hrs > 0 and 24 % hrs == 0:
            return 24 // hrs
    m_doses = re.search(r"in\s+(\d+)(?:\s*-\s*(\d+))?\s*doses", f)
    if m_doses:
        return int(m_doses.group(2) or m_doses.group(1))
    m_keer = re.search(r"(\d+)(?:\s*-\s*(\d+))?\s*(?:keer per dag|dd|maal per dag)", f)
    if m_keer:
        return int(m_keer.group(2) or m_keer.group(1))
    return 1


def _parse_doseringen_rules(raw_doseringen_html: str, substance_name: str, forms_text: str, brands: List[Dict]) -> List[DosingRule]:
    """Parses schema.org DoseSchedule items from Kinderformularium's Doseringen HTML section."""
    rules: List[DosingRule] = []
    if not raw_doseringen_html:
        return rules

    # Split by indication table
    tables = re.findall(r"<table[^>]*class=\"[^\"]*dosage[^\"]*\"[^>]*>(.*?)</table>", raw_doseringen_html, re.DOTALL | re.IGNORECASE)
    if not tables:
        tables = [raw_doseringen_html]

    rule_counter = 0
    for table_html in tables:
        m_ind = re.search(r"itemprop=\"name\"[^>]*>(.*?)</span>", table_html, re.DOTALL | re.IGNORECASE)
        indication = clean_html_text(m_ind.group(1)) if m_ind else "Standaard indicatie"

        # Find route sections inside table
        route_splits = re.split(r"<strong[^>]*itemprop=\"administrationRoute\"[^>]*>(.*?)</strong>", table_html, flags=re.DOTALL | re.IGNORECASE)
        # route_splits[0] is before first route; then pairs of (route_name, route_content)
        for i in range(1, len(route_splits), 2):
            nl_route = clean_html_text(route_splits[i])
            route_content = route_splits[i + 1] if (i + 1) < len(route_splits) else ""
            norm_route, default_form = _map_dutch_route(nl_route)
            if norm_route == "oral" and ("tablet" in forms_text.lower() or "caps" in forms_text.lower()) and "susp" not in forms_text.lower() and "drank" not in forms_text.lower():
                default_form = "tablet/capsule"

            # Find each DoseSchedule block
            schedules = re.findall(
                r"<li[^>]*itemtype=\"http://schema\.org/DoseSchedule\"[^>]*>(.*?)(?=<li[^>]*itemtype=\"http://schema\.org/DoseSchedule\"|</ul>\s*</li>|$)",
                route_content,
                re.DOTALL | re.IGNORECASE,
            )
            for sched_html in schedules:
                m_pop = re.search(r"itemprop=\"targetPopulation\"[^>]*>(.*?)</div>", sched_html, re.DOTALL | re.IGNORECASE)
                target_pop = clean_html_text(m_pop.group(1)) if m_pop else "Kinderen"

                m_val = re.search(r"itemprop=\"doseValue\"[^>]*>(.*?)</span>", sched_html, re.DOTALL | re.IGNORECASE)
                m_unit = re.search(r"itemprop=\"doseUnit\"[^>]*>(.*?)</span>", sched_html, re.DOTALL | re.IGNORECASE)
                m_freq = re.search(r"itemprop=\"frequency\"[^>]*>(.*?)</span>", sched_html, re.DOTALL | re.IGNORECASE)

                if not m_val or not m_unit:
                    continue

                val_str = clean_html_text(m_val.group(1))
                unit_str = clean_html_text(m_unit.group(1)).rstrip(",")
                freq_str = clean_html_text(m_freq.group(1)) if m_freq else ""
                full_sched_text = clean_html_text(sched_html)

                # Extract numeric dose value (if range like "10 - 20", take first or standard value)
                nums = re.findall(r"\d+(?:[.,]\d+)?", val_str)
                if not nums:
                    continue
                # If val_str has something like "5% oplossing: 140", take the last number if "%" precedes first
                raw_num = float(nums[-1].replace(",", ".")) if "%" in val_str and len(nums) > 1 else float(nums[0].replace(",", "."))

                doses_per_day = _parse_doses_per_day(freq_str)

                # Determine basis (weight, bsa, or fixed) and per-dose rate
                unit_lower = unit_str.lower()
                if "/kg" in unit_lower:
                    basis = "weight"
                elif "/m2" in unit_lower or "/m²" in unit_lower:
                    basis = "bsa"
                else:
                    basis = "weight"

                base_unit = unit_str.split("/")[0].strip() or "mg"

                if basis == "weight" and "/kg" not in unit_lower and "/m" not in unit_lower:
                    # Fixed dose (e.g. "200 mg per dosis")
                    rate = 0.0
                    max_single = raw_num
                    max_daily = raw_num * doses_per_day
                else:
                    if "/dag" in unit_lower and doses_per_day > 0:
                        rate = round(raw_num / doses_per_day, 2)
                    else:
                        rate = raw_num
                    max_single = None
                    max_daily = None

                # Parse explicit maximums from text (e.g. "Maximaal 1000 mg per dosis" or "max. 4000 mg/dag" or "max. 4 gram/dag")
                m_max_dag = re.search(r"max(?:imaal|\.?)\s*(\d+(?:[.,]\d+)?)\s*(g|gram|mg|microg)\s*(?:/|per\s+)dag", full_sched_text, re.IGNORECASE)
                if m_max_dag:
                    mv = float(m_max_dag.group(1).replace(",", "."))
                    if m_max_dag.group(2).lower().startswith("g") and base_unit.lower() == "mg":
                        mv *= 1000.0
                    max_daily = mv

                m_max_dosis = re.search(r"max(?:imaal|\.?)\s*(\d+(?:[.,]\d+)?)\s*(g|gram|mg|microg)\s*(?:/|per\s+)(?:dosis|keer)", full_sched_text, re.IGNORECASE)
                if m_max_dosis:
                    mv = float(m_max_dosis.group(1).replace(",", "."))
                    if m_max_dosis.group(2).lower().startswith("g") and base_unit.lower() == "mg":
                        mv *= 1000.0
                    max_single = mv

                # Try to find liquid concentration (mg/ml) from forms_text if oral liquid
                conc_mg_ml = None
                if norm_route == "oral" and base_unit.lower() == "mg":
                    m_conc = re.search(r"(\d+(?:[.,]\d+)?)\s*mg\s*/\s*ml", forms_text, re.IGNORECASE)
                    if m_conc:
                        conc_mg_ml = float(m_conc.group(1).replace(",", "."))

                rule_counter += 1
                slug_id = re.sub(r"[^a-z0-9]+", "-", substance_name.lower()).strip("-")
                rules.append(
                    DosingRule(
                        rule_id=f"{slug_id}-kf-{rule_counter}",
                        route=norm_route,
                        form_type=default_form if nl_route.lower() == "oraal" else f"{default_form} ({nl_route})",
                        formula_description=f"[{indication} — {target_pop}] {val_str} {unit_str} {freq_str}".strip(),
                        basis=basis,
                        rate=rate,
                        unit=base_unit,
                        doses_per_day=doses_per_day,
                        schedule_description=f"{nl_route} ({target_pop}): {freq_str or 'Conform Kinderformularium'}",
                        max_dose_single=max_single,
                        max_dose_daily=max_daily,
                        commercial_concentration_mg_ml=conc_mg_ml,
                        available_strengths=[b.get("name", "") for b in brands[:3]] if brands else ["Zie Kinderformularium"],
                    )
                )

                if len(rules) >= 6:
                    return rules

    return rules


def parse_kinderformularium_html(
    html: str,
    source_url: str,
    index_entry: Optional[Dict] = None,
) -> Optional[DrugInfo]:
    """Parses raw Kinderformularium HTML and extracts structured DrugInfo."""
    # 1. Extract substance title from index_entry or <h3>/<h4> (Kinderformularium uses <h3>/<h4>, not <h1>)
    substance_name = ""
    if index_entry and index_entry.get("generic_name"):
        substance_name = index_entry["generic_name"].split("(")[0].strip()

    if not substance_name:
        m_h3 = re.search(r"<h3[^>]*>(.*?)</h3>", html, re.DOTALL | re.IGNORECASE)
        if m_h3:
            substance_name = clean_html_text(m_h3.group(1)).split("(")[0].strip()

    if not substance_name:
        m_h4 = re.search(r"<h4[^>]*>(.*?)</h4>", html, re.DOTALL | re.IGNORECASE)
        if m_h4:
            substance_name = clean_html_text(m_h4.group(1)).split("(")[0].strip()

    if not substance_name or substance_name.lower() == "unknown substance":
        return None

    # 2. Extract Therapeutic Category (3rd <h3> tag on Kinderformularium pages) & ATC code
    h3_matches = [clean_html_text(m) for m in re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.DOTALL | re.IGNORECASE)]
    therapeutic_category = (
        h3_matches[2].title()
        if len(h3_matches) >= 3 and h3_matches[2]
        else "Kinderformularium Pediatric Monograph"
    )

    m_atc = re.search(r"\b([A-Z]\d{2}[A-Z]{2}\d{2})\b", html)
    atc_code = m_atc.group(1).strip() if m_atc else "N/A"

    # 3. Extract Toedieningsvormen / Strengths & Commercial Brands
    _, forms_text = extract_h4_section(html, "Beschikbare toedieningsvormen")
    brands: List[Dict] = []

    if index_entry and index_entry.get("branded_name"):
        for b_name in [b.strip() for b in index_entry["branded_name"].split(",") if b.strip()]:
            brands.append(
                {
                    "name": b_name,
                    "strength": forms_text[:80] if forms_text else "Diverse sterktes",
                    "form": "Commercieel spécialité (NL/BE)",
                    "cnk": "N/A",
                }
            )

    if forms_text:
        brands.append(
            {
                "name": f"{substance_name} ({forms_text[:70]})",
                "strength": forms_text[:80],
                "form": forms_text[:60],
                "cnk": "N/A",
            }
        )

    # 4. Extract Warnings & Excipients from <h4> sections
    _, excipient_section_text = extract_h4_section(html, "Ongewenste hulpstoffen")
    excipient_warnings = []
    search_exc_pool = f"{forms_text} {excipient_section_text}".lower()

    if "propyleenglycol" in search_exc_pool:
        excipient_warnings.append(
            {
                "excipient": "Propyleenglycol (Propylene glycol)",
                "risk": excipient_section_text or "Exceeds safety threshold in young children (hyperosmolality, lactic acidosis)",
                "min_age_months": 60,
            }
        )
    if "benzylalcohol" in search_exc_pool:
        excipient_warnings.append(
            {
                "excipient": "Benzylalcohol",
                "risk": excipient_section_text or "Fatal gasping syndrome in neonates and young infants",
                "min_age_months": 3,
            }
        )
    if "natriumbenzoaat" in search_exc_pool or "benzoëzuur" in search_exc_pool:
        excipient_warnings.append(
            {
                "excipient": "Natriumbenzoaat / Benzoëzuur",
                "risk": excipient_section_text or "Displacement of bilirubin from albumin in neonates",
                "min_age_months": 2,
            }
        )
    if "sorbitol" in search_exc_pool:
        excipient_warnings.append(
            {
                "excipient": "Sorbitol",
                "risk": excipient_section_text or "Gastrointestinal distress and osmotic diarrhea in infants",
                "min_age_months": 1,
            }
        )
    if "ethanol" in search_exc_pool or "alcohol" in search_exc_pool:
        excipient_warnings.append(
            {
                "excipient": "Ethanol (Alcohol)",
                "risk": excipient_section_text or "CNS depression and hypoglycemia risk in young children",
                "min_age_months": 24,
            }
        )
    if excipient_section_text and not excipient_warnings:
        excipient_warnings.append(
            {
                "excipient": "Hulpstoffen waarschuwing (Kinderformularium)",
                "risk": excipient_section_text[:250],
                "min_age_months": 6,
            }
        )

    cautions = []
    _, contra_text = extract_h4_section(html, "Contraindicaties bij kinderen")
    if contra_text:
        cautions.append(f"Contra-indicaties: {contra_text[:300]}")

    _, warn_text = extract_h4_section(html, "Waarschuwingen en voorzorgen bij kinderen")
    if warn_text:
        cautions.append(f"Waarschuwingen: {warn_text[:350]}")

    # 5. Extract Renal and Hepatic Impairment remarks
    _, renal_text = extract_h4_section(html, "Nierfunctiestoornissen")
    if renal_text and "geen gegevens bekend" not in renal_text.lower():
        cautions.append(f"Nierfunctie advies: {renal_text[:280]}")

    _, hepatic_text = extract_h4_section(html, "Leverfunctiestoornissen")
    hepatic_adjustments = []
    if hepatic_text:
        hepatic_adjustments.append(
            {
                "condition": "Leverfunctiestoornis (Kinderformularium)",
                "instruction": hepatic_text[:300],
            }
        )

    # 6. Extract Dosing Guidelines from <h4>Doseringen</h4>
    _, alg_dose_text = extract_h4_section(html, "Algemene doseer informatie")
    raw_doseringen, clean_doseringen = extract_h4_section(html, "Doseringen")

    dosing_rules = _parse_doseringen_rules(raw_doseringen, substance_name, forms_text, brands)

    if not dosing_rules:
        # Fallback heuristic parsing from clean_doseringen
        rate = 10.0
        unit = "mg"
        doses_per_day = 3
        formula_desc = (
            f"Kinderformularium advies: {clean_doseringen[:160]}..."
            if clean_doseringen
            else "Raadpleeg Kinderformularium monografie"
        )
        m_rate = re.search(
            r"(\d+(?:[.,]\d+)?)\s*(?:-|tot)?\s*(\d+(?:[.,]\d+)?)?\s*(mg|microg|g|ie|eenheden)/kg/(dag|dosis|keer)",
            clean_doseringen,
            re.IGNORECASE,
        )
        if m_rate:
            val = float(m_rate.group(1).replace(",", "."))
            unit = m_rate.group(3)
            per_what = m_rate.group(4).lower()
            rate = round(val / doses_per_day, 2) if per_what == "dag" else val
            formula_desc = f"{val} {unit}/kg/{per_what} conform Kinderformularium"

        dosing_rules.append(
            DosingRule(
                rule_id=f"{substance_name.lower().replace(' ', '-')}-kf-extracted",
                route="oral" if ("oraal" in clean_doseringen.lower() or "drank" in forms_text.lower() or "tablet" in forms_text.lower()) else "intravenous",
                form_type="syrup/suspension" if ("susp" in forms_text.lower() or "drank" in forms_text.lower()) else "tablet/capsule",
                formula_description=formula_desc,
                basis="weight",
                rate=rate,
                unit=unit,
                doses_per_day=doses_per_day,
                schedule_description="Volgens Kinderformularium richtlijn",
                available_strengths=[b.get("name", "") for b in brands[:3]] if brands else ["Zie officiële SmPC"],
            )
        )

    admin_instructions = []
    if alg_dose_text:
        admin_instructions.append(alg_dose_text[:300])
    if forms_text:
        admin_instructions.append(f"Beschikbare vormen: {forms_text[:250]}")
    if not admin_instructions:
        admin_instructions.append("Volg toedieningsinstructies op Kinderformularium.nl")

    drug = DrugInfo(
        substance=substance_name,
        atc_code=atc_code,
        therapeutic_category=therapeutic_category,
        intent="both",
        brands=brands if brands else [{"name": f"{substance_name} (Spécialité)", "strength": "Diverse", "form": "Oral / Parenteral", "cnk": "N/A"}],
        magistral_formula="Raadpleeg TMF / ziekenhuisapotheek formularium indien geen geschikte kindervorm commercieel geregistreerd is",
        administration_instructions=admin_instructions,
        cautions=cautions if cautions else ["Volg standaard pediatrische voorzorgen conform Kinderformularium"],
        source_citation={
            "title": f"Nederlands Kenniscentrum Kinderformularium — {substance_name}",
            "url": source_url,
            "evidence_level": "Level 1A Formulary Monograph",
        },
        excipient_warnings=excipient_warnings,
        hepatic_adjustments=hepatic_adjustments,
        dosing_rules=dosing_rules,
        verification_status="AI_EXTRACTED",
        verified_by="Kinderformularium Crawler (Automated Extraction)",
        verified_at=None,
    )
    return drug


def crawl_and_ingest_drug(substance_or_query: str, db_path: Optional[str] = None) -> Optional[DrugInfo]:
    """Fetches a drug from Kinderformularium (via 938-drug index, URL, or registry) and saves it into SQLite."""
    query_key = substance_or_query.strip().lower()
    if not query_key:
        return None

    # 1. Check if known in curated registry (by substance name or brand name)
    for reg_key, reg in KNOWN_KF_REGISTRY.items():
        brand_names_lower = " ".join(b.get("name", "").lower() for b in reg.get("brands", []))
        if query_key == reg_key or query_key == reg["substance"].lower() or query_key in brand_names_lower.split():
            drug = DrugInfo(
                substance=reg["substance"],
                atc_code=reg["atc_code"],
                therapeutic_category=reg["category"],
                intent=reg["intent"],
                brands=reg["brands"],
                magistral_formula=reg["magistral"],
                administration_instructions=reg["instructions"],
                cautions=reg["cautions"],
                source_citation={
                    "title": f"Kinderformularium - {reg['substance']}",
                    "url": reg["url"],
                    "evidence_level": "Level 1A Formulary Monograph",
                },
                excipient_warnings=reg.get("excipient_warnings", []),
                hepatic_adjustments=reg.get("hepatic_adjustments", []),
                dosing_rules=reg["rules"],
                verification_status="AI_EXTRACTED",
                verified_by="Kinderformularium Crawler (Automated Extraction)",
                verified_at=None,
            )
            save_drug_to_db(drug, db_path)
            return drug

    # 2. Check if a full URL was provided
    if substance_or_query.strip().startswith(("http://", "https://")):
        url = substance_or_query.strip()
        html = fetch_kinderformularium_page(url)
        if html:
            # Try to match entry from index by ID in URL
            m_id = re.search(r"/geneesmiddel/(\d+)", url)
            matched_entry = None
            if m_id:
                gid = int(m_id.group(1))
                for item in fetch_kinderformularium_index():
                    if item.get("id") == gid:
                        matched_entry = item
                        break
            drug = parse_kinderformularium_html(html, url, index_entry=matched_entry)
            if drug:
                save_drug_to_db(drug, db_path)
                return drug
        return None

    # 3. Search the 938-drug Kinderformularium catalog by generic name, synonym, or brand name
    matches = search_kinderformularium_index(substance_or_query, max_results=3)
    for entry in matches:
        url = build_kf_monograph_url(entry)
        html = fetch_kinderformularium_page(url)
        if html and ("Doseringen" in html or "Beschikbare toedieningsvormen" in html):
            drug = parse_kinderformularium_html(html, url, index_entry=entry)
            if drug:
                save_drug_to_db(drug, db_path)
                return drug

    return None

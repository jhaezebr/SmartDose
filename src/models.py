"""Data models for Pediatric Medication Prescriber."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class Patient:
    id: str
    name: str
    age_years: int
    age_months: int  # Total age in months for infants
    gender: str  # 'male' or 'female'
    weight_kg: float
    height_cm: float
    serum_creatinine_mg_dl: float
    allergies: List[str] = field(default_factory=list)
    active_medications: List[str] = field(default_factory=list)
    condition: Optional[str] = None
    transplant_type: Optional[str] = None  # e.g., 'allogeneic', 'autologous', 'none'
    preferred_route: Optional[str] = None  # e.g., 'oral', 'iv', etc.


@dataclass
class RenalThreshold:
    crcl_min: Optional[float] = None
    crcl_max: Optional[float] = None
    instruction: str = ""
    frequency_hours: Optional[int] = None
    dose_factor: float = 1.0


@dataclass
class DosingRule:
    rule_id: str
    route: str  # 'oral', 'intravenous', 'intramuscular'
    form_type: str  # 'syrup/suspension', 'tablet/capsule', 'injection'
    formula_description: str
    basis: str  # 'bsa' or 'weight'
    rate: float  # e.g., 250 mg/m2 or 6 mg/kg
    unit: str  # 'mg', 'mcg', 'IE'
    doses_per_day: int  # e.g. 3 times daily
    schedule_description: str  # e.g., "3 times daily", "Q8H", "every 4 weeks"
    weight_min_kg: Optional[float] = None
    weight_max_kg: Optional[float] = None
    age_min_months: Optional[int] = None
    age_max_months: Optional[int] = None
    max_dose_single: Optional[float] = None
    max_dose_daily: Optional[float] = None
    max_dose_per_kg_daily: Optional[float] = None
    commercial_concentration_mg_ml: Optional[float] = None
    available_strengths: List[str] = field(default_factory=list)
    renal_adjustments: List[RenalThreshold] = field(default_factory=list)


@dataclass
class DrugInfo:
    substance: str
    atc_code: str
    therapeutic_category: str
    intent: str  # 'prophylactic', 'therapeutic', 'both'
    brands: List[Dict[str, str]] = field(default_factory=list)  # [{'name': 'Zovirax', 'cnk': '0042895', 'form': '...'}]
    magistral_formula: Optional[str] = None
    administration_instructions: List[str] = field(default_factory=list)
    cautions: List[str] = field(default_factory=list)
    source_citation: Dict[str, str] = field(default_factory=dict)  # {'title': '...', 'url': '...', 'evidence_level': '...'}
    dosing_rules: List[DosingRule] = field(default_factory=list)


@dataclass
class CalculationResult:
    substance: str
    route: str
    form_type: str
    single_dose: float
    total_daily_dose: float
    unit: str
    frequency_text: str
    formula_used: str
    math_breakdown: str
    liquid_volume_ml: Optional[float] = None
    recommended_syringe: Optional[str] = None
    renal_status_note: Optional[str] = None
    dose_cap_applied: bool = False
    source_citation: Dict[str, str] = field(default_factory=dict)
    commercial_brands: List[Dict[str, str]] = field(default_factory=list)
    magistral_formula: Optional[str] = None
    administration_instructions: List[str] = field(default_factory=list)
    cautions: List[str] = field(default_factory=list)


@dataclass
class DDIScreenResult:
    status: str  # 'SAFE', 'WARNING', 'CONTRAINDICATED'
    alerts: List[Dict[str, str]] = field(default_factory=list)  # [{'severity': 'RED'/'AMBER', 'substance': '...', 'detail': '...'}]
    recommended_alternatives: List[str] = field(default_factory=list)

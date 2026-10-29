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
    excipient_warnings: List[Dict[str, Any]] = field(default_factory=list)
    hepatic_adjustments: List[Dict[str, Any]] = field(default_factory=list)
    verification_status: str = "CLINICALLY_VERIFIED"  # 'CLINICALLY_VERIFIED' or 'AI_EXTRACTED'
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert DrugInfo to JSON-serializable dictionary."""
        return {
            "substance": self.substance,
            "atc_code": self.atc_code,
            "therapeutic_category": self.therapeutic_category,
            "intent": self.intent,
            "brands": self.brands,
            "magistral_formula": self.magistral_formula,
            "administration_instructions": self.administration_instructions,
            "cautions": self.cautions,
            "source_citation": self.source_citation,
            "excipient_warnings": self.excipient_warnings,
            "hepatic_adjustments": self.hepatic_adjustments,
            "verification_status": self.verification_status,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at,
            "dosing_rules": [
                {
                    "rule_id": r.rule_id,
                    "route": r.route,
                    "form_type": r.form_type,
                    "formula_description": r.formula_description,
                    "basis": r.basis,
                    "rate": r.rate,
                    "unit": r.unit,
                    "doses_per_day": r.doses_per_day,
                    "schedule_description": r.schedule_description,
                    "weight_min_kg": r.weight_min_kg,
                    "weight_max_kg": r.weight_max_kg,
                    "age_min_months": r.age_min_months,
                    "age_max_months": r.age_max_months,
                    "max_dose_single": r.max_dose_single,
                    "max_dose_daily": r.max_dose_daily,
                    "max_dose_per_kg_daily": r.max_dose_per_kg_daily,
                    "commercial_concentration_mg_ml": r.commercial_concentration_mg_ml,
                    "available_strengths": r.available_strengths,
                    "renal_adjustments": [
                        {
                            "crcl_min": ra.crcl_min,
                            "crcl_max": ra.crcl_max,
                            "instruction": ra.instruction,
                            "frequency_hours": ra.frequency_hours,
                            "dose_factor": ra.dose_factor,
                        }
                        for ra in r.renal_adjustments
                    ]
                }
                for r in self.dosing_rules
            ]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DrugInfo":
        """Reconstruct DrugInfo from dictionary."""
        dosing_rules = []
        for r_dict in data.get("dosing_rules", []):
            renal_adjs = [
                RenalThreshold(
                    crcl_min=ra.get("crcl_min"),
                    crcl_max=ra.get("crcl_max"),
                    instruction=ra.get("instruction", ""),
                    frequency_hours=ra.get("frequency_hours"),
                    dose_factor=ra.get("dose_factor", 1.0),
                )
                for ra in r_dict.get("renal_adjustments", [])
            ]
            rule = DosingRule(
                rule_id=r_dict.get("rule_id", ""),
                route=r_dict.get("route", "oral"),
                form_type=r_dict.get("form_type", "syrup/suspension"),
                formula_description=r_dict.get("formula_description", ""),
                basis=r_dict.get("basis", "weight"),
                rate=float(r_dict.get("rate", 0.0)),
                unit=r_dict.get("unit", "mg"),
                doses_per_day=int(r_dict.get("doses_per_day", 1)),
                schedule_description=r_dict.get("schedule_description", ""),
                weight_min_kg=r_dict.get("weight_min_kg"),
                weight_max_kg=r_dict.get("weight_max_kg"),
                age_min_months=r_dict.get("age_min_months"),
                age_max_months=r_dict.get("age_max_months"),
                max_dose_single=r_dict.get("max_dose_single"),
                max_dose_daily=r_dict.get("max_dose_daily"),
                max_dose_per_kg_daily=r_dict.get("max_dose_per_kg_daily"),
                commercial_concentration_mg_ml=r_dict.get("commercial_concentration_mg_ml"),
                available_strengths=r_dict.get("available_strengths", []),
                renal_adjustments=renal_adjs,
            )
            dosing_rules.append(rule)

        return cls(
            substance=data.get("substance", ""),
            atc_code=data.get("atc_code", ""),
            therapeutic_category=data.get("therapeutic_category", ""),
            intent=data.get("intent", "both"),
            brands=data.get("brands", []),
            magistral_formula=data.get("magistral_formula"),
            administration_instructions=data.get("administration_instructions", []),
            cautions=data.get("cautions", []),
            source_citation=data.get("source_citation", {}),
            dosing_rules=dosing_rules,
            excipient_warnings=data.get("excipient_warnings", []),
            hepatic_adjustments=data.get("hepatic_adjustments", []),
            verification_status=data.get("verification_status", "CLINICALLY_VERIFIED"),
            verified_by=data.get("verified_by"),
            verified_at=data.get("verified_at"),
        )


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
    hepatic_status_note: Optional[str] = None
    excipient_alerts: List[str] = field(default_factory=list)
    dose_cap_applied: bool = False
    source_citation: Dict[str, str] = field(default_factory=dict)
    commercial_brands: List[Dict[str, str]] = field(default_factory=list)
    magistral_formula: Optional[str] = None
    administration_instructions: List[str] = field(default_factory=list)
    cautions: List[str] = field(default_factory=list)
    verification_status: str = "CLINICALLY_VERIFIED"
    verified_by: Optional[str] = None
    verified_at: Optional[str] = None


@dataclass
class DDIScreenResult:
    status: str  # 'SAFE', 'WARNING', 'CONTRAINDICATED'
    alerts: List[Dict[str, str]] = field(default_factory=list)  # [{'severity': 'RED'/'AMBER', 'substance': '...', 'detail': '...'}]
    recommended_alternatives: List[str] = field(default_factory=list)

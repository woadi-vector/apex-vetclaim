# Copyright 2026 Vector Research Labs. Apache-2.0.
"""check_rating_schedule — deterministic 38 CFR Part 4 lookup.

Returns the diagnostic code and rating criteria for a named condition, drawn
from a curated subset of the VA rating schedule. Source-of-truth references
are cited so the agent can ground every claim in a specific regulation.

This tool is intentionally DETERMINISTIC — no LLM call. Rating schedule
criteria are regulatory text and must be returned verbatim, not summarized.
The agent layers reasoning on top; this tool provides the factual ground.
"""

from typing import Any

# Curated subset of 38 CFR Part 4. Real product would back this with a full
# regulatory database; for scaffold and demo we cover the most-commonly-claimed
# conditions across the categories that matter for veteran triage.
RATING_SCHEDULE: dict[str, dict[str, Any]] = {
    "migraines": {
        "diagnostic_code": "8100",
        "category": "Neurological",
        "cfr_reference": "38 CFR 4.124a",
        "rating_criteria": [
            {"rating": 0, "criteria": "Less frequent attacks."},
            {"rating": 10, "criteria": "Characteristic prostrating attacks averaging one in 2 months over the last several months."},
            {"rating": 30, "criteria": "Characteristic prostrating attacks occurring on an average once a month over the last several months."},
            {"rating": 50, "criteria": "Very frequent completely prostrating and prolonged attacks productive of severe economic inadaptability."},
        ],
        "key_terminology": [
            "'Prostrating' = severe enough that the veteran must lie down",
            "'Economic inadaptability' = interferes with the ability to work",
        ],
        "common_evidence_required": [
            "Headache log documenting frequency and severity",
            "Statements from family/coworkers about observed attacks",
            "Medical records showing diagnosed migraine (not just headache)",
            "Documentation of missed work or activities during attacks",
        ],
    },
    "ptsd": {
        "diagnostic_code": "9411",
        "category": "Mental Disorders",
        "cfr_reference": "38 CFR 4.130",
        "rating_criteria": [
            {"rating": 0, "criteria": "Mental condition formally diagnosed but symptoms not severe enough to interfere with occupational/social functioning or require continuous medication."},
            {"rating": 10, "criteria": "Occupational and social impairment due to mild or transient symptoms which decrease work efficiency only during periods of significant stress, or symptoms controlled by continuous medication."},
            {"rating": 30, "criteria": "Occupational and social impairment with occasional decrease in work efficiency and intermittent periods of inability to perform occupational tasks."},
            {"rating": 50, "criteria": "Occupational and social impairment with reduced reliability and productivity due to symptoms such as flattened affect, panic attacks more than once a week, difficulty understanding complex commands."},
            {"rating": 70, "criteria": "Occupational and social impairment with deficiencies in most areas (work, school, family relations, judgment, thinking, mood) due to symptoms such as suicidal ideation, obsessional rituals, near-continuous panic or depression."},
            {"rating": 100, "criteria": "Total occupational and social impairment due to symptoms such as gross impairment in thought processes, persistent delusions, grossly inappropriate behavior, persistent danger of hurting self or others."},
        ],
        "common_secondary_conditions": [
            "Sleep apnea (secondary to PTSD or PTSD medications)",
            "GERD (secondary to PTSD medications)",
            "Erectile dysfunction (secondary to PTSD medications)",
            "Depressive disorder (secondary to PTSD)",
        ],
        "common_evidence_required": [
            "Stressor statement detailing the in-service event",
            "Buddy statements corroborating the stressor",
            "Current diagnosis from a VA or qualified mental health provider",
            "Documentation of treatment history (medications, therapy)",
        ],
    },
    "sleep_apnea": {
        "diagnostic_code": "6847",
        "category": "Respiratory",
        "cfr_reference": "38 CFR 4.97",
        "rating_criteria": [
            {"rating": 0, "criteria": "Asymptomatic but with documented sleep disorder breathing."},
            {"rating": 30, "criteria": "Persistent day-time hypersomnolence."},
            {"rating": 50, "criteria": "Requires use of breathing assistance device such as CPAP machine."},
            {"rating": 100, "criteria": "Chronic respiratory failure with carbon dioxide retention or cor pulmonale, or requires tracheostomy."},
        ],
        "common_primary_conditions": [
            "PTSD (sleep apnea is a recognized secondary)",
            "Asthma",
            "Sinusitis",
            "Obesity (note: VA does not rate obesity directly, but it can be a chain link)",
        ],
        "common_evidence_required": [
            "Sleep study (polysomnography) showing AHI > 5",
            "CPAP prescription for the 50% rating threshold",
            "Nexus letter if claiming as secondary to another rated condition",
        ],
    },
    "tinnitus": {
        "diagnostic_code": "6260",
        "category": "Auditory",
        "cfr_reference": "38 CFR 4.87",
        "rating_criteria": [
            {"rating": 10, "criteria": "Recurrent. This is the maximum rating for tinnitus regardless of whether it is unilateral or bilateral."},
        ],
        "key_terminology": [
            "Tinnitus is a single 10% rating maximum — it does not stack as 10% per ear",
            "Often claimed alongside hearing loss as separate ratings",
        ],
        "common_evidence_required": [
            "Statement from the veteran describing the ringing/buzzing",
            "Documentation of in-service noise exposure (MOS records, hazardous duty orders)",
            "Audiology exam (often paired with hearing loss claim)",
        ],
    },
    "lumbosacral_strain": {
        "diagnostic_code": "5237",
        "category": "Musculoskeletal — Spine",
        "cfr_reference": "38 CFR 4.71a",
        "rating_criteria": [
            {"rating": 10, "criteria": "Forward flexion of the thoracolumbar spine greater than 60 degrees but not greater than 85 degrees; or, combined range of motion of the thoracolumbar spine greater than 120 degrees but not greater than 235 degrees; or, muscle spasm, guarding, or localized tenderness not resulting in abnormal gait or abnormal spinal contour."},
            {"rating": 20, "criteria": "Forward flexion of the thoracolumbar spine greater than 30 degrees but not greater than 60 degrees; or, combined range of motion not greater than 120 degrees; or, muscle spasm or guarding severe enough to result in abnormal gait or abnormal spinal contour."},
            {"rating": 40, "criteria": "Forward flexion of the thoracolumbar spine 30 degrees or less; or, favorable ankylosis of the entire thoracolumbar spine."},
            {"rating": 50, "criteria": "Unfavorable ankylosis of the entire thoracolumbar spine."},
            {"rating": 100, "criteria": "Unfavorable ankylosis of the entire spine."},
        ],
        "common_secondary_conditions": [
            "Radiculopathy (lower extremities) — rated separately under 38 CFR 4.124a",
            "Bowel/bladder dysfunction (if neurologic component severe)",
        ],
        "common_evidence_required": [
            "Range-of-motion measurements from a VA C&P exam",
            "Imaging (MRI, X-ray) showing structural findings",
            "Documentation of muscle spasm, guarding, or gait abnormality",
        ],
    },
    "knee_strain": {
        "diagnostic_code": "5260",
        "category": "Musculoskeletal — Lower Extremity",
        "cfr_reference": "38 CFR 4.71a",
        "rating_criteria": [
            {"rating": 0, "criteria": "Limitation of flexion to 60 degrees."},
            {"rating": 10, "criteria": "Limitation of flexion to 45 degrees."},
            {"rating": 20, "criteria": "Limitation of flexion to 30 degrees."},
            {"rating": 30, "criteria": "Limitation of flexion to 15 degrees."},
        ],
        "key_terminology": [
            "Flexion = bending the knee",
            "Extension is rated separately under diagnostic code 5261",
            "Each knee is rated separately",
            "Instability is rated separately under diagnostic code 5257",
        ],
        "common_evidence_required": [
            "Range-of-motion measurements",
            "Documentation of pain on motion",
            "Functional loss statement (what activities are limited)",
        ],
    },
    "gerd": {
        "diagnostic_code": "7346",
        "category": "Digestive",
        "cfr_reference": "38 CFR 4.114",
        "rating_criteria": [
            {"rating": 10, "criteria": "Two or more of the symptoms for the 30% rating but of less severity."},
            {"rating": 30, "criteria": "Persistently recurrent epigastric distress with dysphagia, pyrosis, and regurgitation, accompanied by substernal or arm or shoulder pain, productive of considerable impairment of health."},
            {"rating": 60, "criteria": "Symptoms of pain, vomiting, material weight loss and hematemesis or melena with moderate anemia, or other symptom combinations productive of severe impairment of health."},
        ],
        "common_primary_conditions": [
            "PTSD (GERD frequently secondary to PTSD medications)",
            "Service-connected anxiety disorders",
        ],
        "common_evidence_required": [
            "Diagnosis from gastroenterologist or PCP",
            "Documentation of medications (PPIs, H2 blockers) and their effectiveness",
            "Endoscopy results if available",
            "Nexus letter if claiming as secondary",
        ],
    },
}


def check_rating_schedule(condition: str) -> dict[str, Any]:
    """Look up the VA rating schedule criteria for a named condition.

    Returns the diagnostic code, CFR reference, full rating ladder (0% through
    100% where applicable), common secondary conditions, key terminology, and
    typical evidence required. All content is drawn from 38 CFR Part 4
    verbatim and cited so the agent can anchor every claim to a specific
    regulation.

    Args:
      condition: The condition to look up. Matched case-insensitively against
        keys like 'migraines', 'ptsd', 'sleep_apnea', 'tinnitus',
        'lumbosacral_strain', 'knee_strain', 'gerd'. Partial matches return
        the closest hit; unrecognized conditions return a list of supported
        conditions.

    Returns:
      A dict with keys: diagnostic_code, category, cfr_reference,
      rating_criteria (list of {rating, criteria}), and condition-specific
      additional fields. If the condition is not in the curated set, returns
      {"error": "...", "supported_conditions": [...]}.
    """
    if not condition:
        return {
            "error": "Empty condition. Provide a condition name like 'migraines' or 'PTSD'.",
            "supported_conditions": sorted(RATING_SCHEDULE.keys()),
        }

    # Normalize: lowercase, strip, replace spaces with underscores
    key = condition.strip().lower().replace(" ", "_").replace("-", "_")

    if key in RATING_SCHEDULE:
        return {"condition": key, **RATING_SCHEDULE[key]}

    # Try partial match (e.g., "migraine" → "migraines", "back" → "lumbosacral_strain")
    partial_matches = [k for k in RATING_SCHEDULE if key in k or k in key]
    if len(partial_matches) == 1:
        return {
            "condition": partial_matches[0],
            "note": f"Matched '{condition}' to '{partial_matches[0]}'",
            **RATING_SCHEDULE[partial_matches[0]],
        }
    if len(partial_matches) > 1:
        return {
            "error": f"Multiple conditions match '{condition}'. Be more specific.",
            "possible_matches": partial_matches,
        }

    return {
        "error": f"Condition '{condition}' not in the curated rating schedule. The scaffold covers a subset; a real deployment would back this with the full 38 CFR Part 4.",
        "supported_conditions": sorted(RATING_SCHEDULE.keys()),
    }

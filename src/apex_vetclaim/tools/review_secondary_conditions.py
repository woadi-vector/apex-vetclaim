# Copyright 2026 Vector Research Labs. Apache-2.0.
"""review_secondary_conditions — surface commonly-missed secondaries.

Given a primary service-connected condition, returns a curated list of
conditions that VA adjudicators frequently grant as secondary to that
primary. The vast majority of veterans with rated conditions are *under-rated*
because they never claimed the secondaries that flow from the primary.

This is the tool that earns the agent's value. Most VSOs don't have the
breadth to walk every vet through every possible secondary; this tool does.

DETERMINISTIC by design. The data is regulatory and case-law-driven, not
something an LLM should generate.
"""

from typing import Any

SECONDARY_MAP: dict[str, list[dict[str, Any]]] = {
    "ptsd": [
        {
            "condition": "Sleep apnea",
            "diagnostic_code": "6847",
            "nexus_basis": "PTSD is recognized to disrupt sleep architecture; sleep apnea is frequently aggravated or caused by PTSD medications (especially benzodiazepines) and chronic stress response.",
            "evidence_needed": "Sleep study (AHI > 5) + nexus letter from sleep medicine or primary care physician explicitly tying the sleep apnea to PTSD or PTSD medications.",
        },
        {
            "condition": "GERD",
            "diagnostic_code": "7346",
            "nexus_basis": "GERD is frequently secondary to PTSD medications (SSRIs, benzodiazepines) and the chronic stress response that affects gastric motility.",
            "evidence_needed": "Diagnosis from GI or PCP + documentation of medication side effects + nexus letter tying GERD to PTSD or its treatment.",
        },
        {
            "condition": "Erectile dysfunction",
            "diagnostic_code": "7522",
            "nexus_basis": "ED is a documented side effect of SSRIs commonly prescribed for PTSD. Special Monthly Compensation (SMC-K) often applies in addition to the base rating.",
            "evidence_needed": "Diagnosis + documentation of PTSD medication history + nexus letter. SMC-K adds approximately $128/month on top of the base rating.",
        },
        {
            "condition": "Depressive disorder",
            "diagnostic_code": "9434",
            "nexus_basis": "Depression frequently co-occurs with PTSD; if separately diagnosed and the symptoms can be distinguished, it can be claimed and rated separately under 38 CFR 4.130 (though typically combined into a single mental health rating).",
            "evidence_needed": "Separate diagnosis from a mental health provider + symptom differentiation from PTSD core symptoms.",
        },
        {
            "condition": "Migraine headaches",
            "diagnostic_code": "8100",
            "nexus_basis": "Stress-induced migraines are recognized as secondary to PTSD; the chronic hyperarousal can trigger or worsen migraine patterns.",
            "evidence_needed": "Diagnosed migraines (not just headaches) + headache log + nexus letter from neurology or PCP.",
        },
    ],
    "lumbosacral_strain": [
        {
            "condition": "Radiculopathy — lower extremities",
            "diagnostic_code": "8520 (sciatic nerve) or 8521 (external popliteal nerve)",
            "nexus_basis": "Radiculopathy (nerve pain radiating from the spine into the legs) is the single most-missed secondary to back conditions. Rated separately under 38 CFR 4.124a for the neurological component.",
            "evidence_needed": "EMG/nerve conduction study showing radiculopathy + statement from neurology or PM&R + documentation of pain radiation pattern.",
        },
        {
            "condition": "Bowel or bladder dysfunction",
            "diagnostic_code": "7332 (rectal) or 7517 (bladder)",
            "nexus_basis": "Severe lumbar spine conditions can cause cauda equina syndrome or otherwise impair bowel/bladder function. Rated separately if documented.",
            "evidence_needed": "Documentation from urology or GI + nexus letter tying the dysfunction to the spinal condition.",
        },
    ],
    "knee_strain": [
        {
            "condition": "Knee instability",
            "diagnostic_code": "5257",
            "nexus_basis": "Instability (slight, moderate, severe) is rated SEPARATELY from limitation of motion under VA rules. Many vets are rated only for limited flexion when they should also be rated for instability.",
            "evidence_needed": "Documentation of instability findings on C&P exam (Lachman, drawer, McMurray tests) + statement of giving-way episodes.",
        },
        {
            "condition": "Hip strain",
            "diagnostic_code": "5252",
            "nexus_basis": "Knee gait abnormalities frequently cause secondary hip strain over time as the vet compensates for the knee.",
            "evidence_needed": "Diagnosis of hip strain + nexus letter from orthopedics tying the hip condition to the altered gait from the knee.",
        },
        {
            "condition": "Lower back strain",
            "diagnostic_code": "5237",
            "nexus_basis": "Same compensation pattern as hip — altered gait from knee dysfunction cascades up the kinetic chain.",
            "evidence_needed": "Diagnosis of back strain + nexus letter linking it to gait alteration from the knee condition.",
        },
    ],
    "tinnitus": [
        {
            "condition": "Hearing loss",
            "diagnostic_code": "6100",
            "nexus_basis": "Tinnitus and hearing loss are almost always claimed together. If you're rated for tinnitus, you should be evaluated for hearing loss — and vice versa.",
            "evidence_needed": "Audiogram showing pure tone threshold and Maryland CNC speech discrimination scores.",
        },
    ],
    "sleep_apnea": [
        {
            "condition": "Hypertension",
            "diagnostic_code": "7101",
            "nexus_basis": "Untreated sleep apnea is a well-documented cause of secondary hypertension; the relationship is recognized in VA training materials.",
            "evidence_needed": "Diagnosis of hypertension + nexus letter from cardiology or PCP tying it to the sleep apnea (especially if diagnosed BEFORE the sleep apnea was controlled with CPAP).",
        },
    ],
    "migraines": [
        {
            "condition": "Depression or anxiety disorder",
            "diagnostic_code": "9434 / 9400",
            "nexus_basis": "Chronic pain conditions including migraines are recognized as causing or aggravating mental health conditions. If migraines have led to depression/anxiety, that can be claimed separately.",
            "evidence_needed": "Separate diagnosis from a mental health provider + nexus letter tying mood symptoms to the chronic migraine condition.",
        },
    ],
    "gerd": [
        {
            "condition": "Barrett's esophagus",
            "diagnostic_code": "7346 (rated under GERD until malignancy develops)",
            "nexus_basis": "Long-standing GERD can lead to Barrett's esophagus. This is a serious complication worth surveilling and documenting.",
            "evidence_needed": "Endoscopy showing Barrett's metaplasia + nexus letter from GI tying it to long-standing GERD.",
        },
    ],
}


def review_secondary_conditions(primary_condition: str) -> dict[str, Any]:
    """List commonly-claimed secondary conditions for a given primary.

    Most veterans are under-rated because they never claim the secondaries
    that flow from their service-connected primary conditions. This tool
    returns the most-commonly-granted secondary claims with nexus basis
    and evidence requirements for each.

    Args:
      primary_condition: The veteran's primary service-connected condition.
        Matched case-insensitively against the same keys as
        check_rating_schedule (e.g., 'ptsd', 'lumbosacral_strain').

    Returns:
      A dict with a list of secondary conditions, each containing
      condition name, diagnostic code, nexus basis, and evidence required.
      If the primary is not in the curated set, returns an error with
      supported primaries.
    """
    if not primary_condition:
        return {
            "error": "Empty condition. Provide a primary condition name.",
            "supported_primaries": sorted(SECONDARY_MAP.keys()),
        }

    key = primary_condition.strip().lower().replace(" ", "_").replace("-", "_")

    if key in SECONDARY_MAP:
        return {
            "primary_condition": key,
            "secondaries": SECONDARY_MAP[key],
            "caveat": "These are the most-commonly-granted secondaries. The veteran's individual case may support others; consult a VSO or qualified attorney to discuss specifics. Surface only — do not file a claim without medical evidence supporting the nexus.",
        }

    partial_matches = [k for k in SECONDARY_MAP if key in k or k in key]
    if len(partial_matches) == 1:
        match = partial_matches[0]
        return {
            "primary_condition": match,
            "note": f"Matched '{primary_condition}' to '{match}'",
            "secondaries": SECONDARY_MAP[match],
            "caveat": "These are the most-commonly-granted secondaries.",
        }

    return {
        "error": f"Primary condition '{primary_condition}' not in the curated secondary-conditions map.",
        "supported_primaries": sorted(SECONDARY_MAP.keys()),
    }

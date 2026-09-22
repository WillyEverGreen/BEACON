"""
Authoritative Registry of Regulatory Control Profiles & Persona Lenses (§25–§38).
"""

from __future__ import annotations

from app.profiles.models import PersonaLens, RegulatoryProfile

# ── §26: Default Profile — GLOBAL_WCAG_22_AA ──────────────────────────────────

GLOBAL_WCAG_22_AA = RegulatoryProfile(
    profile_id="GLOBAL_WCAG_22_AA",
    name="Global WCAG 2.2 Level AA Baseline",
    jurisdiction="International",
    scope="Web content and applications globally",
    technical_standard="W3C WCAG 2.2 Level A and AA",
    mapped_requirements={
        "1.1.1": "WCAG 2.2 SC 1.1.1 Non-text Content (A)",
        "1.2.1": "WCAG 2.2 SC 1.2.1 Audio-only and Video-only (Prerecorded) (A)",
        "1.2.2": "WCAG 2.2 SC 1.2.2 Captions (Prerecorded) (A)",
        "1.2.3": "WCAG 2.2 SC 1.2.3 Audio Description or Media Alternative (A)",
        "1.2.4": "WCAG 2.2 SC 1.2.4 Captions (Live) (AA)",
        "1.2.5": "WCAG 2.2 SC 1.2.5 Audio Description (Prerecorded) (AA)",
        "1.3.1": "WCAG 2.2 SC 1.3.1 Info and Relationships (A)",
        "1.3.2": "WCAG 2.2 SC 1.3.2 Meaningful Sequence (A)",
        "1.3.3": "WCAG 2.2 SC 1.3.3 Sensory Characteristics (A)",
        "1.3.4": "WCAG 2.2 SC 1.3.4 Orientation (AA)",
        "1.3.5": "WCAG 2.2 SC 1.3.5 Identify Input Purpose (AA)",
        "1.4.1": "WCAG 2.2 SC 1.4.1 Use of Color (A)",
        "1.4.2": "WCAG 2.2 SC 1.4.2 Audio Control (A)",
        "1.4.3": "WCAG 2.2 SC 1.4.3 Contrast (Minimum) (AA)",
        "1.4.4": "WCAG 2.2 SC 1.4.4 Resize Text (AA)",
        "1.4.5": "WCAG 2.2 SC 1.4.5 Images of Text (AA)",
        "1.4.10": "WCAG 2.2 SC 1.4.10 Reflow (AA)",
        "1.4.11": "WCAG 2.2 SC 1.4.11 Non-text Contrast (AA)",
        "1.4.12": "WCAG 2.2 SC 1.4.12 Text Spacing (AA)",
        "1.4.13": "WCAG 2.2 SC 1.4.13 Content on Hover or Focus (AA)",
        "2.1.1": "WCAG 2.2 SC 2.1.1 Keyboard (A)",
        "2.1.2": "WCAG 2.2 SC 2.1.2 No Keyboard Trap (A)",
        "2.1.4": "WCAG 2.2 SC 2.1.4 Character Key Shortcuts (A)",
        "2.2.1": "WCAG 2.2 SC 2.2.1 Timing Adjustable (A)",
        "2.2.2": "WCAG 2.2 SC 2.2.2 Pause, Stop, Hide (A)",
        "2.3.1": "WCAG 2.2 SC 2.3.1 Three Flashes or Below Threshold (A)",
        "2.4.1": "WCAG 2.2 SC 2.4.1 Bypass Blocks (A)",
        "2.4.2": "WCAG 2.2 SC 2.4.2 Page Titled (A)",
        "2.4.3": "WCAG 2.2 SC 2.4.3 Focus Order (A)",
        "2.4.4": "WCAG 2.2 SC 2.4.4 Link Purpose (In Context) (A)",
        "2.4.5": "WCAG 2.2 SC 2.4.5 Multiple Ways (AA)",
        "2.4.6": "WCAG 2.2 SC 2.4.6 Headings and Labels (AA)",
        "2.4.7": "WCAG 2.2 SC 2.4.7 Focus Visible (AA)",
        "2.4.11": "WCAG 2.2 SC 2.4.11 Focus Not Obscured (Minimum) (AA)",
        "2.5.1": "WCAG 2.2 SC 2.5.1 Pointer Gestures (A)",
        "2.5.2": "WCAG 2.2 SC 2.5.2 Pointer Cancellation (A)",
        "2.5.3": "WCAG 2.2 SC 2.5.3 Label in Name (A)",
        "2.5.4": "WCAG 2.2 SC 2.5.4 Motion Actuation (A)",
        "2.5.7": "WCAG 2.2 SC 2.5.7 Dragging Movements (AA)",
        "2.5.8": "WCAG 2.2 SC 2.5.8 Target Size (Minimum) (AA)",
        "3.1.1": "WCAG 2.2 SC 3.1.1 Language of Page (A)",
        "3.1.2": "WCAG 2.2 SC 3.1.2 Language of Parts (AA)",
        "3.2.1": "WCAG 2.2 SC 3.2.1 On Focus (A)",
        "3.2.2": "WCAG 2.2 SC 3.2.2 On Input (A)",
        "3.2.3": "WCAG 2.2 SC 3.2.3 Consistent Navigation (AA)",
        "3.2.4": "WCAG 2.2 SC 3.2.4 Consistent Identification (AA)",
        "3.2.6": "WCAG 2.2 SC 3.2.6 Consistent Help (A)",
        "3.3.1": "WCAG 2.2 SC 3.3.1 Error Identification (A)",
        "3.3.2": "WCAG 2.2 SC 3.3.2 Labels or Instructions (A)",
        "3.3.3": "WCAG 2.2 SC 3.3.3 Error Suggestion (AA)",
        "3.3.4": "WCAG 2.2 SC 3.3.4 Error Prevention (Legal, Financial, Data) (AA)",
        "3.3.7": "WCAG 2.2 SC 3.3.7 Redundant Entry (A)",
        "3.3.8": "WCAG 2.2 SC 3.3.8 Accessible Authentication (Minimum) (AA)",
        "4.1.2": "WCAG 2.2 SC 4.1.2 Name, Role, Value (A)",
        "4.1.3": "WCAG 2.2 SC 4.1.3 Status Messages (AA)",
    },
    mandatory_criteria={
        "1.1.1", "1.2.1", "1.2.2", "1.2.3", "1.2.4", "1.2.5", "1.3.1", "1.3.2", "1.3.3", "1.3.4", "1.3.5",
        "1.4.1", "1.4.2", "1.4.3", "1.4.4", "1.4.5", "1.4.10", "1.4.11", "1.4.12", "1.4.13",
        "2.1.1", "2.1.2", "2.1.4", "2.2.1", "2.2.2", "2.3.1", "2.4.1", "2.4.2", "2.4.3", "2.4.4",
        "2.4.5", "2.4.6", "2.4.7", "2.4.11", "2.5.1", "2.5.2", "2.5.3", "2.5.4", "2.5.7", "2.5.8",
        "3.1.1", "3.1.2", "3.2.1", "3.2.2", "3.2.3", "3.2.4", "3.2.6", "3.3.1", "3.3.2", "3.3.3",
        "3.3.4", "3.3.7", "3.3.8", "4.1.2", "4.1.3"
    },
    report_sections=["Executive Summary", "WCAG 2.2 Conformance Matrix", "Priority Remediations", "Technical Findings"],
)

# ── §27: US Federal / Section 508 Profile ─────────────────────────────────────

US_SECTION_508 = RegulatoryProfile(
    profile_id="US_SECTION_508",
    name="US Federal Section 508 Compliance Profile",
    jurisdiction="United States",
    scope="US Federal Agencies, Contractors, and recipients of federal funds",
    technical_standard="Revised Section 508 (incorporating WCAG 2.0 A/AA + 508 Functional Performance)",
    mapped_requirements={
        "1.1.1": "Section 508 Chapter 5 (501.1 / WCAG 2.0 1.1.1 Non-text Content)",
        "1.2.1": "Section 508 501.1 (WCAG 2.0 1.2.1 Audio/Video Prerecorded)",
        "1.2.2": "Section 508 501.1 (WCAG 2.0 1.2.2 Captions)",
        "1.2.3": "Section 508 501.1 (WCAG 2.0 1.2.3 Audio Description / Media Alternative)",
        "1.2.4": "Section 508 501.1 (WCAG 2.0 1.2.4 Captions Live)",
        "1.2.5": "Section 508 501.1 (WCAG 2.0 1.2.5 Audio Description Prerecorded)",
        "1.3.1": "Section 508 501.1 (WCAG 2.0 1.3.1 Info & Relationships)",
        "1.3.2": "Section 508 501.1 (WCAG 2.0 1.3.2 Meaningful Sequence)",
        "1.3.3": "Section 508 501.1 (WCAG 2.0 1.3.3 Sensory Characteristics)",
        "1.4.1": "Section 508 501.1 (WCAG 2.0 1.4.1 Color)",
        "1.4.2": "Section 508 501.1 (WCAG 2.0 1.4.2 Audio Control)",
        "1.4.3": "Section 508 501.1 (WCAG 2.0 1.4.3 Contrast Minimum)",
        "1.4.4": "Section 508 501.1 (WCAG 2.0 1.4.4 Resize Text)",
        "1.4.5": "Section 508 501.1 (WCAG 2.0 1.4.5 Images of Text)",
        "2.1.1": "Section 508 501.1 (WCAG 2.0 2.1.1 Keyboard)",
        "2.1.2": "Section 508 501.1 (WCAG 2.0 2.1.2 Keyboard Trap)",
        "2.2.1": "Section 508 501.1 (WCAG 2.0 2.2.1 Timing Adjustable)",
        "2.2.2": "Section 508 501.1 (WCAG 2.0 2.2.2 Pause, Stop, Hide)",
        "2.3.1": "Section 508 501.1 (WCAG 2.0 2.3.1 Three Flashes)",
        "2.4.1": "Section 508 501.1 (WCAG 2.0 2.4.1 Bypass Blocks)",
        "2.4.2": "Section 508 501.1 (WCAG 2.0 2.4.2 Page Titled)",
        "2.4.3": "Section 508 501.1 (WCAG 2.0 2.4.3 Focus Order)",
        "2.4.4": "Section 508 501.1 (WCAG 2.0 2.4.4 Link Purpose in Context)",
        "2.4.5": "Section 508 501.1 (WCAG 2.0 2.4.5 Multiple Ways)",
        "2.4.6": "Section 508 501.1 (WCAG 2.0 2.4.6 Headings and Labels)",
        "2.4.7": "Section 508 501.1 (WCAG 2.0 2.4.7 Focus Visible)",
        "3.1.1": "Section 508 501.1 (WCAG 2.0 3.1.1 Language of Page)",
        "3.1.2": "Section 508 501.1 (WCAG 2.0 3.1.2 Language of Parts)",
        "3.2.1": "Section 508 501.1 (WCAG 2.0 3.2.1 On Focus)",
        "3.2.2": "Section 508 501.1 (WCAG 2.0 3.2.2 On Input)",
        "3.2.3": "Section 508 501.1 (WCAG 2.0 3.2.3 Consistent Navigation)",
        "3.2.4": "Section 508 501.1 (WCAG 2.0 3.2.4 Consistent Identification)",
        "3.3.1": "Section 508 501.1 (WCAG 2.0 3.3.1 Error Identification)",
        "3.3.2": "Section 508 501.1 (WCAG 2.0 3.3.2 Labels or Instructions)",
        "3.3.3": "Section 508 501.1 (WCAG 2.0 3.3.3 Error Suggestion)",
        "3.3.4": "Section 508 501.1 (WCAG 2.0 3.3.4 Error Prevention)",
        "4.1.1": "Section 508 501.1 (WCAG 2.0 4.1.1 Parsing)",
        "4.1.2": "Section 508 501.1 (WCAG 2.0 4.1.2 Name, Role, Value)",
    },
    mandatory_criteria={
        "1.1.1", "1.2.1", "1.2.2", "1.2.3", "1.2.4", "1.2.5",
        "1.3.1", "1.3.2", "1.3.3",
        "1.4.1", "1.4.2", "1.4.3", "1.4.4", "1.4.5",
        "2.1.1", "2.1.2",
        "2.2.1", "2.2.2",
        "2.3.1",
        "2.4.1", "2.4.2", "2.4.3", "2.4.4", "2.4.5", "2.4.6", "2.4.7",
        "3.1.1", "3.1.2",
        "3.2.1", "3.2.2", "3.2.3", "3.2.4",
        "3.3.1", "3.3.2", "3.3.3", "3.3.4",
        "4.1.1", "4.1.2",
    },
    optional_advisory_checks={
        "1.3.4", "1.3.5", "1.4.10", "1.4.11", "1.4.12", "1.4.13",
        "2.1.4", "2.5.1", "2.5.2", "2.5.3", "2.5.4", "2.5.7", "2.5.8",
        "3.2.6", "3.3.7", "3.3.8", "4.1.3"
    },  # Post-WCAG 2.0 additions (WCAG 2.1 / 2.2 best practices)
    report_sections=["Section 508 Overview", "VPAT/ACR Supporting Findings", "WCAG 2.0 Mapped Clauses", "Scope Notes"],
    disclaimer=(
        "Technical assessment only. This evaluation maps detected evidence against the selected "
        "Revised Section 508 criteria (incorporating WCAG 2.0 Level A/AA). It does not constitute "
        "legal advice, formal ACR/VPAT certification, or a government determination of compliance."
    ),
    verification_source={
        "authority": "U.S. Access Board (36 CFR Part 1194)",
        "standard": "Revised Section 508 Chapter 5",
        "retrieved_at": "2026-04-01",
        "status": "current",
    },
)

# ── §28: UK Public Sector Profile ─────────────────────────────────────────────

UK_PUBLIC_SECTOR = RegulatoryProfile(
    profile_id="UK_PUBLIC_SECTOR",
    name="UK Public Sector Bodies Accessibility Regulations 2018",
    jurisdiction="United Kingdom",
    scope="UK Central Government, Local Authorities, NHS, and Public Sector bodies",
    technical_standard="GOV.UK Accessibility Guidance (WCAG 2.2 Level AA + Accessibility Statement)",
    mapped_requirements={
        "1.1.1": "PSBAR 2018 / WCAG 2.2 1.1.1 Non-text Content",
        "1.3.1": "PSBAR 2018 / WCAG 2.2 1.3.1 Info & Relationships",
        "1.4.3": "PSBAR 2018 / WCAG 2.2 1.4.3 Contrast (Minimum)",
        "2.1.1": "PSBAR 2018 / WCAG 2.2 2.1.1 Keyboard Accessible",
        "2.4.7": "PSBAR 2018 / WCAG 2.2 2.4.7 Focus Visible",
        "2.4.11": "PSBAR 2018 / WCAG 2.2 2.4.11 Focus Not Obscured (Minimum)",
        "2.5.8": "PSBAR 2018 / WCAG 2.2 2.5.8 Target Size (Minimum)",
        "3.2.6": "PSBAR 2018 / WCAG 2.2 3.2.6 Consistent Help",
        "3.3.7": "PSBAR 2018 / WCAG 2.2 3.3.7 Redundant Entry",
        "3.3.8": "PSBAR 2018 / WCAG 2.2 3.3.8 Accessible Authentication",
        "4.1.2": "PSBAR 2018 / WCAG 2.2 4.1.2 Name, Role, Value",
        "statement": "Public Sector Bodies Regulation 8 (Accessibility Statement Requirement)",
    },
    mandatory_criteria={
        "1.1.1", "1.3.1", "1.4.3", "2.1.1", "2.4.7", "2.4.11", "2.5.8", "3.2.6", "3.3.7", "3.3.8", "4.1.2"
    },
    report_sections=["PSBAR 2018 Summary", "WCAG 2.2 Technical Findings", "Accessibility Statement Audit", "Disproportionate Burden Notes"],
    disclaimer=(
        "Technical assessment per Central Digital and Data Office (CDDO) and GOV.UK guidance. "
        "Does not constitute legal certification under the Public Sector Bodies Accessibility Regulations 2018."
    ),
    verification_source={
        "authority": "Central Digital and Data Office (CDDO), UK Government",
        "standard": "PSBAR 2018 (WCAG 2.2 AA)",
        "retrieved_at": "2026-04-01",
        "status": "current",
    },
)

# ── §29: EU Accessibility Profile (EN 301 549 / EAA) ──────────────────────────

EU_EN_301_549 = RegulatoryProfile(
    profile_id="EU_EN_301_549",
    name="EU EN 301 549 & European Accessibility Act (EAA)",
    jurisdiction="European Union",
    scope="EU Public Sector and commercial services covered under Directive 2019/882 (EAA)",
    technical_standard="EN 301 549 V3.2.1 Chapter 9 (Web) & WCAG 2.1/2.2 AA",
    mapped_requirements={
        "1.1.1": "EN 301 549 Clause 9.1.1.1 Non-text content",
        "1.3.1": "EN 301 549 Clause 9.1.3.1 Info and relationships",
        "1.4.3": "EN 301 549 Clause 9.1.4.3 Contrast minimum",
        "1.4.10": "EN 301 549 Clause 9.1.4.10 Reflow",
        "1.4.11": "EN 301 549 Clause 9.1.4.11 Non-text contrast",
        "2.1.1": "EN 301 549 Clause 9.2.1.1 Keyboard",
        "2.1.2": "EN 301 549 Clause 9.2.1.2 No keyboard trap",
        "2.4.7": "EN 301 549 Clause 9.2.4.7 Focus visible",
        "2.5.8": "EN 301 549 Clause 9.2.5.8 Target size",
        "3.3.8": "EN 301 549 Clause 9.3.3.8 Accessible authentication",
        "4.1.2": "EN 301 549 Clause 9.4.1.2 Name, role, value",
    },
    mandatory_criteria={
        "1.1.1", "1.3.1", "1.4.3", "1.4.10", "1.4.11", "2.1.1", "2.1.2", "2.4.7", "2.5.8", "3.3.8", "4.1.2"
    },
    report_sections=["EAA / EN 301 549 Compliance Matrix", "Chapter 9 Web Clauses", "Technical Findings", "Scope & Exemption Notes"],
    disclaimer=(
        "Technical assessment against ETSI EN 301 549 Chapter 9 technical specifications. "
        "Does not constitute legal proof of conformity for European Accessibility Act (Directive 2019/882) obligations."
    ),
    verification_source={
        "authority": "ETSI / CEN / CENELEC",
        "standard": "EN 301 549 V3.2.1 (harmonised European standard)",
        "retrieved_at": "2026-04-01",
        "status": "current",
    },
)

# ── §30: India Government Profile (GIGW 3.0) ──────────────────────────────────

INDIA_GIGW_3 = RegulatoryProfile(
    profile_id="INDIA_GIGW_3",
    name="India Guidelines for Indian Government Websites (GIGW 3.0)",
    jurisdiction="India",
    scope="Indian Government Ministries, Departments, Public Sector Undertakings, and State Portals",
    technical_standard="GIGW 3.0 (aligned with WCAG 2.1/2.2 AA)",
    mapped_requirements={
        "1.1.1": "GIGW 3.0 Quality Check 6.1 (Alt text for non-text content)",
        "1.3.1": "GIGW 3.0 Quality Check 6.2 (Semantic markup and headings)",
        "1.4.1": "GIGW 3.0 Quality Check 6.3 (Color independence)",
        "1.4.3": "GIGW 3.0 Quality Check 6.4 (Contrast ratio)",
        "2.1.1": "GIGW 3.0 Quality Check 6.5 (Full keyboard accessibility)",
        "2.4.2": "GIGW 3.0 Quality Check 6.6 (Meaningful page titles)",
        "3.1.1": "GIGW 3.0 Quality Check 6.7 (Default language specified)",
        "4.1.2": "GIGW 3.0 Quality Check 6.8 (Form labels and accessible names)",
    },
    mandatory_criteria={
        "1.1.1", "1.3.1", "1.4.1", "1.4.3", "2.1.1", "2.4.2", "3.1.1", "4.1.2"
    },
    report_sections=["GIGW 3.0 Quality Matrix", "Bilingual / Multi-lingual Assessment", "Technical Findings", "STQC Readiness Notes"],
    disclaimer=(
        "Technical evaluation against GIGW 3.0 accessibility checkpoints. Does not constitute formal legal compliance advice. "
        "Formal certification must be obtained through the Standardization Testing and Quality Certification (STQC) Directorate."
    ),
    verification_source={
        "authority": "National Informatics Centre (NIC), Ministry of Electronics & IT (MeitY)",
        "standard": "GIGW 3.0",
        "retrieved_at": "2026-04-01",
        "status": "current",
    },
)

REGULATORY_PROFILES: dict[str, RegulatoryProfile] = {
    "GLOBAL_WCAG_22_AA": GLOBAL_WCAG_22_AA,
    "US_SECTION_508": US_SECTION_508,
    "UK_PUBLIC_SECTOR": UK_PUBLIC_SECTOR,
    "EU_EN_301_549": EU_EN_301_549,
    "INDIA_GIGW_3": INDIA_GIGW_3,
}


# ── §32–§38: Persona Lenses ───────────────────────────────────────────────────

PERSONA_LENSES: dict[str, PersonaLens] = {
    "SCREEN_READER": PersonaLens(
        id="SCREEN_READER",
        name="Screen Reader Lens",
        description="Perspective of users relying on screen readers (NVDA, JAWS, VoiceOver, TalkBack).",
        relevant_criteria={"1.1.1", "1.3.1", "1.3.2", "2.4.2", "2.4.4", "2.4.6", "4.1.2", "4.1.3"},
        user_impact_template="A screen reader user may encounter this element without receiving an announced name, role, or context.",
    ),
    "KEYBOARD_MOTOR": PersonaLens(
        id="KEYBOARD_MOTOR",
        name="Keyboard & Motor Lens",
        description="Perspective of users navigating without a mouse (keyboard, switch device, head pointer).",
        relevant_criteria={"2.1.1", "2.1.2", "2.1.4", "2.4.1", "2.4.3", "2.4.7", "2.4.11", "2.5.7", "2.5.8"},
        user_impact_template="A keyboard or switch device user may be unable to reach, see, or interact with this control.",
    ),
    "LOW_VISION": PersonaLens(
        id="LOW_VISION",
        name="Low Vision & Color Lens",
        description="Perspective of users with partial sight, color blindness, or reduced contrast sensitivity.",
        relevant_criteria={"1.4.1", "1.4.3", "1.4.4", "1.4.10", "1.4.11", "1.4.12", "2.4.11", "2.5.8"},
        user_impact_template="A user with low vision or color vision deficiency may not perceive this text or visual element.",
    ),
    "COGNITIVE": PersonaLens(
        id="COGNITIVE",
        name="Cognitive & Learning Lens",
        description="Perspective of users with cognitive, neurodivergent, attention, or memory differences.",
        relevant_criteria={"2.2.1", "2.2.2", "3.1.5", "3.2.3", "3.2.4", "3.2.6", "3.3.1", "3.3.2", "3.3.7", "3.3.8"},
        user_impact_template="A user with cognitive or executive function needs may experience disorientation, memory burden, or unexpected behavior.",
    ),
    "DEAF_HARD_OF_HEARING": PersonaLens(
        id="DEAF_HARD_OF_HEARING",
        name="Deaf & Hard of Hearing Lens",
        description="Perspective of users who are deaf or hard of hearing requiring visual alternatives to audio.",
        relevant_criteria={"1.2.1", "1.2.2", "1.2.3", "1.2.4", "1.2.5", "1.4.2"},
        user_impact_template="A deaf or hard of hearing user may be unable to access information presented solely in audio format.",
    ),
}

# AARI Nexus | Email-derived business intelligence baseline

Date: 2026-10-13. Status: exploratory evidence, not verified financial or enrollment reporting. Source: authenticated Gmail searches; email subjects and labels, not full-thread adjudication. This document is intended for Nexus ingestion; repository storage is not evidence of live Azure ingestion.

## Scope and counts
- `label:"AARI/02 Grants & Funding" newer_than:180d`: 96 matching messages, no next page.
- `label:"AARI/03 Partners" newer_than:90d`: first 98 returned, additional page present.
- `label:"AARI/04 Programs & Scholars" newer_than:90d`: first 84 returned, additional page present.
- Counts are messages, not unique opportunities or partners; labels overlap, and search pagination limits completeness.

## Actionable signals to verify
| Domain | Evidence from message subjects | Verification / next action |
|---|---|---|
| Funding | `RE: AARI: $100K equipment application and one-year operating-history question` | Determine eligibility rule, application deadline, amount actually requested and owner. Do not count $100K as awarded. |
| Funding | `Notice of Non-Selection: Supply Chain Acceleration and Logistics Enablement (SCALE) NOFO` | Record declined outcome and review rationale before pursuing similar programs. |
| Funding | `Salesforce Accelerator - Agents for Impact: Letter of Interest Received & Updated Selection Timeline` | Record LOI submitted, retrieve selection timeline and next action. |
| Funding | `Re: Congratulations! | QTS Grant Award Notification for AARI` | Read full thread and award documentation to verify award amount, restrictions, disbursement, and recognition before reporting funds secured. |
| Funding | `Re: AARI board challenge: $25,000 by November 30` | Confirm whether this is a target, pledge, or actual commitment. |
| Partners | `RE: SHIFT follow-up | AARI + Southern Company` | Identify decision maker, requested contribution and next meeting. |
| Partners | `RE: AUC to QTS: internship timeline and student resumes` | Verify employer-hosted internship slots, deadlines and placement outcomes. |
| Partners | `Re: AARI x Google Pilot: Next Steps` | Extract commitments and pilot milestones. |
| Partners | `Re: AARI + Georgia Piedmont Tech | AI Infrastructure and Technical Workforce Partnership` | Extract partnership stage and training commitments. |
| Infrastructure | `Preliminary electrical capacity inquiry: Douglass Elementary community technology campus` and `Preliminary use and zoning inquiry: Douglass Elementary` | Track power, zoning, blockers, owner and response dates separately. |
| Students | `PCI student recruitment: AARI applications due October 12`, `Help South Fulton students explore careers behind AI`, `Help Union City students explore careers behind AI`, `East Point Students for AARI Data Center Cohort` | Attribute referrals to recruiting source and reconcile with actual Nexus registrations. Use AI Data Factory in new outward-facing copy. |

## Proposed operational tables
1. `opportunities`: id, organization, type, ask_usd, committed_usd, received_usd, stage, deadline, restrictions, owner, evidence_message_id, verified_at.
2. `partner_pipeline`: organization, contact, sector, stage, requested_contribution, next_action, next_action_due, last_meaningful_response, evidence_message_id.
3. `student_pipeline`: student_id (pseudonymous), referral_source, application_date, cohort, training_status, interview, internship_host, placement_outcome. Join only through approved identifiers in Nexus.
4. `blockers`: project, blocker_type, owner, opened_at, due_at, resolved_at, impact, evidence_message_id.

## Core metrics
- $10,000,000 funding goal: track requested, committed, awarded, received separately; never add them together.
- Partner conversion: introduction -> reply -> meeting -> documented commitment -> delivered contribution.
- Student funnel: referred -> applied -> enrolled -> completed -> interviewed -> employer-hosted internship -> job placement.
- Follow-up: business days since last meaningful response; overdue owner-assigned actions.
- Project blockers: days unresolved for power, zoning, equipment, facilities and employer commitments.

## Data governance and implementation
- This baseline contains no student names, addresses, email bodies, or private contact details.
- Do not interpret `IMPORTANT` labels, high email counts, or subject wording as commitments.
- Before automation: validate Gmail thread extraction, deduplicate by thread/opportunity, classify outcomes with human review, and maintain evidence links and confidence flags.
- Persist only approved fields into Nexus's Azure-backed data store, with least-privilege access and retention controls. No live Azure write or Power BI/Power Apps refresh was performed by this commit.
- Next engineering milestone: add an authenticated Gmail ingestion adapter, incremental sync, normalization, source-evidence lineage, review queue, and BI endpoint. Deployment requires review/approval.

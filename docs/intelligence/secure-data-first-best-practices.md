# Build From Trusted Data, Not From the Demo: AARI's AI Engineering Playbook

**Draft for external adaptation | 2026-10-13**

A model that delivers a convincing answer is not necessarily a system that delivers a correct answer. The most expensive enterprise AI mistakes often begin with a beautifully demonstrated experience, then fail when the system has to distinguish stale information, conflicting records, missing authorization, and numerical truth.

The AARI Nexus effort starts with a different question: **What secure, authoritative, already-available data can we use before building anything else?**

## Principle 1: Inventory before architecture

In a real organization, useful infrastructure already exists: cloud databases, identity, CRM-like records, shared applications and operational communications. Creating a fresh vector database because a prototype needs embeddings can introduce parallel truth, additional expense, new security exposure and hard-to-debug synchronization problems. The right first deliverable is an evidence-based inventory of existing resources and their owners.

## Principle 2: Separate evidence from facts and decisions

An email can document a proposed grant, an award notice or a promise to send payment. None of those alone proves cleared cash. In our initial case, QTS's award notice established a $15,000 grant. AARI later confirmed receipt of the check. Those are different events and both must be represented accurately; bank clearing remains a separate reconciliation step. An AI assistant must not turn a proposed $100,000 request into booked funding.

That distinction belongs in the SQL data model and business rules, not in an LLM's memory.

## Principle 3: Use RAG for evidence, SQL for arithmetic

Retrieval-augmented generation helps users ask conversational questions about source documents. Structured SQL views calculate verified metrics. The language model can compare, synthesize and explain, but official funding and student-outcome totals should come from deterministic, governed queries.

RAG is not one giant semantic search call. It combines access control, metadata filters, document retrieval, source linking, appropriate context limits, answer verification and explicit uncertainty.

## Principle 4: The user should not care where the answer lives

A business leader should be able to ask, 'Which partners are closest to funding a workforce program and what is blocking them?' without learning database tables or toggling between multiple dashboards. The answer can be served through a business application, a bot or an authorized ChatGPT connection. Different front ends should share the same governed back end and source evidence.

## Principle 5: 'Model strategy' does not mean training a model

Start with an existing Azure-hosted general model and a tested retrieval layer. Add embeddings only when measured retrieval quality requires them. Train a specialized classifier or fine-tune later, after collecting permissioned and labeled examples and demonstrating improvement. Avoid training a foundation model to compensate for missing data engineering.

## Principle 6: Security is a data-path property

Authenticate before retrieval, enforce row-level source authorization, minimize and classify stored personal data, use scoped access and managed identities, protect secrets, log access, and treat every email body as untrusted content. Data governance cannot be bolted onto the dashboard after it launches.

## Principle 7: Production is an evaluation, not a screenshot

A release passes when answers match reconciled data; citations open the right sources; new messages propagate within a measured interval; wrong or unauthorized questions are refused; the system survives a restart; operating costs remain visible; and owners know what to do when a source is disconnected.

**A useful rule:** build the shortest end-to-end verified path first, then scale the parts that actually constrain accuracy, reliability or adoption.

## AARI's operating definition of success

AARI is not trying to create another AI demonstration. It is building a working intelligence capability for its AI Data Factory workforce mission: funding pipeline, employer partnerships, student pathways and infrastructure decisions. The system succeeds when its users can make better decisions from secure, current and attributable data.

**Publication note:** This is an engineering best-practices draft. Do not publicly describe the planned Nexus features as deployed, or publish internal URLs, identities, individual correspondence, financial records beyond approved disclosures, or private architecture findings.

-- REVIEW ONLY. Execute with sqlcmd -b ONLY after schema/data/identity/network gates.
-- One-time additive migration in the EXISTING reviewed staging database.
-- No database creation, seed data, student data, destructive DDL or runtime hook.
:ON ERROR EXIT
SET XACT_ABORT ON;
IF SCHEMA_ID(N'nexus_intelligence') IS NOT NULL
    THROW 51000, 'Schema already exists; inspect migration state instead of overwriting.', 1;
BEGIN TRANSACTION;
EXEC(N'CREATE SCHEMA nexus_intelligence AUTHORIZATION dbo');
GO

CREATE TABLE nexus_intelligence.data_scope (
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    retention_days int NOT NULL CHECK (retention_days BETWEEN 1 AND 3650),
    PRIMARY KEY (tenant_id, scope_key)
);

-- Administrator-owned allowlist. Runtime roles cannot read or change this table.
-- This constrains SQL principals; per-human caller authorization is ALSO required
-- before retrieval when Container Apps shares a managed identity/connection pool.
CREATE TABLE nexus_intelligence.principal_scope_access (
    principal_name sysname NOT NULL,
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    PRIMARY KEY (principal_name, tenant_id, scope_key),
    FOREIGN KEY (tenant_id, scope_key) REFERENCES nexus_intelligence.data_scope
);

CREATE TABLE nexus_intelligence.organization (
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    organization_id uniqueidentifier NOT NULL,
    display_name nvarchar(200) NOT NULL,
    PRIMARY KEY (tenant_id, scope_key, organization_id),
    FOREIGN KEY (tenant_id, scope_key) REFERENCES nexus_intelligence.data_scope
);

CREATE TABLE nexus_intelligence.source_message (
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    source_message_id uniqueidentifier NOT NULL,
    provider nvarchar(32) NOT NULL,
    account_key nvarchar(64) NOT NULL, -- opaque source account key, not mailbox address
    upstream_message_id nvarchar(128) NOT NULL,
    upstream_thread_id nvarchar(128) NULL,
    source_url nvarchar(1000) NULL, -- caller access/link validity checked separately
    observed_at datetime2(3) NOT NULL,
    retention_until datetime2(3) NOT NULL,
    classification varchar(16) NOT NULL CHECK (classification IN ('INTERNAL','RESTRICTED')),
    index_allowed bit NOT NULL DEFAULT 0,
    record_state varchar(16) NOT NULL DEFAULT 'ACTIVE' CHECK (record_state IN ('ACTIVE','DELETED','RETRACTED')),
    content_hash binary(32) NULL,
    PRIMARY KEY (tenant_id, scope_key, source_message_id),
    UNIQUE (tenant_id, scope_key, provider, account_key, upstream_message_id),
    CHECK (retention_until > observed_at),
    CHECK (index_allowed = 0 OR classification = 'INTERNAL'),
    FOREIGN KEY (tenant_id, scope_key) REFERENCES nexus_intelligence.data_scope
);

CREATE TABLE nexus_intelligence.evidence (
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    evidence_id uniqueidentifier NOT NULL,
    source_message_id uniqueidentifier NULL,
    evidence_kind varchar(24) NOT NULL CHECK (evidence_kind IN ('SOURCE_MESSAGE','ATTESTATION','BANK_RECONCILIATION','EXECUTIVE_CONFIRMATION','CURATED_SEED')),
    source_reference nvarchar(500) NOT NULL,
    observed_at datetime2(3) NOT NULL,
    expires_at datetime2(3) NOT NULL,
    review_state varchar(16) NOT NULL DEFAULT 'PENDING' CHECK (review_state IN ('PENDING','APPROVED','REJECTED','RETRACTED')),
    reviewer_key nvarchar(128) NULL, -- opaque approved reviewer, not email address
    reviewed_at datetime2(3) NULL,
    PRIMARY KEY (tenant_id, scope_key, evidence_id),
    CHECK (expires_at > observed_at),
    CHECK (review_state <> 'APPROVED' OR (reviewer_key IS NOT NULL AND reviewed_at IS NOT NULL)),
    CHECK (evidence_kind <> 'SOURCE_MESSAGE' OR source_message_id IS NOT NULL),
    FOREIGN KEY (tenant_id, scope_key) REFERENCES nexus_intelligence.data_scope,
    FOREIGN KEY (tenant_id, scope_key, source_message_id) REFERENCES nexus_intelligence.source_message
);

CREATE TABLE nexus_intelligence.contact (
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    contact_id uniqueidentifier NOT NULL,
    organization_id uniqueidentifier NOT NULL,
    display_name nvarchar(200) NOT NULL,
    evidence_id uniqueidentifier NOT NULL,
    PRIMARY KEY (tenant_id, scope_key, contact_id),
    UNIQUE (tenant_id, scope_key, organization_id, contact_id),
    FOREIGN KEY (tenant_id, scope_key, organization_id) REFERENCES nexus_intelligence.organization,
    FOREIGN KEY (tenant_id, scope_key, evidence_id) REFERENCES nexus_intelligence.evidence
);

CREATE TABLE nexus_intelligence.funding_opportunity (
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    opportunity_id uniqueidentifier NOT NULL,
    organization_id uniqueidentifier NOT NULL,
    stable_source_key nvarchar(128) NOT NULL,
    purpose nvarchar(500) NOT NULL,
    currency char(3) NOT NULL CHECK (currency LIKE '[A-Z][A-Z][A-Z]'),
    proposed_ask decimal(19,2) NULL CHECK (proposed_ask >= 0),
    ask_evidence_id uniqueidentifier NULL,
    eligibility_state varchar(16) NOT NULL DEFAULT 'UNRESOLVED' CHECK (eligibility_state IN ('UNRESOLVED','ELIGIBLE','INELIGIBLE')),
    disposition varchar(16) NOT NULL DEFAULT 'OPEN' CHECK (disposition IN ('OPEN','NOT_SELECTED','WITHDRAWN','CLOSED')),
    PRIMARY KEY (tenant_id, scope_key, opportunity_id),
    UNIQUE (tenant_id, scope_key, stable_source_key),
    CHECK (proposed_ask IS NULL OR ask_evidence_id IS NOT NULL),
    FOREIGN KEY (tenant_id, scope_key, organization_id) REFERENCES nexus_intelligence.organization,
    FOREIGN KEY (tenant_id, scope_key, ask_evidence_id) REFERENCES nexus_intelligence.evidence
);

-- Each event is a cumulative amount snapshot PER STATE, not a cash transaction.
-- Revisions correct that snapshot. Never SUM revisions or award+receipt+deposit.
CREATE TABLE nexus_intelligence.status_event (
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    event_id uniqueidentifier NOT NULL,
    opportunity_id uniqueidentifier NOT NULL,
    financial_state varchar(16) NOT NULL CHECK (financial_state IN ('PROPOSED','SUBMITTED','AWARDED','RECEIVED','DEPOSITED','RECONCILED')),
    snapshot_revision int NOT NULL CHECK (snapshot_revision > 0),
    cumulative_amount decimal(19,2) NOT NULL CHECK (cumulative_amount >= 0),
    evidence_id uniqueidentifier NOT NULL,
    observed_at datetime2(3) NOT NULL,
    recorded_at datetime2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
    record_state varchar(16) NOT NULL DEFAULT 'ACTIVE' CHECK (record_state IN ('ACTIVE','RETRACTED')),
    review_state varchar(16) NOT NULL DEFAULT 'PENDING' CHECK (review_state IN ('PENDING','APPROVED','REJECTED')),
    PRIMARY KEY (tenant_id, scope_key, event_id),
    UNIQUE (tenant_id, scope_key, opportunity_id, financial_state, snapshot_revision),
    FOREIGN KEY (tenant_id, scope_key, opportunity_id) REFERENCES nexus_intelligence.funding_opportunity,
    FOREIGN KEY (tenant_id, scope_key, evidence_id) REFERENCES nexus_intelligence.evidence
);

-- A contact is not a budget controller without an independently reviewed claim.
CREATE TABLE nexus_intelligence.budget_authority (
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    authority_id uniqueidentifier NOT NULL,
    organization_id uniqueidentifier NOT NULL,
    controller_contact_id uniqueidentifier NOT NULL,
    budget_description nvarchar(500) NOT NULL,
    authority_kind varchar(24) NOT NULL CHECK (authority_kind IN ('CONTROLS_BUDGET','APPROVES_REQUEST','INFLUENCES_ONLY')),
    evidence_id uniqueidentifier NOT NULL,
    observed_at datetime2(3) NOT NULL,
    PRIMARY KEY (tenant_id, scope_key, authority_id),
    FOREIGN KEY (tenant_id, scope_key, organization_id, controller_contact_id) REFERENCES nexus_intelligence.contact(tenant_id, scope_key, organization_id, contact_id),
    FOREIGN KEY (tenant_id, scope_key, evidence_id) REFERENCES nexus_intelligence.evidence
);

CREATE TABLE nexus_intelligence.action_item (
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    action_id uniqueidentifier NOT NULL,
    opportunity_id uniqueidentifier NOT NULL,
    contact_id uniqueidentifier NULL,
    action_kind varchar(16) NOT NULL CHECK (action_kind IN ('DISCOVERY','SUBMISSION','FOLLOW_UP')),
    next_action nvarchar(500) NOT NULL,
    blockers nvarchar(1000) NULL,
    reviewed_priority int NOT NULL CHECK (reviewed_priority > 0),
    due_at datetime2(3) NULL,
    evidence_id uniqueidentifier NOT NULL,
    action_state varchar(16) NOT NULL DEFAULT 'PENDING' CHECK (action_state IN ('PENDING','APPROVED','DONE','CANCELLED')),
    PRIMARY KEY (tenant_id, scope_key, action_id),
    FOREIGN KEY (tenant_id, scope_key, opportunity_id) REFERENCES nexus_intelligence.funding_opportunity,
    FOREIGN KEY (tenant_id, scope_key, contact_id) REFERENCES nexus_intelligence.contact,
    FOREIGN KEY (tenant_id, scope_key, evidence_id) REFERENCES nexus_intelligence.evidence
);

CREATE TABLE nexus_intelligence.evidence_chunk (
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    chunk_id uniqueidentifier NOT NULL,
    evidence_id uniqueidentifier NOT NULL,
    chunk_ordinal int NOT NULL CHECK (chunk_ordinal >= 0),
    minimized_excerpt nvarchar(2000) NOT NULL, -- never full thread bodies
    PRIMARY KEY (tenant_id, scope_key, chunk_id),
    UNIQUE (tenant_id, scope_key, evidence_id, chunk_ordinal),
    FOREIGN KEY (tenant_id, scope_key, evidence_id) REFERENCES nexus_intelligence.evidence
);

CREATE TABLE nexus_intelligence.ingestion_state (
    tenant_id uniqueidentifier NOT NULL,
    scope_key nvarchar(64) NOT NULL,
    provider nvarchar(32) NOT NULL,
    account_key nvarchar(64) NOT NULL,
    history_cursor nvarchar(200) NULL, -- cursor only, never OAuth refresh token
    last_success_at datetime2(3) NULL,
    source_observed_at datetime2(3) NULL,
    checkpoint_version rowversion,
    PRIMARY KEY (tenant_id, scope_key, provider, account_key),
    FOREIGN KEY (tenant_id, scope_key) REFERENCES nexus_intelligence.data_scope
);
GO

CREATE FUNCTION nexus_intelligence.fn_scope_access(@tenant_id uniqueidentifier, @scope_key nvarchar(64))
RETURNS TABLE WITH SCHEMABINDING
AS RETURN SELECT 1 AS allowed
WHERE EXISTS (
    SELECT 1 FROM nexus_intelligence.principal_scope_access AS a
    WHERE a.principal_name = USER_NAME() AND a.tenant_id = @tenant_id AND a.scope_key = @scope_key
);
GO

CREATE SECURITY POLICY nexus_intelligence.source_scope_policy
ADD FILTER PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.data_scope,
ADD FILTER PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.organization,
ADD FILTER PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.source_message,
ADD FILTER PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.evidence,
ADD FILTER PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.contact,
ADD FILTER PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.funding_opportunity,
ADD FILTER PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.status_event,
ADD FILTER PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.budget_authority,
ADD FILTER PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.action_item,
ADD FILTER PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.evidence_chunk,
ADD FILTER PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.ingestion_state,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.organization AFTER INSERT,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.organization AFTER UPDATE,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.source_message AFTER INSERT,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.source_message AFTER UPDATE,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.evidence AFTER INSERT,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.evidence AFTER UPDATE,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.contact AFTER INSERT,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.contact AFTER UPDATE,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.funding_opportunity AFTER INSERT,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.funding_opportunity AFTER UPDATE,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.status_event AFTER INSERT,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.status_event AFTER UPDATE,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.budget_authority AFTER INSERT,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.budget_authority AFTER UPDATE,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.action_item AFTER INSERT,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.action_item AFTER UPDATE,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.evidence_chunk AFTER INSERT,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.evidence_chunk AFTER UPDATE,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.ingestion_state AFTER INSERT,
ADD BLOCK PREDICATE nexus_intelligence.fn_scope_access(tenant_id, scope_key) ON nexus_intelligence.ingestion_state AFTER UPDATE
WITH (STATE = ON, SCHEMABINDING = ON);
GO

CREATE VIEW nexus_intelligence.v_approved_evidence AS
SELECT e.tenant_id, e.scope_key, e.evidence_id, e.evidence_kind,
       e.source_reference, e.observed_at, e.expires_at, s.source_url
FROM nexus_intelligence.evidence AS e
LEFT JOIN nexus_intelligence.source_message AS s
 ON s.tenant_id = e.tenant_id AND s.scope_key = e.scope_key AND s.source_message_id = e.source_message_id
WHERE e.review_state = 'APPROVED' AND e.expires_at > SYSUTCDATETIME()
 AND (e.source_message_id IS NULL OR (s.record_state = 'ACTIVE' AND s.retention_until > SYSUTCDATETIME()));
GO

CREATE VIEW nexus_intelligence.v_funding_by_opportunity AS
WITH ranked AS (
 SELECT s.*, ROW_NUMBER() OVER (
  PARTITION BY tenant_id, scope_key, opportunity_id, financial_state ORDER BY snapshot_revision DESC
 ) AS rn FROM nexus_intelligence.status_event AS s WHERE review_state = 'APPROVED'
), verified AS (
 SELECT r.tenant_id, r.scope_key, r.opportunity_id, r.financial_state,
  CASE WHEN r.record_state = 'ACTIVE' AND e.evidence_id IS NOT NULL
    AND (r.financial_state <> 'DEPOSITED' OR e.evidence_kind IN ('EXECUTIVE_CONFIRMATION','BANK_RECONCILIATION'))
    AND (r.financial_state <> 'RECONCILED' OR e.evidence_kind = 'BANK_RECONCILIATION')
   THEN r.cumulative_amount END AS amount,
  r.observed_at, e.evidence_kind
 FROM ranked AS r LEFT JOIN nexus_intelligence.v_approved_evidence AS e
 ON e.tenant_id=r.tenant_id AND e.scope_key=r.scope_key AND e.evidence_id=r.evidence_id
 WHERE r.rn=1
)
SELECT o.tenant_id, o.scope_key, o.opportunity_id, o.currency,
 MAX(CASE WHEN v.financial_state='AWARDED' THEN v.amount END) AS awarded,
 MAX(CASE WHEN v.financial_state='RECEIVED' THEN v.amount END) AS received,
 MAX(CASE WHEN v.financial_state='DEPOSITED' THEN v.amount END) AS deposited,
 MAX(CASE WHEN v.financial_state='RECONCILED' THEN v.amount END) AS reconciled,
 MAX(CASE WHEN v.financial_state='DEPOSITED' AND v.amount IS NOT NULL THEN v.evidence_kind END) AS deposit_evidence_kind,
 MAX(v.observed_at) AS observed_at
FROM nexus_intelligence.funding_opportunity AS o LEFT JOIN verified AS v
 ON v.tenant_id=o.tenant_id AND v.scope_key=o.scope_key AND v.opportunity_id=o.opportunity_id
GROUP BY o.tenant_id, o.scope_key, o.opportunity_id, o.currency;
GO

CREATE VIEW nexus_intelligence.v_funding_totals AS
SELECT tenant_id, scope_key, currency, SUM(awarded) AS known_awarded,
 SUM(received) AS known_received, SUM(deposited) AS known_deposited,
 SUM(reconciled) AS known_reconciled,
 SUM(CASE WHEN awarded IS NULL THEN 1 ELSE 0 END) AS award_unknown_count,
 SUM(CASE WHEN received IS NULL THEN 1 ELSE 0 END) AS receipt_unknown_count,
 SUM(CASE WHEN deposited IS NULL THEN 1 ELSE 0 END) AS deposit_unknown_count,
 SUM(CASE WHEN reconciled IS NULL THEN 1 ELSE 0 END) AS reconciliation_unknown_count,
 SUM(CASE WHEN deposit_evidence_kind='EXECUTIVE_CONFIRMATION' THEN 1 ELSE 0 END) AS executive_confirmed_deposit_count,
 MAX(observed_at) AS observed_at
FROM nexus_intelligence.v_funding_by_opportunity GROUP BY tenant_id, scope_key, currency;
GO

CREATE VIEW nexus_intelligence.v_next_approach AS
SELECT a.tenant_id, a.scope_key, a.action_id, o.opportunity_id,
 org.display_name AS organization, c.display_name AS contact,
 a.action_kind, a.next_action, a.blockers, a.reviewed_priority, a.due_at,
 CASE WHEN ask.evidence_id IS NOT NULL THEN o.proposed_ask END AS proposed_ask,
 o.currency, o.eligibility_state, ae.source_reference AS action_evidence,
 ask.source_reference AS ask_evidence,
 authority.display_name AS budget_controller, authority.source_reference AS authority_evidence,
 CASE WHEN authority.display_name IS NULL THEN 'UNKNOWN' ELSE 'EVIDENCE_SUPPORTED' END AS authority_status
FROM nexus_intelligence.action_item AS a
JOIN nexus_intelligence.funding_opportunity AS o
 ON o.tenant_id=a.tenant_id AND o.scope_key=a.scope_key AND o.opportunity_id=a.opportunity_id
JOIN nexus_intelligence.organization AS org
 ON org.tenant_id=o.tenant_id AND org.scope_key=o.scope_key AND org.organization_id=o.organization_id
JOIN nexus_intelligence.v_approved_evidence AS ae
 ON ae.tenant_id=a.tenant_id AND ae.scope_key=a.scope_key AND ae.evidence_id=a.evidence_id
LEFT JOIN nexus_intelligence.v_approved_evidence AS ask
 ON ask.tenant_id=o.tenant_id AND ask.scope_key=o.scope_key AND ask.evidence_id=o.ask_evidence_id
LEFT JOIN nexus_intelligence.contact AS c
 ON c.tenant_id=a.tenant_id AND c.scope_key=a.scope_key AND c.contact_id=a.contact_id AND c.organization_id=o.organization_id
LEFT JOIN nexus_intelligence.v_approved_evidence AS ce
 ON ce.tenant_id=c.tenant_id AND ce.scope_key=c.scope_key AND ce.evidence_id=c.evidence_id
OUTER APPLY (
 SELECT TOP (1) controller.display_name, be.source_reference
 FROM nexus_intelligence.budget_authority AS b
 JOIN nexus_intelligence.contact AS controller
  ON controller.tenant_id=b.tenant_id AND controller.scope_key=b.scope_key AND controller.contact_id=b.controller_contact_id
 JOIN nexus_intelligence.v_approved_evidence AS be
  ON be.tenant_id=b.tenant_id AND be.scope_key=b.scope_key AND be.evidence_id=b.evidence_id
 WHERE b.tenant_id=o.tenant_id AND b.scope_key=o.scope_key AND b.organization_id=o.organization_id
  AND b.authority_kind='CONTROLS_BUDGET'
 ORDER BY b.observed_at DESC, b.authority_id
) AS authority
WHERE a.action_state='APPROVED' AND o.disposition='OPEN'
 AND (a.contact_id IS NULL OR ce.evidence_id IS NOT NULL)
 AND (o.eligibility_state='ELIGIBLE' OR a.action_kind='DISCOVERY')
 AND (NULLIF(a.blockers,'') IS NULL OR a.action_kind='DISCOVERY');
GO

CREATE VIEW nexus_intelligence.v_retrieval_chunks AS
SELECT c.tenant_id, c.scope_key, c.chunk_id, c.minimized_excerpt, e.source_reference, e.source_url, e.observed_at
FROM nexus_intelligence.evidence_chunk AS c
JOIN nexus_intelligence.v_approved_evidence AS e
 ON e.tenant_id=c.tenant_id AND e.scope_key=c.scope_key AND e.evidence_id=c.evidence_id
JOIN nexus_intelligence.evidence AS raw_e
 ON raw_e.tenant_id=c.tenant_id AND raw_e.scope_key=c.scope_key AND raw_e.evidence_id=c.evidence_id
JOIN nexus_intelligence.source_message AS s
 ON s.tenant_id=raw_e.tenant_id AND s.scope_key=raw_e.scope_key AND s.source_message_id=raw_e.source_message_id
WHERE s.index_allowed=1 AND s.classification='INTERNAL';
GO

CREATE ROLE nexus_intelligence_reader AUTHORIZATION dbo;
GRANT SELECT ON OBJECT::nexus_intelligence.v_funding_by_opportunity TO nexus_intelligence_reader;
GRANT SELECT ON OBJECT::nexus_intelligence.v_funding_totals TO nexus_intelligence_reader;
GRANT SELECT ON OBJECT::nexus_intelligence.v_next_approach TO nexus_intelligence_reader;
GRANT SELECT ON OBJECT::nexus_intelligence.v_approved_evidence TO nexus_intelligence_reader;
GRANT SELECT ON OBJECT::nexus_intelligence.v_retrieval_chunks TO nexus_intelligence_reader;
-- No runtime principal is added. No writer, CREATE/ALTER, or raw table grants.
COMMIT TRANSACTION;

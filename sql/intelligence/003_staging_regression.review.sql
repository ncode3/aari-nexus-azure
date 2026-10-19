-- PREPARED, NOT EXECUTED. Synthetic staging SQL regression after reviewed migration.
-- Never run against production. No real mail, student rows or resource identifiers.
-- sqlcmd -b keeps one connection across GO batches; everything below rolls back.
:ON ERROR EXIT
SET XACT_ABORT ON;
BEGIN TRANSACTION;
DECLARE @tenant uniqueidentifier='00000000-0000-0000-0000-000000000111';
DECLARE @org uniqueidentifier='00000000-0000-0000-0000-000000000112';
DECLARE @opportunity uniqueidentifier='00000000-0000-0000-0000-000000000113';
DECLARE @award uniqueidentifier='00000000-0000-0000-0000-000000000114';
DECLARE @receipt uniqueidentifier='00000000-0000-0000-0000-000000000115';
DECLARE @now datetime2(3)=SYSUTCDATETIME();
-- Bootstrap only the test administrator and synthetic reader to synthetic scope.
INSERT nexus_intelligence.data_scope VALUES (@tenant,N'synthetic-fundraising',30);
INSERT nexus_intelligence.principal_scope_access VALUES (USER_NAME(),@tenant,N'synthetic-fundraising');
CREATE USER nexus_intelligence_synthetic_reader WITHOUT LOGIN;
ALTER ROLE nexus_intelligence_reader ADD MEMBER nexus_intelligence_synthetic_reader;
INSERT nexus_intelligence.principal_scope_access VALUES (N'nexus_intelligence_synthetic_reader',@tenant,N'synthetic-fundraising');
INSERT nexus_intelligence.organization VALUES (@tenant,N'synthetic-fundraising',@org,N'Synthetic QTS analogue');
INSERT nexus_intelligence.evidence
 (tenant_id,scope_key,evidence_id,evidence_kind,source_reference,observed_at,expires_at,review_state,reviewer_key,reviewed_at)
VALUES (@tenant,N'synthetic-fundraising',@award,'CURATED_SEED',N'Synthetic award evidence',@now,DATEADD(day,30,@now),'APPROVED',N'synthetic-reviewer',@now),
       (@tenant,N'synthetic-fundraising',@receipt,'ATTESTATION',N'Synthetic check receipt attestation',@now,DATEADD(day,30,@now),'APPROVED',N'synthetic-reviewer',@now);
INSERT nexus_intelligence.funding_opportunity
 (tenant_id,scope_key,opportunity_id,organization_id,stable_source_key,purpose,currency)
VALUES (@tenant,N'synthetic-fundraising',@opportunity,@org,N'synthetic-qts',N'Synthetic test only','USD');
-- First business assertion: approach, ask, contact vs budget authority, evidence.
DECLARE @truist uniqueidentifier=NEWID(), @truist_opportunity uniqueidentifier=NEWID(), @contact uniqueidentifier=NEWID();
INSERT nexus_intelligence.organization VALUES (@tenant,N'synthetic-fundraising',@truist,N'Synthetic Truist analogue');
INSERT nexus_intelligence.contact VALUES (@tenant,N'synthetic-fundraising',@contact,@truist,N'Synthetic contact',@award);
INSERT nexus_intelligence.funding_opportunity
 (tenant_id,scope_key,opportunity_id,organization_id,stable_source_key,purpose,currency,proposed_ask,ask_evidence_id)
VALUES (@tenant,N'synthetic-fundraising',@truist_opportunity,@truist,N'synthetic-truist',N'Synthetic equipment request','USD',100000,@award);
INSERT nexus_intelligence.action_item
 (tenant_id,scope_key,action_id,opportunity_id,contact_id,action_kind,next_action,blockers,reviewed_priority,evidence_id,action_state)
VALUES (@tenant,N'synthetic-fundraising',NEWID(),@truist_opportunity,@contact,'DISCOVERY',
 N'Explore request and identify the actual budget controller',N'Eligibility and board list unresolved',1,@award,'APPROVED');
IF NOT EXISTS (SELECT 1 FROM nexus_intelligence.v_next_approach
 WHERE tenant_id=@tenant AND organization=N'Synthetic Truist analogue' AND contact=N'Synthetic contact'
 AND proposed_ask=100000 AND currency='USD' AND action_kind='DISCOVERY'
 AND budget_controller IS NULL AND authority_status='UNKNOWN' AND action_evidence IS NOT NULL AND ask_evidence IS NOT NULL)
 THROW 51099,'First business acceptance: approach/ask/authority/evidence failed.',1;
INSERT nexus_intelligence.status_event
 (tenant_id,scope_key,event_id,opportunity_id,financial_state,snapshot_revision,cumulative_amount,evidence_id,observed_at,review_state)
VALUES (@tenant,N'synthetic-fundraising',NEWID(),@opportunity,'AWARDED',1,10000,@award,@now,'APPROVED'),
       (@tenant,N'synthetic-fundraising',NEWID(),@opportunity,'AWARDED',2,15000,@award,@now,'APPROVED'),
       (@tenant,N'synthetic-fundraising',NEWID(),@opportunity,'RECEIVED',1,15000,@receipt,@now,'APPROVED'),
       (@tenant,N'synthetic-fundraising',NEWID(),@opportunity,'DEPOSITED',1,15000,@receipt,@now,'APPROVED');
IF NOT EXISTS (SELECT 1 FROM nexus_intelligence.v_funding_totals
 WHERE tenant_id=@tenant AND scope_key=N'synthetic-fundraising'
 AND known_awarded=15000 AND known_received=15000 AND known_deposited IS NULL AND deposit_unknown_count=2)
 THROW 51100,'Snapshot arithmetic or unverified deposit handling failed.',1;
-- Executive deposit confirmation is valid deposit evidence, not bank reconciliation.
DECLARE @deposit uniqueidentifier=NEWID();
INSERT nexus_intelligence.evidence
 (tenant_id,scope_key,evidence_id,evidence_kind,source_reference,observed_at,expires_at,review_state,reviewer_key,reviewed_at)
VALUES (@tenant,N'synthetic-fundraising',@deposit,'EXECUTIVE_CONFIRMATION',N'Synthetic executive deposit confirmation',@now,DATEADD(day,30,@now),'APPROVED',N'synthetic-reviewer',@now);
INSERT nexus_intelligence.status_event
 (tenant_id,scope_key,event_id,opportunity_id,financial_state,snapshot_revision,cumulative_amount,evidence_id,observed_at,review_state)
VALUES (@tenant,N'synthetic-fundraising',NEWID(),@opportunity,'DEPOSITED',2,15000,@deposit,@now,'APPROVED'),
       (@tenant,N'synthetic-fundraising',NEWID(),@opportunity,'RECONCILED',1,15000,@deposit,@now,'APPROVED');
IF NOT EXISTS (SELECT 1 FROM nexus_intelligence.v_funding_totals
 WHERE tenant_id=@tenant AND scope_key=N'synthetic-fundraising' AND known_deposited=15000
 AND known_reconciled IS NULL AND executive_confirmed_deposit_count=1 AND reconciliation_unknown_count=2)
 THROW 51104,'Executive deposit confirmation was lost or misclassified as bank reconciliation.',1;
-- Review retraction must not resurrect the earlier $10,000 snapshot.
INSERT nexus_intelligence.status_event
 (tenant_id,scope_key,event_id,opportunity_id,financial_state,snapshot_revision,cumulative_amount,evidence_id,observed_at,record_state,review_state)
VALUES (@tenant,N'synthetic-fundraising',NEWID(),@opportunity,'AWARDED',3,15000,@award,@now,'RETRACTED','APPROVED');
IF EXISTS (SELECT 1 FROM nexus_intelligence.v_funding_totals
 WHERE tenant_id=@tenant AND scope_key=N'synthetic-fundraising' AND known_awarded IS NOT NULL)
 THROW 51101,'Retraction restored an older snapshot.',1;
-- Hidden scope and different tenant must not be visible through the reader views.
INSERT nexus_intelligence.data_scope VALUES (@tenant,N'synthetic-private',30);
INSERT nexus_intelligence.principal_scope_access VALUES (USER_NAME(),@tenant,N'synthetic-private');
INSERT nexus_intelligence.organization VALUES (@tenant,N'synthetic-private',NEWID(),N'Hidden organization');
DECLARE @hidden_org uniqueidentifier=(SELECT organization_id FROM nexus_intelligence.organization
 WHERE tenant_id=@tenant AND scope_key=N'synthetic-private');
INSERT nexus_intelligence.funding_opportunity
 (tenant_id,scope_key,opportunity_id,organization_id,stable_source_key,purpose,currency)
VALUES (@tenant,N'synthetic-private',NEWID(),@hidden_org,N'private-opportunity',N'Hidden source scope','USD');
DECLARE @other uniqueidentifier='00000000-0000-0000-0000-000000000999';
INSERT nexus_intelligence.data_scope VALUES (@other,N'synthetic-fundraising',30);
INSERT nexus_intelligence.principal_scope_access VALUES (USER_NAME(),@other,N'synthetic-fundraising');
INSERT nexus_intelligence.organization VALUES (@other,N'synthetic-fundraising',@org,N'Other tenant organization');
INSERT nexus_intelligence.funding_opportunity
 (tenant_id,scope_key,opportunity_id,organization_id,stable_source_key,purpose,currency)
VALUES (@other,N'synthetic-fundraising',@opportunity,@org,N'synthetic-qts',N'Hidden other tenant','USD');
GO
EXECUTE AS USER = 'nexus_intelligence_synthetic_reader';
IF (SELECT COUNT(*) FROM nexus_intelligence.v_funding_by_opportunity) <> 2
 THROW 51102,'Reader cross-tenant/source isolation failed.',1;
IF HAS_PERMS_BY_NAME('nexus_intelligence.source_message','OBJECT','SELECT')=1
 THROW 51103,'Reader has raw source table permission.',1;
REVERT;
GO
ROLLBACK TRANSACTION;
PRINT 'Synthetic snapshot/retraction/deposit/reader-isolation regression passed; changes rolled back.';

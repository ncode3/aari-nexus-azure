-- SEPARATE PERMISSION PROPOSAL. Never run until identity/data grants are approved.
-- SQL contained Entra user must already exist with independently approved CONNECT.
-- ARM Reader/Contributor and an identity attachment do not grant SQL data access.
:ON ERROR EXIT
SET XACT_ABORT ON;
DECLARE @approved bit = 0; -- administrator changes ONLY following documented review
DECLARE @principal sysname = N'REPLACE_WITH_EXISTING_REVIEWED_SQL_PRINCIPAL';
DECLARE @tenant uniqueidentifier = NULL;
DECLARE @scope nvarchar(64) = N'REPLACE_WITH_APPROVED_SCOPE';
IF @approved <> 1 OR @tenant IS NULL OR @principal LIKE N'REPLACE_%' OR @scope LIKE N'REPLACE_%'
    THROW 51001, 'Permission proposal is not reviewed and bound.', 1;
IF DATABASE_PRINCIPAL_ID(@principal) IS NULL
    THROW 51002, 'Existing reviewed contained SQL principal not found.', 1;
IF NOT EXISTS (SELECT 1 FROM nexus_intelligence.data_scope WHERE tenant_id=@tenant AND scope_key=@scope)
    THROW 51003, 'Reviewed source scope is absent or not visible to this administrator.', 1;
BEGIN TRANSACTION;
IF NOT EXISTS (SELECT 1 FROM nexus_intelligence.principal_scope_access
               WHERE principal_name=@principal AND tenant_id=@tenant AND scope_key=@scope)
    INSERT nexus_intelligence.principal_scope_access VALUES (@principal,@tenant,@scope);
DECLARE @sql nvarchar(max)=N'ALTER ROLE nexus_intelligence_reader ADD MEMBER '+QUOTENAME(@principal)+N';';
EXEC sys.sp_executesql @sql;
COMMIT TRANSACTION;
-- Read role is limited to five views; it does not authorize each human caller.
-- Inspect existing role memberships before approval; no db_owner/datareader grants.

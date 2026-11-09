"""Read-only all-region actual costs, inventory, dependencies and budget evidence.

Raw evidence stays under gitignored data/. No stop/delete/PUT or token command exists.
"""
import argparse
import json
import re
import subprocess
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path


class AzureReadError(RuntimeError):
    pass


class AzureReader:
    def __init__(self, wsl=False):
        self.prefix = ['wsl.exe', '-d', 'Ubuntu', '--exec', 'az'] if wsl else ['az']
        self.wsl = wsl

    def call(self, *args):
        result = subprocess.run([*self.prefix, *args, '--output', 'json', '--only-show-errors'],
                                capture_output=True, encoding='utf-8', timeout=180)
        if result.returncode:
            # Never echo complete CLI stderr, signed URLs, credentials or account details.
            code = re.search(r'\b(?:AADSTS\d+|AuthorizationFailed|AuthenticationFailed|InvalidAuthenticationToken|ExpiredAuthenticationToken|TooManyRequests|SubscriptionNotFound)\b', result.stderr)
            raise AzureReadError(code.group() if code else 'Azure command failed; secure sign-in/access or network verification required')
        return json.loads(result.stdout)

    def rest(self, url, body=None, body_file=None):
        args = ['rest', '--method', 'post' if body is not None else 'get', '--url', url]
        if body is not None:
            body_file.write_text(json.dumps(body), encoding='utf-8')
            file = body_file.resolve().as_posix()
            if self.wsl:
                file = subprocess.check_output(['wsl.exe', '-d', 'Ubuntu', '--exec', 'wslpath', '-a', file], encoding='utf-8').strip()
            args.extend(['--body', '@' + file])
        return self.call(*args)


def cost_query(reader, scope, start, end, directory):
    body = {'type': 'ActualCost', 'timeframe': 'Custom',
            'timePeriod': {'from': start.isoformat(), 'to': end.isoformat()},
            'dataset': {'granularity': 'None', 'aggregation': {'totalCost': {'name': 'PreTaxCost', 'function': 'Sum'}},
                        'grouping': [{'type': 'Dimension', 'name': 'ResourceId'},
                                     {'type': 'Dimension', 'name': 'ResourceLocation'}]}}
    url = f'https://management.azure.com{scope}/providers/Microsoft.CostManagement/query?api-version=2025-03-01'
    rows, seen = [], set()
    while url:
        if url in seen or not url.startswith('https://management.azure.com/'):
            raise AzureReadError('Untrusted or repeated cost pagination link')
        seen.add(url)
        result = reader.rest(url, body, directory / 'query.json')['properties']
        columns = [column['name'] for column in result['columns']]
        rows.extend(dict(zip(columns, row)) for row in result['rows'])
        url = result.get('nextLink')
    return rows


def owns_nexus(resource):
    tags = {str(k).lower(): str(v).lower() for k, v in (resource.get('tags') or {}).items()}
    return ('nexus' in resource.get('name', '').lower() or
            any('nexus' in tags.get(k, '') for k in ('project', 'workload', 'application')))


def audit(reader, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC)
    current = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous = (current - timedelta(days=1)).replace(day=1)
    report = {'observed_at': now.isoformat(), 'all_regions': True, 'budget_ceiling_usd': 50,
              'resources_changed': False, 'subscriptions': [], 'errors': []}
    accounts = reader.call('account', 'list')
    for account in accounts:
        if account.get('state') != 'Enabled':
            continue
        subscription = account['id']
        scope = '/subscriptions/' + subscription
        entry = {'subscription_id': subscription, 'name': account['name'], 'resources': [], 'costs': {}, 'budgets': []}
        report['subscriptions'].append(entry)
        try:
            resources = reader.call('resource', 'list', '--subscription', subscription)
            for resource in resources:
                record = {k: resource.get(k) for k in ('id', 'name', 'type', 'location', 'resourceGroup', 'tags')}
                record['nexus_attribution'] = 'name-or-explicit-tag' if owns_nexus(resource) else 'unverified-or-other-workload'
                record['recommendation'] = 'keep-until-cutover-and-recovery-verified' if owns_nexus(resource) else 'keep-not-proven-unnecessary'
                if owns_nexus(resource):
                    try:
                        details = reader.call('resource', 'show', '--ids', resource['id'])
                    except AzureReadError as exc:
                        record['dependency_error'] = str(exc)
                        details = {}
                    properties = details.get('properties') or {}
                    template = properties.get('template') or {}
                    configuration = properties.get('configuration') or {}
                    record['dependencies'] = {'environment': properties.get('environmentId') or properties.get('managedEnvironmentId'),
                        'identities': list((details.get('identity') or {}).get('userAssignedIdentities') or {}),
                        'registries': [r.get('server') for r in configuration.get('registries') or []],
                        'secret_references': [s.get('keyVaultUrl', '').split('?')[0] for s in configuration.get('secrets') or [] if s.get('keyVaultUrl')],
                        'volumes': template.get('volumes') or [],
                        'containers': [{'name': c.get('name'), 'image': c.get('image'),
                            'environment_variable_names': [e.get('name') for e in c.get('env') or []],
                            'volume_mounts': c.get('volumeMounts') or []} for c in template.get('containers') or []]}
                    record['runtime'] = {k: properties.get(k) for k in ('runningStatus', 'latestReadyRevisionName', 'provisioningState')}
                    record['scale'] = template.get('scale')
                entry['resources'].append(record)
            (destination / 'audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            scopes = [scope] + [scope + '/resourceGroups/' + group for group in
                sorted({r['resourceGroup'] for r in resources if owns_nexus(r)})]
            for budget_scope in scopes:
                try:
                    budgets = reader.rest(f'https://management.azure.com{budget_scope}/providers/Microsoft.Consumption/budgets?api-version=2024-08-01')
                    for budget in budgets.get('value', []):
                        entry['budgets'].append({'scope': budget_scope, 'name': budget['name'], 'properties': budget['properties']})
                except AzureReadError as exc:
                    report['errors'].append({'phase': 'budgets', 'scope': budget_scope, 'error': str(exc)})
            for label, start, end in [('previous_month', previous, current - timedelta(microseconds=1)), ('month_to_date', current, now)]:
                try:
                    entry['costs'][label] = cost_query(reader, scope, start, end, destination)
                except AzureReadError as exc:
                    report['errors'].append({'phase': 'costs-' + label, 'scope': scope, 'error': str(exc)})
        except (AzureReadError, subprocess.TimeoutExpired) as exc:
            report['errors'].append({'phase': 'subscription', 'subscription': subscription, 'error': type(exc).__name__ + ': ' + str(exc)[:180]})
    (destination / 'audit.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    decisions = []
    gates = {
        'Microsoft.App/containerApps': 'Retire only after verified production backup/restore, test-bot acceptance, and stopped-cloud-poller cutover. Keep active now.',
        'Microsoft.ContainerRegistry/registries': 'Keep pinned rollback image; retire only after rollback retention and consumer inventory.',
        'Microsoft.Storage/storageAccounts': 'Keep documents and rollback data; retire only after content/count-verified migration and retention approval.',
        'Microsoft.KeyVault/vaults': 'Keep rollback secrets and approved integrations; verify every consumer before retirement.',
        'Microsoft.ManagedIdentity/userAssignedIdentities': 'Keep identity and SharePoint selected permissions until every consumer is inventoried.',
        'Microsoft.App/managedEnvironments': 'Keep while any app/revision uses it; do not delete an environment containing other apps.',
        'Microsoft.CognitiveServices/accounts': 'Keep pending deployment/consumer verification; routine local inference does not use it.',
        'Microsoft.EventGrid/systemTopics': 'Keep until event subscriptions and storage integration dependencies are verified.',
        'Microsoft.Sql/servers/databases': 'Keep; business-system ownership and recovery are not established by the bot migration.',
    }
    for entry in report['subscriptions']:
        for resource in entry['resources']:
            if resource['nexus_attribution'] != 'name-or-explicit-tag':
                continue
            costs = {}
            for period, rows in entry['costs'].items():
                matches = [row for row in rows if str(row.get('ResourceId', '')).lower() == resource['id'].lower()]
                costs[period] = [{'amount': str(row.get('PreTaxCost', row.get('Cost'))), 'currency': row.get('Currency'),
                                  'region': row.get('ResourceLocation')} for row in matches]
            decisions.append({'resource_id': resource['id'], 'name': resource['name'], 'type': resource['type'],
                'region': resource['location'], 'verified_cost_rows': costs,
                'no_row_means': 'No reported charge row, not proof of free or unused service',
                'decision': 'keep', 'retirement_gate': gates.get(resource['type'], 'Keep audit/telemetry until retention and downstream dependencies are verified.')})
    (destination / 'keep-retire.json').write_text(json.dumps(decisions, indent=2), encoding='utf-8')
    summaries = []
    for entry in report['subscriptions']:
        owned = {r['id'].lower() for r in entry['resources'] if r['nexus_attribution'] == 'name-or-explicit-tag'}
        for period, rows in entry['costs'].items():
            by_currency = {}
            for row in rows:
                currency = row.get('Currency', 'unknown')
                values = by_currency.setdefault(currency, {'all_resources': Decimal(0), 'nexus_attributed': Decimal(0)})
                cost = Decimal(str(row.get('PreTaxCost', row.get('Cost', 0))))
                values['all_resources'] += cost
                if str(row.get('ResourceId', '')).lower() in owned:
                    values['nexus_attributed'] += cost
            summaries.append({'period': period, 'currency_totals': {currency: {k: str(v) for k, v in values.items()} for currency, values in by_currency.items()},
                              'regions': sorted({str(r.get('ResourceLocation')) for r in rows}), 'cost_rows': len(rows)})
    return {'subscriptions': len(report['subscriptions']), 'summary': summaries, 'errors': report['errors'], 'resources_changed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wsl', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('data/azure-audit'))
    args = parser.parse_args()
    try:
        print(json.dumps(audit(AzureReader(args.wsl), args.out), indent=2))
    except (AzureReadError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({'verified': False, 'error': type(exc).__name__ + ': ' + str(exc)[:180]}))
        raise SystemExit(1)

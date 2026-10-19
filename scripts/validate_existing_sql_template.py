"""Validate compiled Bicep reuse/binding; not live Azure connectivity or policy proof."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1]


def validate(template: dict) -> None:
    inventory=json.loads((ROOT/'infra/intelligence/confirmed-deployment.json').read_text())
    if template.get('resources'):
        raise ValueError('Existing SQL template must not provision any resource')
    bindings={'sqlResourceGroupName':'resource_group', 'sqlServerName':'server', 'sqlDatabaseName':'database'}
    for param, key in bindings.items():
        value=template['parameters'][param]
        if value.get('defaultValue') != inventory[key] or value.get('allowedValues') != [inventory[key]]:
            raise ValueError('Compiled template can target an unconfirmed SQL resource: '+param)
    required={'observedSqlLocation','observedPublicNetworkAccess','observedEntraOnly',
              'observedUseFreeLimit','observedFreeLimitExhaustionBehavior'}
    if not required.issubset(template.get('outputs',{})):
        raise ValueError('Policy observation outputs missing')


if __name__=='__main__':
    validate(json.loads(Path(sys.argv[1]).read_text(encoding='utf-8')))
    print('Compiled existing-resource bindings match user-confirmed inventory; zero resource declarations. Live policy/connectivity/cost review remains pending.')

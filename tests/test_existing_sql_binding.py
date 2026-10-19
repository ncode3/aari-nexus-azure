import json
import unittest
from pathlib import Path
from scripts.validate_existing_sql_template import validate

ROOT=Path(__file__).resolve().parents[1]


class ExistingSqlBindingTests(unittest.TestCase):
    def template(self):
        data=json.loads((ROOT/'infra/intelligence/confirmed-deployment.json').read_text())
        return {'resources':[], 'parameters':{
            param:{'defaultValue':data[key],'allowedValues':[data[key]]}
            for param,key in [('sqlResourceGroupName','resource_group'),('sqlServerName','server'),('sqlDatabaseName','database')]},
            'outputs':{name:{} for name in ['observedSqlLocation','observedPublicNetworkAccess','observedEntraOnly','observedUseFreeLimit','observedFreeLimitExhaustionBehavior']}}

    def test_binding_checks_never_allow_resource_creation_or_another_database(self):
        validate(self.template())
        for changed in ['resources','database']:
            t=self.template()
            if changed=='resources':
                t['resources']=[{'type':'Microsoft.Sql/servers'}]
            else:
                t['parameters']['sqlDatabaseName']['defaultValue']='duplicate-db'
            with self.assertRaises(ValueError):
                validate(t)

    def test_eus_suffix_does_not_override_reported_west_us(self):
        data=json.loads((ROOT/'infra/intelligence/confirmed-deployment.json').read_text())
        self.assertEqual(data['region'],'westus')
        self.assertTrue(data['entra_only_authentication'])
        self.assertEqual(data['sql_public_network_access'],'Disabled')
        self.assertEqual(data['free_limit_exhaustion_behavior'],'AutoPause')
        self.assertEqual(data['monthly_intelligence_budget_ceiling_usd'],50)
        self.assertFalse(data['application_connectivity_verified'])

    def test_missing_observation_outputs_are_rejected(self):
        t=self.template()
        del t['outputs']['observedEntraOnly']
        with self.assertRaises(ValueError):
            validate(t)

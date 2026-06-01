# -*- coding: utf-8 -*-
import json
import time
import uuid


class AaManager:
    def __init__(self, context): self.context = context
    def toJson(self, response):
        if response['status'] >= 400: raise Exception(response['content'].decode('utf-8'))
        try: return json.loads(response['content'].decode('utf-8'))
        except: return response['content'].decode('utf-8')
    def encode(self, url): return url.replace(' ', '%20').replace('$', '%24').replace("'", '%27').replace('[', '%5B').replace(']', '%5D')
    def get(self, url): return self.toJson(self.context.request(operation='GET', link=self.encode(url), body=''))
    def post(self, url, data): return self.toJson(self.context.request(operation='POST', link=self.encode(url), body=data))
    def delete(self, url, data=''): return self.toJson(self.context.request(operation='DELETE', link=self.encode(url), body=data))

    def runOrchWorkflow(self, workflowName, inputs={}):
        result = self.get("/vro/workflows?$filter=name eq '" + workflowName + "'")
        if not isinstance(result, dict):
            raise Exception('vRO workflows API returned unexpected response')
        content = result.get('content', [])
        if not content:
            raise Exception('vRO Workflow not found: ' + workflowName)
        wfId = content[0]['id']
        params = []
        for k, v in inputs.items():
            if isinstance(v, bool):
                params.append({'name': k, 'type': 'boolean', 'value': {'boolean': {'value': v}}})
            elif v is None:
                params.append({'name': k, 'type': 'string', 'value': {'string': {'value': ''}}})
            else:
                params.append({'name': k, 'type': 'string', 'value': {'string': {'value': str(v)}}})
        runId = str(uuid.uuid4())
        self.post('/vro/runs', {'workflowId': wfId, 'executionId': runId, 'parameters': params})
        for _ in range(300):
            state = self.get('/vro/runs/' + runId)
            runState = state.get('runStatus', '') if isinstance(state, dict) else ''
            if runState == 'COMPLETED':
                outputs = {}
                for k, v in (state.get('workflowOutputs') or {}).items():
                    val = v.get('value') or {}
                    if 'string' in val: outputs[k] = val['string']['value']
                    elif 'boolean' in val: outputs[k] = val['boolean']['value']
                    elif 'number' in val: outputs[k] = val['number']['value']
                    else: outputs[k] = val
                return outputs
            if runState in ['FAILED', 'CANCELED']:
                raise Exception("Workflow '" + workflowName + "' " + runState + ': ' + (state.get('errorMessage') or ''))
            time.sleep(2)
        raise Exception("Workflow '" + workflowName + "' timed out")


def handler(context, inputs):
    aa = AaManager(context)

    nsx = aa.runOrchWorkflow('Custom.VPC.nsxTier1Manager', {
        'cloudZoneId': inputs['cloudZoneId'],
        'importMode': inputs['importMode'],
        'organizationCode': inputs['organizationCode'],
        'tier0Path': inputs.get('tier0Path', ''),
        'edgeClusterPath': inputs.get('edgeClusterPath', ''),
        'existingTier1Path': inputs.get('existingTier1Path', '')
    })
    tier1Id = nsx['tier1Id']
    tier1Path = nsx['tier1Path']
    tier1Name = nsx['tier1Name']
    nsxHostname = nsx['nsxHostname']

    zone = aa.get('/iaas/api/zones/' + inputs['cloudZoneId'])
    cloudAccountId = zone['cloudAccountId']
    regionId = zone.get('regionId', '')

    cloudAccount = aa.get('/iaas/api/cloud-accounts/' + cloudAccountId)
    nsxAccountId = cloudAccount['linkedCloudAccountIds'][0]

    orgCode = inputs['organizationCode']
    profileName = 'netprofile-' + orgCode
    profilesRes = aa.get('/iaas/api/network-profiles?$filter=name eq \'' + profileName + '\'')
    profiles = profilesRes.get('content', []) if isinstance(profilesRes, dict) else []

    if profiles:
        networkProfileId = profiles[0]['id']
    else:
        newProfile = aa.post('/iaas/api/network-profiles', {
            'name': profileName,
            'regionId': regionId,
            'isolationType': 'PRIVATE_PEERED'
        })
        networkProfileId = newProfile['id']

    vpcProfile = '/provisioning/uerp/resources/network-profiles/' + networkProfileId

    outputs = dict(inputs)
    outputs['id'] = tier1Id
    outputs['name'] = tier1Name
    outputs['tier1Path'] = tier1Path
    outputs['networkProfileId'] = networkProfileId
    outputs['vpcProfile'] = vpcProfile
    outputs['nsxAccountId'] = nsxAccountId
    outputs['nsxHostname'] = nsxHostname
    return outputs

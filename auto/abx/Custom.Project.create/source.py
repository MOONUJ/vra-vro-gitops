# -*- coding: utf-8 -*-
'''
@copyright: Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import Libraries Here
#===============================================================================
import json
import time


#===============================================================================
# AaManager SDK
#===============================================================================
class AaManager:
    def __init__(self, context): self.context = context
    def toJson(self, response):
        if response['status'] >= 400: raise Exception(response['content'].decode('utf-8'))
        try: return json.loads(response['content'].decode('utf-8'))
        except: return response['content'].decode('utf-8')
    def encode(self, url): return url.replace(' ', '%20').replace('$', '%24').replace("'", '%27').replace('[', '%5B').replace(']', '%5D')
    def get(self, url): return self.toJson(self.context.request(operation='GET', link=self.encode(url), body=''))
    def post(self, url, data): return self.toJson(self.context.request(operation='POST', link=self.encode(url), body=data))
    def put(self, url, data): return self.toJson(self.context.request(operation='PUT', link=self.encode(url), body=data))
    def patch(self, url, data): return self.toJson(self.context.request(operation='PATCH', link=self.encode(url), body=data))
    def delete(self, url, data=''): return self.toJson(self.context.request(operation='DELETE', link=self.encode(url), body=data))
    def getUerp(self, url): return self.get(f'/provisioning/uerp{url}')
    def postUerp(self, url, data): return self.post(f'/provisioning/uerp{url}', data)
    def putUerp(self, url, data): return self.put(f'/provisioning/uerp{url}', data)
    def patchUerp(self, url, data): return self.patch(f'/provisioning/uerp{url}', data)
    def deleteUerp(self, url, data=''): return self.delete(f'/provisioning/uerp{url}', data)
    def runOrchAction(self, projectId, uri, data={}):
        result = self.post(f'/form-service/api/forms/renderer/external-value?projectId={projectId}', {'uri':uri, 'dataSource':'scriptAction', 'parameters':[{'name':k, 'value':v} for k, v in data.items()]})
        if 'data' in result: return result['data']
        elif 'error' in result: raise Exception(result['error']['summaryMessage'])
        else: raise Exception('unknown error')


#===============================================================================
# Implement Handler Here
#===============================================================================
def handler(context, inputs):
    aa = AaManager(context)

    if 'administrators' not in inputs: inputs['administrators'] = []
    if 'members' not in inputs: inputs['members'] = []
    if 'viewers' not in inputs: inputs['viewers'] = []
    if 'supervisors' not in inputs: inputs['supervisors'] = []
    if 'sharedResources' not in inputs: inputs['sharedResources'] = False
    if 'cloudZones' not in inputs: inputs['cloudZones'] = []
    if 'placementPolicy' not in inputs: inputs['placementPolicy'] = 'default'
    if 'catalogs' not in inputs: inputs['catalogs'] = []
    if 'organization' not in inputs: inputs['organization'] = []
    
    project = aa.post('/iaas/api/projects', {
        'name': inputs['name'],
        'description': inputs['displayName'],
        'sharedResources': inputs['sharedResources'],
        'zoneAssignmentConfigurations': [{'zoneId': cloudZone} for cloudZone in inputs['cloudZones']],
        'placementPolicy': inputs['placementPolicy'].upper(),
        'customProperties': {
            'profile': inputs['profile'],
            'organization': inputs['organization']
        }   
    })
    projectId = project['id']
    
    # Cloud Zone들을 돌며 Region Href 수집
    regionHrefs = []
    for cloudZone in inputs['cloudZones']:
        zone_info = aa.get(f"/iaas/api/zones/" + cloudZone)
        region_href = zone_info.get('_links', {}).get('region', {}).get('href')
        
        if region_href and (region_href not in regionHrefs):
            regionHrefs.append(region_href)
    
    # 1. Organization 이름으로 기존 Network Profiles 조회
    network_profile_response = aa.get(f"/iaas/api/network-profiles?$filter=name eq '{inputs['organization']}'")
    profiles = network_profile_response.get('content', [])
    
    # 2. 기존 프로필 중 현재 프로젝트의 Region과 매칭되는 게 있는지 확인
    matched_network_profiles = []
    for profile in profiles:
        profile_region_href = profile.get('_links', {}).get('region', {}).get('href')
        if profile_region_href in regionHrefs:
            matched_network_profiles.append(profile)
            
    # 3. 매칭되는 네트워크 프로필이 없다면 신규 생성
    if not matched_network_profiles:
        for region_href in regionHrefs:
            # URL에서 마지막 ID나 이름을 따와 명명하거나 organization 명을 기반으로 생성
            # vRA 스펙에 따라 regionId 파라미터가 필수이므로 href에서 ID를 추출합니다.
            region_id = region_href.split('/')[-1]
            
            new_profile = aa.post('/iaas/api/network-profiles', {
                'name': inputs['organization'], # 혹은 원하는 네이밍 규칙 적용
                'description': f"Auto-created network profile for {inputs['organization']}",
                'regionId': region_id,
                # 필요 시 추가적인 네트워크 속성(isolationType, fabricNetworkIds 등)을 여기 정의합니다.
            })
            matched_network_profiles.append(new_profile)
            
    # 최종 할당되거나 생성된 프로필들의 ID 목록 추출 (필요 시 활용)
    inputs['networkProfileIds'] = [p.get('id') for p in matched_network_profiles]
    

    inputs['id'] = projectId
    inputs['selfId'] = projectId
    outputs = inputs
    return outputs

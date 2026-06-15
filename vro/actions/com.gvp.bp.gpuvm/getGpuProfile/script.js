if(!gpuSize || !gpuModel || !category || !projectId || !regionLink){return null;};
var aa = System.getModule("com.gvp").AaManager(true);

var tags = aa.get("/iaas/api/tags?$filter= key eq '"+category+"'").content
var project = aa.get("/iaas/api/projects/" + projectId);
var projectProfile = project.customProperties.profile;

//var profileDetails = aa.getUerp(profileLink);
//var targetRegionLink = profileDetails.provisioningRegionLink;
var targetRegionLink = regionLink;

var projectZoneId = null;
for each (var zone in project.zones) {
    //var placementZoneLink = "/provisioning/resources/placement-zones/" + zone.zoneId;
    //var placementZone = aa.getUerp(placementZoneLink);
    var placementZoneLink = "/iaas/api/zones/" + zone.zoneId;
    var placementZone = aa.get(placementZoneLink)
    if (placementZone._links.region.href === targetRegionLink) {
        projectZoneId = zone.zoneId;
        break;
    }
}

if (!projectZoneId) {
    System.log("No matching zone found for target region");
    return null;
}

var zoneComputes = aa.get("/iaas/api/zones/" + projectZoneId + "/computes").content;

var computeNames = [];
for each(var zoneCompute in zoneComputes){
    var profileTag = zoneCompute.tags.filter(function(item){return item.key == "profile"});
    var gpuTag = zoneCompute.tags.filter(function(item){return item.key == category && item.value == gpuModel});
    
    if(profileTag.length > 0 && profileTag.filter(function(item){return item.value == projectProfile}).length != 0 && gpuTag.length > 0){
        computeNames.push(zoneCompute.name);
    }
}

var result = [];
for each(var computeName in computeNames){
    var cluster = VcPlugin.getAllClusterComputeResources(null, "xpath:name='" + computeName + "'")[0];
    
    // cluster 존재 검증
    if (!cluster || !cluster.host) {
        System.log("Cluster or hosts not found for: " + computeName);
        continue;
    }
    
    var hosts = cluster.host;
    for (var h in hosts){
        var configManager = hosts[h].configManager;
        if (!configManager || !configManager.graphicsManager) {
            System.log("Graphics manager not available for host: " + hosts[h].name);
            continue;
        }
        
        var gpuManager = configManager.graphicsManager;
        var vgpuProfileInfo = null;
        try {
            vgpuProfileInfo = hosts[h].config.sharedGpuCapabilities.filter( function(item){ return item.vgpu.split("-").length == 2;});//gpuManager.retrieveVgpuProfileInfo();
            if (!vgpuProfileInfo) {
                System.log("No vGPU profile info available for host: " + hosts[h].name);
                continue;
            }
        } catch (gpuError) {
            System.log("Failed to retrieve GPU profile info for host " + hosts[h].name + ": " + gpuError);
            continue;
        }
        
        // 지정된 GPU 크기에 맞는 프로필 필터링
        var vgpuProfile = vgpuProfileInfo.filter(function(item){
            var match = item.vgpu.match(/-(\d+)/); 
            var endsWithQorC = /[qc]$/i.test(item.vgpu);
            return match && match[1] == gpuSize && endsWithQorC;
            //return item.fbSizeInGib.toString() == gpuSize;
        });
        

        
        // 매칭되는 프로필이 없으면 다음 호스트로
        if (vgpuProfile.length === 0) {
            continue;
        }
        
        // 수정: vgpuProfile 배열 사용
        for(var g in vgpuProfile){
            var profileName = vgpuProfile[g].vgpu;
            //var profileName = vgpuProfile[g].profileName;
            if(result.indexOf(profileName) === -1 ){
                result.push(profileName);
            }
        }
    }
}

// 정렬
result.sort(function(a, b) {
    return a.toUpperCase() < b.toUpperCase() ? -1 : 1;
});

// 수정: 안전한 반환
return result.length > 0 ? result[0] : null;
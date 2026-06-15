if(!gpuModel || !category || !projectId || !regionLink || !resourceId){return null;};
var aa = System.getModule("com.gvp").AaManager(true);

var machine = aa.get("/iaas/api/machines/" + resourceId);
var currentGpuSize = null;
if (machine.customProperties && machine.customProperties.gpuSize) {
    currentGpuSize = machine.customProperties.gpuSize.toString();
    System.log("Current GPU Size for machine " + machine.name + " = " + currentGpuSize);
}


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
        break; // 첫 번째 일치하는 zone에서 중단
    }
}

// projectZoneId 검증 추가
if (!projectZoneId) {
    System.log("No matching zone found for target region");
    return [];
}

var zoneComputes = aa.get("/iaas/api/zones/" + projectZoneId + "/computes").content;

var computeNames = [];
for each(var zoneCompute in zoneComputes){
    var profileTag = zoneCompute.tags.filter(function(item){return item.key == "profile"});
    var gpuTag = zoneCompute.tags.filter(function(item){return item.key == category && item.value == gpuModel});
    
    // 배열 안전성 검사 추가
    if(profileTag.length > 0 && profileTag.filter(function(item){return item.value == projectProfile}).length != 0 && gpuTag.length > 0){
        computeNames.push(zoneCompute.name); // 수정: [i] 제거
    }
}

var result = [];
for each(var computeName in computeNames){
    var cluster = VcPlugin.getAllClusterComputeResources(null, "xpath:name='" + computeName + "'")[0];
    var hosts = cluster.host;
    for (var h in hosts){
        var configManager = hosts[h].configManager;
        if (!configManager || !configManager.graphicsManager) {
            System.log("Graphics manager not available for host: " + hosts[h].name); // 수정: hostList -> hosts
            continue;
        }
        var gpuManager = configManager.graphicsManager;
        var vgpuProfileInfo = null;
        try {
            vgpuProfileInfo = hosts[h].config.sharedGpuCapabilities.filter( function(item){ return item.vgpu.split("-").length == 2;}); //gpuManager.retrieveVgpuProfileInfo();
        } catch (gpuError) {
            System.log("Failed to retrieve GPU profile info for host " + hosts[h].name + ": " + gpuError); // 수정: hostList -> hosts
            continue;
        }

        for(var g in vgpuProfileInfo){
            var gpuProfile = vgpuProfileInfo[g].vgpu;
            var match = gpuProfile.match(/-(\d+)/)
            
            if (!match || !match[1]) {
                continue;
            }

            var size = match[1].toString();                // "4" 같은 문자열

            // 🔴 현재 VM에 할당된 gpuSize는 제외
            if (currentGpuSize && size == currentGpuSize) {
                continue;
            }

            if (result.indexOf(size) === -1) {
                result.push(size);

            //var fbSize = vgpuProfileInfo[g].fbSizeInGib.toString();
            // 수정: some() 올바른 사용법
            /*if(result.indexOf(match[1]) === -1){
                result.push(match[1]);
            }*/
            }
        }
    }
}
// 수정: 숫자 정렬
result.sort(function(a, b) {
    return parseFloat(a) - parseFloat(b);
});

return result;
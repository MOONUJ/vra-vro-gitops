if(!category || !projectId || !regionLink ){return null;};
var aa = System.getModule("com.gvp").AaManager(true);

var tags = aa.get("/iaas/api/tags?$filter= key eq '"+category+"'").content
var project = aa.get("/iaas/api/projects/" + projectId);
var projectProfile = project.customProperties.profile;


//var profileDetails = aa.getUerp(profileLink);
//var targetRegionLink = profileDetails.provisioningRegionLink;
var targetRegionLink = regionLink;
for each (var zone in project.zones) {
    //var placementZoneLink = "/provisioning/resources/placement-zones/" + zone.zoneId;
    //var placementZone = aa.getUerp(placementZoneLink);
    var placementZoneLink = "/iaas/api/zones/" + zone.zoneId;
    var placementZone = aa.get(placementZoneLink)
    if (placementZone._links.region.href === targetRegionLink) {
        var projectZoneId = zone.zoneId;
    }
}

// projectZoneId 검증 추가
if (!projectZoneId) {
    System.log("No matching zone found for target region");
    return [];
}


var projectZoneId = zone.zoneId;
var zoneComputes = aa.get("/iaas/api/zones/" + projectZoneId + "/computes").content;

var tagValues = [];
for each(var zoneCompute in zoneComputes){
    var profileTag = zoneCompute.tags.filter(function(item){return item.key == "profile"});
    var gpuTag = zoneCompute.tags.filter(function(item){return item.key == category});
    if( profileTag.filter(function(item){return item.value == projectProfile}).length != 0 && gpuTag.length > 0){
        for (var i in gpuTag){
            tagValues.push(gpuTag[i].value)
        }
    }
}
var result = [];
for each(var tag in tags) {
    if(tagValues.indexOf(tag.value) != -1){
        result.push({
            label: tag.value.toUpperCase(),
            value: tag.value
        });
    }

}








result.sort(function(a, b) {
    return a.label.toUpperCase() < b.label.toUpperCase() ? -1 : 1;
});

return result;

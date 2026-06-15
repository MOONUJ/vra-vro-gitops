if(!cloudZoneLink) {return null;}
if(!gpuModel) {return null;}
if(!profile) {return null;}

var aa = System.getModule("com.gvp").AaManager(true);

var cloudZones = aa.get("/iaas/api/zones").content;
var filteredZones = cloudZones.filter( function(item){ return item._links.region.href == cloudZoneLink});

var result = [];
for each(var zone in filteredZones){
    var computes = aa.get("/iaas/api/zones/" + zone.id + "/computes").content;
    for each(var compute in computes){
        var gpuModelTag = compute.tags.filter(function(item) { return item.key == "gpuModel" &&  item.value == gpuModel });
        var profileTag = compute.tags.filter(function(item) { return item.key == "profile" &&  item.value == profile });
        if(gpuModelTag.length > 0 && profileTag.length >0 ){
            result.push(compute.name)
        }
    }

};

return result


var aa = System.getModule("com.gvp").AaManager(true);
var result = [];
for each(var zone in aa.get("/iaas/api/zones/").content) {
    computeLink = zone._links.computes.href
    for each(var compute in aa.get(computeLink).content){
        for each(var tag in compute.tags){
            if(tag.value == profile){
                result.push({
                    label: zone.description ? zone.description : zone.name,
                    value: zone.id,
                });        
            }
        }
    }
}
return result.sort(function (a, b) {
    return a.label.toUpperCase() < b.label.toUpperCase() ? -1 : 1;
});

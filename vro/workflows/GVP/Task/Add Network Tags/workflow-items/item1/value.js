var aa = System.getModule("com.gvp").AaManager(true);

for each(var network in networks){
    var fabric = aa.get("/iaas/api/fabric-networks/" + network);
    var segType = aa.get("/iaas/api/network-domains/" + fabric.networkDomainId).customProperties.__transportZoneTrafficType == "VLAN_BACKED"? "bridge": "overlay";
    var tags = fabric.tags;
    if(tags){
        var vpcSegTag = tags.filter(function(item){ return item.key == vpcSegCategory});
        var segTypeTag = tags.filter(function(item){ return item.key == segTypeCategory});
        var orgTag = tags.filter(function(item){ return item.key == orgCategory && item.value == orgCode});
        if(vpcSegTag == 0){
            tags.push({
                "key": vpcSegCategory,
                "value": fabric.name
            })
        }
        if(segTypeTag == 0){
            tags.push({
                "key": segTypeCategory,
                "value": segType
            })
        }
        if(orgTag == 0){
            tags.push({
                "key": orgCategory,
                "value": orgCode
            })
        }
    } else {
        var tags = [
            {
                "key": orgCategory,
                "value": orgCode
            },
            {
                "key": vpcSegCategory,
                "value": fabric.name
            },
            {
                "key": segTypeCategory,
                "value": segType
            }
        ]
    }


    aa.patch("/iaas/api/fabric-networks/" + network, {
        "tags": tags
    })
}
if(!resourceId){ return null; }

var aa = System.getModule("com.gvp").AaManager(true);


var machine = aa.get("/iaas/api/machines/" + resourceId); 

/*
var compute = aa.getUerp("/resources/compute/" + resourceId);
var machineInterfaces = compute.networkInterfaceLinks.filter(function(item){
    var interface = aa.getUerp(item);
    if(interface.tagLinks){
        var tag = aa.getUerp(interface.tagLinks[0]);
    } else {
        var tag = null;
    }
    return tag && tag.value == "overlay";
})
*/

var machineInterfaces = machine._links['network-interfaces'].hrefs.filter( function(item){
    var interface = aa.get(item);
    return interface.tags && interface.tags[0].value == "overlay"
})


var additionalNetworks = machine.customProperties.additionalNetworks?JSON.parse(machine.customProperties.additionalNetworks):[];
for each(var addIntf in additionalNetworks) {
    if(addIntf.tags[0].value == "overlay"){
        machineInterfaces.push(addIntf);
    }
}
var result = [];

/*
for (var i = 0; i < machineInterfaces.length; i++) {
    if( typeof machineInterfaces[i] == "string"){
        var interface = aa.getUerp(machineInterfaces[i]);
        result.push({
            label: "[" + i + "]" + interface.address,
            value: machineInterfaces[i]
        });       
    } else {
        result.push({
            label: "[" + i + "] " + machineInterfaces[i].address,
            value: machineInterfaces[i].id           
        })
    }
}
*/

for (var i = 0; i < machineInterfaces.length; i++) {
    if( typeof machineInterfaces[i] == "string"){
        var interface = aa.get(machineInterfaces[i]);
        result.push({
            label: "[" + i + "]" + interface.addresses[0],
            value: machineInterfaces[i]
        });
    } else {
        result.push({
            label: "[" + i + "] " + machineInterfaces[i].address,
            value: machineInterfaces[i].id           
        })
    }
}

return result;
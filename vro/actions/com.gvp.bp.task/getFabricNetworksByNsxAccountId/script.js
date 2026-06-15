if(!accountId) {return null}
var aa = System.getModule("com.gvp").AaManager(true);

var networks = aa.get("/iaas/api/fabric-networks?$top=500").content;

var result = [];
for each(var network in networks){
    if(network.cloudAccountIds[0] == accountId && network.name.indexOf(search?search: "") != -1){
        result.push({
            label: network.name,
            value: network.id
        })
    }
}
return result
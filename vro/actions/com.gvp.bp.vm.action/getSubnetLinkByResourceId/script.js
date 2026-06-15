if (!resourceId) { return null; }

var aa = System.getModule("com.gvp").AaManager(true);
var machine = aa.get("/iaas/api/machines/" + resourceId);
var project = aa.get("/iaas/api/projects/" + machine.projectId);
var cloudAccountId = machine.cloudAccountIds[0];
var orgCode =  project.customProperties.organization;
var orgTagCategory = aa.get("/iaas/api/tags?$filter=value eq '"+orgCode+"'").content[0].key;


var networks = aa.get("/iaas/api/networks").content;
var seen = {};
var filteredNetworks = [];
for (var i = 0; i< networks.length; i++){
    if(networks[i].tags){
        var key = networks[i].tags.filter(function(item){return item.key == 'vpcSegId'})[0].value;
        if(!seen[key]){
            seen[key] = true;
            filteredNetworks.push(networks[i]);
        }
    }

}
var result =  [];
if(networks.length == 0) { throw "Check the Network Profile"}
for each (var network in filteredNetworks){
    if( network.tags ) {
        var orgFilter = network.tags.filter(function(item) { return item.key == orgTagCategory && item.value.toLowerCase() == orgCode.toLowerCase()});
        var sharedFilter = network.tags.filter(function(item){ return item.key == orgTagCategory});
        //var segTypeFilter = network.tags.filter( function(item){ return item.key == "segType" && item.value != "bridge"});
        if (orgFilter.length > 0 || sharedFilter.length == 0 /* && segTypeFilter.length > 0 */) {
            result.push({
                label: network.name,
                value: network._links.self.href
            });
        }
    }
}

result.sort(function (a, b) {
    return a.label.toUpperCase() < b.label.toUpperCase() ? -1 : 1;
});

return result;

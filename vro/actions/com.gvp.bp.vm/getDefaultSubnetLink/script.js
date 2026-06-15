if (!regionLink || !orgCode || !orgTagCategory) { return null; }

var aa = System.getModule("com.gvp").AaManager(true);

var regionResp = aa.get(regionLink);
if (!regionResp || !regionResp.cloudAccountId) {
    throw "cloudAccountId not found in response for regionHref: " + regionHref;
} 
var cloudAccountId = regionResp.cloudAccountId;
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
        if ((orgFilter.length > 0 || sharedFilter.length == 0) &&  result.filter(function(item){ return item.label == network.name}).length == 0) {
            result.push({
                label: network.name,
                value: network._links.self.href
            });
        }
    }
}
/*
var subnetApi = "/resources/sub-networks?expand&$filter=endpointLink eq '/resources/endpoints/" + cloudAccountId + "'";
var subnetResp = aa.getUerp(subnetApi);

var result = [];
for (var key in subnetResp.documents) {
    if (!subnetResp.documents.hasOwnProperty(key)) continue;

    var subnet = subnetResp.documents[key];
    if (subnet.expandedTags && subnet.expandedTags.length > 0) {
        for (var i = 0; i < subnet.expandedTags.length; i++) {
            var tagObj = subnet.expandedTags[i];
            if (tagObj.tag && tagObj.tag.indexOf(orgTagCategory + "\n") === 0) {
                result.push({
                    label: subnet.name,
                    value: subnet.documentSelfLink
                });
                break; // 한 번 매칭되면 중복 추가 방지
            }
        }
    }
}
*/
result.sort(function (a, b) {
    return a.label.toUpperCase() < b.label.toUpperCase() ? -1 : 1;
});

return result[0].value;

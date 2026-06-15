if (!profileLink) { return null; }

var aa = System.getModule("com.gvp").AaManager(true);
var subnets = aa.getUerp("/resources/sub-networks?expand&$filter=customProperties.vpc eq '" + profileLink + "'");
var result = [];
for each(var subnetLink in subnets.documentLinks) {
    var subnet = subnets.documents[subnetLink];
    result.push({
        label: subnet.customProperties.displayName ? subnet.customProperties.displayName : subnet.name,
        value: subnetLink
    });
}
return result.sort(function (a, b) {
    return a.label.toUpperCase() < b.label.toUpperCase() ? -1 : 1;
});
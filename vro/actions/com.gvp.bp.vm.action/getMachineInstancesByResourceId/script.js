if(!resourceId) { return null };

var aa = System.getModule("com.gvp").AaManager(true);
//var vcsa = aa.get("/deployment/api/resources/" + resourceId).properties.account;
var machine = aa.get("/deployment/api/resources/" + resourceId);
var vcsa = aa.get("/iaas/api/cloud-accounts?$filter=name eq '" + machine.properties.account + "'").content[0].cloudAccountProperties.hostName;

var instances = Server.getConfigurationElementCategoryWithPath("GVP/Instance/" + vcsa ).configurationElements;
var result = [];
for each(var instance in instances){
    result.push(instance.name);
}
result.sort(function (a, b) {
    var aGB = a.split("-")[1];
    var bGB = b.split("-")[1];
    var aNum = parseInt(aGB.split("G")[0]);
    var bNum = parseInt(bGB.split("G")[0]);
    return aNum - bNum;
    return a.toUpperCase() < b.toUpperCase() ? -1 : 1;
});

return result;
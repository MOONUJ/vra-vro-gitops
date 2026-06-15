if(!machineInstance || !cloudZoneLink) { return null;}

var aa = System.getModule("com.gvp").AaManager(true);
var region = aa.get(cloudZoneLink);
var cloudAccount = aa.get("/iaas/api/cloud-accounts/" + region.cloudAccountId);
var vcsa = cloudAccount.cloudAccountProperties.hostName;
//var machine = aa.get("/deployment/api/resources/" + resourceId);
//var vcsa = aa.get("/iaas/api/cloud-accounts?$filter=name eq '" + machine.properties.account + "'").content[0].cloudAccountProperties.hostName;
//var vcsa = aa.get("/deployment/api/resources/" + resourceId).properties.account;
var instances = Server.getConfigurationElementCategoryWithPath("GVP/Instance/" + vcsa ).configurationElements;

for each(var instance in instances){
    if(instance.name == machineInstance){
        var result = instance.getAttributeWithKey("cluster").value;
    }    
}

return [result[0]]
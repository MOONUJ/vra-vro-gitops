if(!machineInstance || !resourceId) { return null;}

var aa = System.getModule("com.gvp").AaManager(true);
var machine = aa.get("/deployment/api/resources/" + resourceId);
var vcsa = aa.get("/iaas/api/cloud-accounts?$filter=name eq '" + machine.properties.account + "'").content[0].cloudAccountProperties.hostName;
//var vcsa = aa.get("/deployment/api/resources/" + resourceId).properties.account;
var instances = Server.getConfigurationElementCategoryWithPath("GVP/Instance/" + vcsa ).configurationElements;

for each(var instance in instances){
    if(instance.name == machineInstance){
        var result = instance.getAttributeWithKey("cpu").value;
    }    
}

return result
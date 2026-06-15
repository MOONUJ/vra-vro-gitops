if(!resourceId) { return null };

var aa = System.getModule("com.gvp").AaManager(true);
var machine = aa.get("/deployment/api/resources/" + resourceId);
var vcsa = aa.get("/iaas/api/cloud-accounts?$filter=name eq '" + machine.properties.account + "'").content[0].cloudAccountProperties.hostName;
//var vcsa = machine.properties.account;
var gpuProfile = machine.properties.gpuProfile;
System.log(vcsa);
var instances = Server.getConfigurationElementCategoryWithPath("GVP/Instance/" + vcsa ).configurationElements;

for each(var instance in instances){
    if(instance.getAttributeWithKey("gpuProfile").value == gpuProfile ){
        var result = instance.name;
        break;
    }
}

return result;
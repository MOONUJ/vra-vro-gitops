if(!resourceId){ return null;}

var aa = System.getModule("com.gvp").AaManager(true);
var machine = aa.get("/deployment/api/resources/" + resourceId);
var vcsa = aa.get("/iaas/api/cloud-accounts?$filter=name eq '" + machine.properties.account + "'").content[0].cloudAccountProperties.hostName;
return vcsa;
//return aa.get("/deployment/api/resources/" + resourceId).properties.account

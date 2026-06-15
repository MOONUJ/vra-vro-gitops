if(!resourceId) { return null;}

var aa = System.getModule("com.gvp").AaManager(true);
var machine = aa.get("/deployment/api/resources/" + resourceId);
return JSON.parse(machine.properties.vcenterClusterName)[0]

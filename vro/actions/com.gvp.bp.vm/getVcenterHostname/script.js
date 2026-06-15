if(!cloudZoneLink) {return null}
var aa =System.getModule("com.gvp").AaManager(true);
var region = aa.get(cloudZoneLink);

var cloudAccount = aa.get("/iaas/api/cloud-accounts/" + region.cloudAccountId);

return cloudAccount.cloudAccountProperties.hostName;
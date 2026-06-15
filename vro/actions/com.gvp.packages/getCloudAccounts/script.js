var aa = System.getModule("com.gvp").AaManager(true);
var result = [];
// register configurations
for each(var content in aa.get("/iaas/api/cloud-accounts").content) {
    try {
        var hostname = content.cloudAccountProperties.hostName.split(".")[0];
        var username = content.cloudAccountProperties.privateKeyId;
        result.push({
            hostname: content.cloudAccountProperties.hostName,
            username: username,
            password: null
        });
        System.log("register GVP/Endpoint/" + hostname);
    } catch (e) { System.log("already registered GVP/Endpoint/" + hostname); }
}

return result
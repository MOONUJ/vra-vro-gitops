var aa = System.getModule("com.gvp").AaManager(true);
var machine = aa.get("/iaas/api/machines/" + resourceId);
var computeName = machine.name;
var vm = VcPlugin.getAllVirtualMachines(null, "xpath:name='" + computeName + "'")[0];
var sdkConnection = vm.sdkConnection;
var ticket = sdkConnection.sessionManager.acquireCloneTicket();
var vcHostname = sdkConnection.name.split("/")[2];
var uri = "vmrc://clone:" + ticket + "@" + vcHostname + "/?moid=" + vm.moref.value;
return uri


var aa = System.getModule("com.gvp").AaManager(true);

var computeName = 'mujtest01';

var vm = VcPlugin.getAllVirtualMachines(null, "xpath:name='" + computeName + "'")[0];
var guestOperationsManager = vm.sdkConnection.guestOperationsManager;
var guestAuth = new VcNamePasswordAuthentication();
guestAuth.username = adminUsername;
guestAuth.password = adminPassword;

try {
    guestOperationsManager.authManager.validateCredentialsInGuest(vm, guestAuth);
} catch (e){
    System.log(e);
    throw "Failed to authenticate with the Virtual Machine";
}

var nsx = System.getModule("com.gvp").NsxManager(aa.getUerp(subnet.endpointLink).endpointProperties.hostName.split(".")[0]);
var nsxUpdated = false;
for each(var dhcp in nsx.get("/policy/api/v1" + subnet.customProperties.__path + "/dhcp-static-binding-configs").results) {
    if (dhcp.id == interfaceId) {
        dhcp.ip_address = newIpAddress;
        nsx.patch("/policy/api/v1" + dhcp.path, dhcp);
        nsxUpdated = true;
        break;
    }
}

var programPath = "/bin/bash";
var arguments = "-c 'sudo netplan apply'"

var guestProgramSpec = new VcGuestProgramSpec();
guestProgramSpec.programPath = programPath;
guestProgramSpec.arguments = arguments;

var processManager = guestOperationsManager.processManager;
try {
    var pid = processManager.startProgramInGuest(vm , guestAuth , guestProgramSpec);
} catch (e){
    throw e;
}


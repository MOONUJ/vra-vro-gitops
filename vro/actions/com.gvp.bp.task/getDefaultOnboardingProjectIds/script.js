if(!machineId || machineId.indexOf("null") >= 0){ 
    return "";
}
var aa = System.getModule("com.gvp").AaManager(true);

var machine = aa.get("/iaas/api/machines/" + machineId);
var vm = VcPlugin.getAllVirtualMachines(null, "xpath:instanceId='" + machine.customProperties.instanceUUID + "'")[0];
var projects =  aa.get("/project-service/api/projects?$filter=name eq '" + vm.parent.name + "'").content;

if(projects.length == 1) {
    return projects[0].id;
} else {
    return ""
}
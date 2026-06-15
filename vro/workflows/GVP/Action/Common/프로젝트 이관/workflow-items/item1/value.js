
var aa = System.getModule("com.gvp").AaManager(true);

try {
    var vms = aa.get("/iaas/api/machines?$filter=projectId eq '" + projectId + "'"  ).content;
    if(vms.length > 0) {
        var targetProject = aa.get("/iaas/api/projects/" + targetProjectId);
        for each(var vm in vms){
            System.log(vm.name + " Move to " + targetProject.name + " Folder ")
            var machine = VcPlugin.getAllVirtualMachines(null,"xpath:name='" + vm.name + "'");
            var vcName = machine[0].sdkId.split(".")[0];
            var folder = VcPlugin.getAllVmFolders(null, "xpath:name='" + targetProject.name + "' and contains(sdkId, '" + vcName + "')")[0];
            if(!folder){
                 System.log(vm.name + ": " + targetProject.name + " Not Founded ");
                var orgFolder = VcPlugin.getAllVmFolders(null,"xpath:name='" + targetProject.customProperties.organization + "' and contains(sdkId,'" + vcName + "')")[0];
                if(!orgFolder){
                    System.log(vm.name + ": " + targetProject.customProperties.organization + " Not Founded ");
                    var vmFolder = VcPlugin.getAllVmFolders(null,"xpath:name='vm' and contains(sdkId,'" + vcName + "')")[0];
                    System.log(vm.name + ":  Create " + target.customProperties.organization + " Folder");
                    var orgFolder = vmFolder.createFolder(targetProject.customProperties.organization);
                    System.log(vm.name + ":  Create " + targetProject.name + " Folder");
                    var folder = orgFolder.createFolder(targetProject.name);
                } else {
                    System.log(vm.name + ":  Create " + targetProject.name + " Folder");
                    var folder = orgFolder.createFolder(targetProject.name);
                }
            }
            var task = folder.moveIntoFolder_Task(machine);
            var actionResult = System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(task,false,1);
            System.log("Move Folder Action Result : " + actionResult);
        }
    }
} catch (e) {
    throw e;
}

var size = aa.get("/deployment/api/deployments?projects=" + projectId).totalElements;
var deployments = aa.get("/deployment/api/deployments?projects=" + projectId + "&size="+ size ).content;
var requestIds = [];
for each(var deployment in deployments){
    if(deployment.blueprintId == "inline-blueprint"){
       // aa.delete("/deployment/api/deployments/" + deployment.id);
    } else {
        try {
            var result = aa.post("/deployment/api/deployments/" + deployment.id + "/requests",{
                actionId: "Deployment.ChangeProject",
                inputs: {
                    targetProjectId: targetProjectId
                }
            })
            requestIds.push(result.id);
        } catch (e) {
            throw e;
        }

    }
}

var allSuccessful = false;
var count = 0;
while (!allSuccessful) {
    allSuccessful = true; // 매 루프마다 초기화
    var statuses = [];

    for (var i = 0; i < requestIds.length; i++) {
        var requestId = requestIds[i];
        var result = aa.get("/deployment/api/requests/" + requestId);
        statuses.push(result.status);

        if (result.status !== "SUCCESSFUL") {
            allSuccessful = false;
        }
        if (result.status == "FAILED"){
            throw "FAILED : " + result.details
        }
    }

    count++;
    if (count > 20) {
        throw "Waiting Time out"
    }
    // Optional: 너무 빠른 루프 방지
    System.sleep(5000); // 5초 대기 (아래에 sleep 함수 있음)    
}

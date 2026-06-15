var aa = System.getModule("com.gvp").AaManager(true);

/* deleted
var machine = aa.get("/iaas/api/machines/" + vmName);
var cloudAccountId = machine.cloudAccountIds[0];
var vcenterHostname =  aa.get("/iaas/api/cloud-accounts/" + cloudAccountId).cloudAccountProperties.hostName;
*/

for each( var machineId in machineIds ){
    var machine = aa.get("/iaas/api/machines/" + machineId);
    var cloudAccountId = machine.cloudAccountIds[0]
    var vcenterHostname =  aa.get("/iaas/api/cloud-accounts/" + cloudAccountId).cloudAccountProperties.hostName;
    var vm = VcPlugin.getAllVirtualMachines(null, "xpath:name='" + machine.name + "'")[0];

    var host = vm.summary.runtime.host;
    var clusterName = [host.parent.name]
    var project = aa.get("/iaas/api/projects?$filter=name eq '" + vm.parent.name + "'").content;
    if(project.length > 0 ){
        var projectId = project[0].id;
    } else {
        throw "VM Folder Name's Project is not Found"
    }

    if(vm.config.guestId.indexOf("rocky") >= 0){
        var osName = "rocky";
        var isLinux = true;
    } else if (vm.config.guestId.indexOf("ubuntu") >= 0 ) {
        var osName = "ubuntu";
        var isLinux = true
    } else {
        throw "Please check the VM OS type, acceptable os is rocky and ubuntu."
    }

    var customProperties = {
        "isLinux": isLinux,
        "osName": osName,
        "displayName": vm.name,
        "additionalNetworks": "[]",
        "vcenterHostName": vcenterHostname,
        "vcenterClusterName": JSON.stringify(clusterName),
        "note": vm.annotation,
        "createDate": vm.config.createDate
    };

    var devices = vm.config.hardware.device;
    var pciDevice = devices.filter( function(item){
        return item instanceof VcVirtualPCIPassthrough;
    });


    if( pciDevice.length > 0){
        var isGpu = true;
        var gpuProfile = pciDevice[0].backing.vgpu;
        var gpuSize =  System.getModule("com.gvp.bp.task").getGpuSizeByGpuProfile(gpuProfile);
        var gpuModel = System.getModule("com.gvp.bp.task").getGpuModelByGpuProfile(gpuProfile);
        var gpuDeviceCount = pciDevice.length;

        var categories =  Server.getConfigurationElementCategoryWithPath("GVP/Instance").subCategories
        for each( var category in categories){
            if( vm.sdkConnection.name.indexOf(category.name) >= 0) {
                var instances = category.configurationElements;
                break;
            }
        }
        for each(var instance in instances){
            if(instance.getAttributeWithKey("gpuProfile").value == gpuProfile){
                var machineInstance = instance.name
            }
        }
        if(!machineInstance){
            throw "Cloud not found acceptable machine instance"
        }

    } else {
        var isGpu = false;
    }
    if(isGpu){
        customProperties.gpuDeviceCount = gpuDeviceCount;
        customProperties.gpuModel = gpuModel;
        customProperties.gpuSize = gpuSize;
        customProperties.gpuProfile = gpuProfile;
        customProperties.machineInstance = machineInstance;
    }

    var onboardingPlanPayload = {
    "name": "ONBOARDING - " + vm.name,
    "projectId": projectId,
    "endpointIds": [
        cloudAccountId
    ],
    "customProperties": customProperties,
    "usePlacements": false
    }
    var onboardingPlan = aa.post("/relocation/onboarding/plan", onboardingPlanPayload);

    var deploymentPayload = {
        "deployments": [
            {
                "name": isGpu?"Onboarding-GPUVM-" + vm.name: "Onboarding-VM-" + vm.name,
                "resources": [
                    {
                        "link": "/resources/compute/" + machine.id,
                        "name": machine.name,
                        "tagLinks": []
                    }
                ]
            }
        ],
        "planLink": onboardingPlan.documentSelfLink
    }

    aa.post("/relocation/onboarding/task/create-deployment-bulk", deploymentPayload);

    var executePayload = {
        "planLink": onboardingPlan.documentSelfLink
    };

    //aa.post("/relocation/api/wo/execute-plan", executePayload);


}








var aa = System.getModule("com.gvp").AaManager(true);

var machine = aa.get("/iaas/api/machines/" + vmName);
var cloudAccountId = machine.cloudAccountIds[0];
var vcenterHostname =  aa.get("/iaas/api/cloud-accounts/" + cloudAccountId).cloudAccountProperties.hostName;
var vm = VcPlugin.getAllVirtualMachines(null, "xpath:name='" + machine.name + "'")[0];
var host = vm.summary.runtime.host;
var clusterName = [host.parent.name]
var customProperties = {
    "isLinux": isLinux,
    "osName": osName,
    "displayName": machine.name,
    "additionalNetworks": "[]",
    "vcenterHostName": vcenterHostname,
    "vcenterClusterName": JSON.stringify(clusterName),
    "note": ""
};
if(gpuDeviceCount != '' && gpuModel != '' && gpuSize != '' && gpuProfile !=''){
    var isGpu = true;
} else {
    var isGpu = false;
}
if(isGpu){
    customProperties.gpuDeviceCount = gpuDeviceCount;
    customProperties.gpuModel = gpuModel;
    customProperties.gpuSize = gpuSize;
    customProperties.gpuProfile = gpuProfile;
}

var onboardingPlanPayload = {
  "name": "ONBOARDING - " + machine.name,
  "projectId": project,
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
            "name": isGpu?"Onboarding-GPUVM-" + machine.name: "Onboarding-VM-" + machine.name,
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
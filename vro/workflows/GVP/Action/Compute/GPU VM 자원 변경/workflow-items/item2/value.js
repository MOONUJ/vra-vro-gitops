/**
 * vRealize Automation VM Resize and GPU Management Workflow
 * Refactored for better maintainability and readability
 */

// ==================== CONSTANTS ====================
var CONSTANTS = {
    ACTIONS: {
        RESIZE: "Cloud.vSphere.Machine.Resize"
    },
    DEFAULTS: {
        SLEEP_INTERVAL: 10000,
        MAX_RETRIES: 10
    },
    STATUS: {
        SUCCESSFUL: "SUCCESSFUL"
    }
};

// ==================== UTILITY FUNCTIONS ====================

/**
 * Wait for request completion with timeout
 */
function waitForRequestCompletion(requestId, aa, resourceId) {
    var requestSuccess = false;
    var retryCount = 0;
    var maxRetries = CONSTANTS.DEFAULTS.MAX_RETRIES;
    
    while (!requestSuccess && retryCount < maxRetries) {
        try {
            var requests = aa.get("/deployment/api/resources/" + resourceId + "/requests").content;
            var targetAction = null;
            
            for each(var request in requests) {
                if (request.id === requestId) {
                    targetAction = request;
                    break;
                }
            }
            
            if (targetAction && targetAction.status === CONSTANTS.STATUS.SUCCESSFUL) {
                requestSuccess = true;
                return targetAction.name + " - " + requestId + " Successful";
            }
            
            System.sleep(CONSTANTS.DEFAULTS.SLEEP_INTERVAL);
            retryCount++;
            
        } catch (error) {
            System.error("Error checking request status: " + error.message);
            throw error;
        }
    }
    
    throw new Error("Request timeout: " + requestId + " exceeded maximum retries (" + maxRetries + ")");
}

// ==================== MAIN WORKFLOW FUNCTIONS ====================

/**
 * Initialize workflow environment and get required objects
 */
function initializeWorkflow() {
    try {
        var aa = System.getModule("com.gvp").AaManager(true);
        var machine = aa.get("/iaas/api/machines/" + resourceId);
        var endpointId = machine.cloudAccountIds[0];
        var endpointLink = "/resources/endpoints/" + endpointId;
        var endpointName = aa.getUerp(endpointLink).endpointProperties.hostName.split(".")[0];
        var vcConf = System.getModule("com.gvp").ConfManager().load("/GVP/Endpoint/" + endpointName);
        
        // Get vRA Host
        var vraHosts = Server.findAllForType("VRA:Host");
        var vraHost = null;
        for each(var host in vraHosts) {
            if (host.name === "Admin") {
                vraHost = host;
                break;
            }
        }
        
        if (!vraHost) {
            throw new Error("VRA Host 'Admin' not found");
        }
        
        return {
            aa: aa,
            machine: machine,
            vcConf: vcConf,
            vraHost: vraHost
        };
        
    } catch (error) {
        System.error("Failed to initialize workflow: " + error.message);
        throw error;
    }
}

/**
 * Check if VM resize is required
 */
function isResizeRequired(machine, cpuCount, memoryCount) {
    var currentCpuCount = parseInt(machine.customProperties.cpuCount) || 0;
    var currentMemoryGB = parseInt(machine.customProperties.memoryGB) || 0;
    
    return (cpuCount !== currentCpuCount) || (memoryCount !== currentMemoryGB);
}

/**
 * Resize VM if required
 */
function resizeVMIfRequired(aa, resourceId, cpuCount, memoryCount, machine) {
    if (!isResizeRequired(machine, cpuCount, memoryCount)) {
        System.log("VM resize not required");
        return;
    }
    
    try {
        System.log("Starting VM resize...");
        var request = aa.post("/deployment/api/resources/" + resourceId + "/requests", {
            "actionId": CONSTANTS.ACTIONS.RESIZE,
            "inputs": {
                "cpuCount": cpuCount,
                "totalMemoryMB": memoryCount * 1024
            }
        });
        
        var result = waitForRequestCompletion(request.id, aa, resourceId);
        System.log("VM resize completed: " + result);
        
    } catch (error) {
        System.error("Failed to resize VM: " + error.message);
        throw error;
    }
}

/**
 * Check if GPU Resize is required
 */
function isGpuResizeRequired(machine, gpuSize) {
    if (!gpuSize) {
        return false;
    }
    
    var currentGpuSize = machine.customProperties.gpuSize ? 
        machine.customProperties.gpuSize : null;
    
    return gpuSize !== currentGpuSize;
}

/**
 * Resize GPU if required
 */
function resizeGpuIfRequired(aa, resourceId, gpuModel, gpuSize, machine) {
    // gpuModel과 gpuSize 둘 다 체크
    if (!gpuModel || !gpuSize) {
        System.log("GPU resize not required: gpuModel or gpuSize not provided");
        return;
    }
    
    if (!isGpuResizeRequired(machine, gpuSize)) {
        System.log("GPU resize not required");
        return;
    }
    
    try {
        System.log("Starting GPU resize...");
        var vm = VcPlugin.getAllVirtualMachines(null,"xpath:name='" + machine.name+ "'")[0];
        var host = vm.runtime.host;
        var gpuProfiles = host.config.sharedGpuCapabilities;
        var devices = vm.config.hardware.device;
        var pciDevice = devices.filter( function(item){
            return item instanceof VcVirtualPCIPassthrough;
        });
        if(pciDevice.length == 0) {
            throw "Cannot found gpu device";
        }
        var suffix = pciDevice[0].backing.vgpu[pciDevice[0].backing.vgpu.length - 1]
        var gpuProfile = gpuProfiles.filter( function(item) {
            var profileName = item.vgpu.toLowerCase();
            var expectedProfile = "grid_" + gpuModel.toLowerCase() + "-" + gpuSize + suffix;

            return profileName == expectedProfile;
        });
        if(gpuProfile.length == 0) {
            throw "Cannot found gpu profile";
        }
        
        System.getModule("com.vmware.library.vc.vm.tools").vim3WaitToolsStarted(vm, 1, 5);
        System.getModule("com.vmware.library.vc.vm.power").shutdownVM(vm, 10, 1);

        var deviceChange = new Array();
        deviceChange[0] = new VcVirtualDeviceConfigSpec();
        deviceChange[0].device = pciDevice[0];
        deviceChange[0].device.backing.vgpu = gpuProfile[0].vgpu;
        deviceChange[0].operation = VcVirtualDeviceConfigSpecOperation.edit;

        var spec = new VcVirtualMachineConfigSpec();
        spec.deviceChange = deviceChange;
        var task = vm.reconfigVM_Task(spec);
        System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(task, false, 1) ;
        var powerTask = vm.powerOnVM_Task();
        System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(powerTask, false, 1) ;
        System.getModule("com.vmware.library.vc.vm.tools").vim3WaitToolsStarted(vm, 1, 5);

        aa.patch("/iaas/api/machines/" + resourceId, {
            "customProperties": {
                "gpuSize": gpuSize
            }
        });

        System.log("GPU resize completed");
        
    } catch (error) {
        System.error("Failed to resize GPU: " + error.message);
        throw error;
    }
}

// ==================== MAIN EXECUTION ====================

/**
 * Main workflow execution
 */
function executeWorkflow() {
    try {
        System.log("Starting VM and GPU management workflow...");
        
        // Initialize workflow context
        var context = initializeWorkflow();
        
        // Execute VM resize if required
        resizeVMIfRequired(context.aa, resourceId, cpuCount, memoryCount, context.machine);

        // Execute GPU resize if required
        resizeGpuIfRequired(context.aa, resourceId, gpuModel, gpuSize, context.machine);
        
        System.log("VM and GPU management workflow completed successfully");
        
    } catch (error) {
        System.error("Workflow execution failed: " + error.message);
        throw error;
    }
}

// Execute the main workflow
executeWorkflow();
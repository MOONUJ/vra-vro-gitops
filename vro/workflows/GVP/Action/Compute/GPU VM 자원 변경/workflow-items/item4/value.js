/**
 * ============================================================================
 * VM Resize Workflow - CPU/Memory Only
 * ============================================================================
 * 
 * Input Parameters:
 * - resourceId (string, required): VM resource identifier
 * - machineInstance (string, required) : Target Flavor (CPU, Memory, gpuModel, gpuSize)
 * 
 * Outputs:
 * - resizeResult (boolean): Success/failure status
 * - resizeMessage (string): Result message
 * 
 * Features:
 * - Automatic power state management by vRA (shutdown → resize → power on)
 * - Enhanced error handling for API calls
 * - Detailed progress logging with status descriptions
 * - Real-time elapsed time tracking
 * - Request ID not found handling
 * - customProperties null check
 * - Network error handling
 * - User-friendly status messages
 * 
 * Note:
 * - If VM is powered on, vRA will automatically manage power state
 * - Expected time: 1-2 min (powered off) or 3-7 min (powered on)
 * ============================================================================
 */

(function() {
    'use strict';
    
    var CONFIG = {
        ACTION_RESIZE: "Cloud.vSphere.Machine.Resize",
        SLEEP_INTERVAL: 10000,
        MAX_RETRIES: 20,
        STATUS_SUCCESS: "SUCCESSFUL",
        STATUS_FAILED: "FAILED"
    };
    
    function logInfo(message) {
        System.log("[VM-RESIZE] " + message);
    }
    
    function logWarn(message) {
        System.warn("[VM-RESIZE] " + message);
    }
    
    function logError(message) {
        System.error("[VM-RESIZE] " + message);
    }
    
    function repeatString(str, count) {
        var result = "";
        for (var i = 0; i < count; i++) {
            result += str;
        }
        return result;
    }
    
    function trimString(str) {
        if (typeof str !== 'string') return str;
        return str.replace(/^\s+|\s+$/g, '');
    }
    
    function isArray(obj) {
        return Object.prototype.toString.call(obj) === '[object Array]';
    }
    
    function logSection(title) {
        var separator = repeatString("=", 60);
        System.log(separator);
        System.log("  " + title);
        System.log(separator);
    }
    
    
    function validateInputs() {
        var errors = [];
        
        if (!resourceId || trimString(resourceId) === "") {
            errors.push("resourceId is required");
        }
        
        if (!machineInstance || trimString(machineInstance) === "") {
            errors.push("machineInstance is required");
        }
        
        /* Delete Input
        if (cpuCount !== undefined && cpuCount !== null) {
            if (typeof cpuCount !== 'number' || cpuCount <= 0) {
                errors.push("cpuCount must be a positive number");
            }
        }
        
        if (memoryCount !== undefined && memoryCount !== null) {
            if (typeof memoryCount !== 'number' || memoryCount <= 0) {
                errors.push("memoryCount must be a positive number");
            }
        }
        */
        
        
        if (errors.length > 0) {
            throw new Error("Input validation failed:\n  - " + errors.join("\n  - "));
        }
        
        logInfo("Input validation passed");
    }
    
    function waitForCompletion(requestId, aa) {
        var retries = 0;
        
        logInfo("Waiting for resize to complete...");
        
        while (retries < CONFIG.MAX_RETRIES) {
            try {
                var response = aa.get("/deployment/api/resources/" + resourceId + "/requests");
                var requests = response.content;
                
                for (var i = 0; i < requests.length; i++) {
                    if (requests[i].id === requestId) {
                        var status = requests[i].status;
                        
                        if (status === CONFIG.STATUS_SUCCESS) {
                            logInfo("✓ Resize completed successfully");
                            return;
                        }
                        
                        if (status === CONFIG.STATUS_FAILED) {
                            throw new Error("Resize failed: " + (requests[i].message || "Unknown error"));
                        }
                        
                        logInfo("⟳ Status: " + status);
                        break;
                    }
                }
                
            } catch (error) {
                if (error.message.indexOf("Resize failed") === 0) {
                    throw error;
                }
                logWarn("API error: " + error.message);
            }
            
            System.sleep(CONFIG.SLEEP_INTERVAL);
            retries++;
        }
        
        throw new Error("Request timeout");
    }
    
    function main() {
        logSection("VM Resize Workflow - START");
        
        try {
            // Validate inputs
            validateInputs();
            
            /* no more use
            // Skip if no resize parameters provided
            if (cpuCount === undefined && memoryCount === undefined && coresPerSocket === undefined) {
                resizeResult = true;
                resizeMessage = "VM resize skipped: No CPU/Memory/CoresPerSocket parameters provided";
                logInfo(resizeMessage);
                logSection("VM Resize Workflow - COMPLETED (No changes)");
                return;
            }
            */
            
            // Initialize AA client
            logInfo("Initializing Aria Automation client...");
            var aa;
            try {
                aa = System.getModule("com.gvp").AaManager(true);
            } catch (error) {
                throw new Error("Failed to initialize AA client: " + error.message);
            }
            
            // Get machine information
            logInfo("Retrieving machine information for: " + resourceId);
            var machine;
            try {
                machine = aa.get("/iaas/api/machines/" + resourceId);
            } catch (error) {
                throw new Error("Failed to retrieve machine: " + error.message);
            }
            
            if (!machine) {
                throw new Error("Machine not found: " + resourceId);
            }
            
            logInfo("Machine found: " + machine.name);
            
            // Validate customProperties
            if (!machine.customProperties) {
                throw new Error("Machine customProperties not found or invalid");
            }
            
            // Get current values
            var currentCpu = parseInt(machine.customProperties.cpuCount) || 0;
            var currentMemory = parseInt(machine.customProperties.memoryGB) || 0;
            
            logInfo("Current configuration - CPU: " + currentCpu + ", Memory: " + currentMemory + "GB");
            var mc = aa.get("/deployment/api/resources/" + resourceId);
            var vcsa = aa.get("/iaas/api/cloud-accounts?$filter=name eq '" + mc.properties.account + "'").content[0].cloudAccountProperties.hostName;
            //var vcsa = aa.get("/deployment/api/resources/" + resourceId).properties.account;
            var instance = Server.getConfigurationElementCategoryWithPath("GVP/Instance/" + vcsa).configurationElements.filter(function (item){ return item.name == machineInstance })[0];
            var targetCpu = instance.getAttributeWithKey("cpu").value || currentCpu;
            var targetMemory = instance.getAttributeWithKey("memory").value || currentMemory;
            
            
            // Check if resize needed
            if (targetCpu === currentCpu && targetMemory === currentMemory) {
                resizeResult = true;
                resizeMessage = "VM resize skipped: Current values match target (CPU: " + currentCpu + ", Memory: " + currentMemory + "GB)";
                logInfo(resizeMessage);
                logSection("VM Resize Workflow - COMPLETED (No changes)");
                //return;
            } else {      
                logInfo("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                logInfo("Resize Changes:");
                if (currentCpu !== targetCpu) {
                    logInfo("  • CPU: " + currentCpu + " → " + targetCpu + " cores (" + (targetCpu > currentCpu ? "+" : "") + (targetCpu - currentCpu) + ")");
                }
                if (currentMemory !== targetMemory) {
                    logInfo("  • Memory: " + currentMemory + "GB → " + targetMemory + "GB (" + (targetMemory > currentMemory ? "+" : "") + (targetMemory - currentMemory) + "GB)");
                }
                logInfo("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
                
                // Submit resize request
                logInfo("Submitting resize request...");
                var request = aa.post("/deployment/api/resources/" + resourceId + "/requests", {
                    actionId: CONFIG.ACTION_RESIZE,
                    inputs: {
                        cpuCount: targetCpu,                    
                        totalMemoryMB: targetMemory * 1024,  // GB → MB 자동 변환
                        rebootMachine: true
                    }
                });
                
                if (!request || !request.id) {
                    throw new Error("Invalid request response");
                }
                
                logInfo("✓ Request submitted - ID: " + request.id);
                
                // Wait for completion
                logInfo("");
                logInfo("Waiting for resize operation to complete...");
                waitForCompletion(request.id, aa);
                
                resizeResult = true;
                resizeMessage = "VM resize completed successfully (CPU: " + targetCpu + ", Memory: " + targetMemory + "GB)";
                logInfo("✓ Resize completed successfully");
                logSection("VM Resize Workflow - COMPLETED");                
            }

            
        } catch (error) {
            resizeResult = false;
            resizeMessage = "VM resize failed: " + error.message;
            logError(resizeMessage);
            logSection("VM Resize Workflow - FAILED");
            throw error;
        }
//-----------------------------------------------
        var asisGpuModel = machine.customProperties.gpuModel;
        var asisGpuSize = machine.customProperties.gpuSize;
        var gpuDeviceCount =instance.getAttributeWithKey("deviceCount").value;;
        var gpuModel = instance.getAttributeWithKey("gpuModel").value;;
        var gpuSize = instance.getAttributeWithKey("gpuSize").value;;
        var gpuProfile = instance.getAttributeWithKey("gpuProfile").value;;
        

        var vm = VcPlugin.getAllVirtualMachines(null,"xpath:name='" + machine.name + "'")[0];
        var devices = vm.config.hardware.device;
        var pciDevice = devices.filter( function(item){
            return item instanceof VcVirtualPCIPassthrough;
        });
        var asisGpuDeviceCount = pciDevice.length;
        var asisGpuProfile = pciDevice[0].backing.vgpu;
        try {
            System.log("Wait VM Tools Started");
            System.getModule("com.vmware.library.vc.vm.tools").vim3WaitToolsStarted(vm, 1, 20);
            System.log("Shut Down VM");
            System.getModule("com.vmware.library.vc.vm.power").shutdownVMAndForce(vm, 20, 1);
            

            if( asisGpuDeviceCount < gpuDeviceCount ){
                for (var key in devices) {
                    var device = devices[key];
                    if (device instanceof VcVirtualPCIController){
                        var controllerKey = device.key;
                    }
                }

                for(var i = asisGpuDeviceCount; i < gpuDeviceCount; i++){
                    var deviceChange = new Array();
                    deviceChange[0] = new VcVirtualDeviceConfigSpec();
                    deviceChange[0].device = new VcVirtualPCIPassthrough();
                    deviceChange[0].device.controllerKey = controllerKey; 
                    deviceChange[0].device.backing = new VcVirtualPCIPassthroughVmiopBackingInfo();
                    deviceChange[0].device.backing.vgpu = gpuProfile;
                    deviceChange[0].device.slotInfo = new VcVirtualDevicePciBusSlotInfo();
                    deviceChange[0].device.unitNumber = null;
                    deviceChange[0].device.key = null;
                    deviceChange[0].device.deviceInfo = new VcDescription();
                    deviceChange[0].device.deviceInfo.summary = "NVIDIA GRID vGPU";
                    deviceChange[0].device.deviceInfo.label = "PCI device " + i.toString();
                    deviceChange[0].operation = VcVirtualDeviceConfigSpecOperation.add;

                    var spec = new VcVirtualMachineConfigSpec();
                    spec.deviceChange = deviceChange;
                    var task = vm.reconfigVM_Task(spec);

                    System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(task, false, 1) ;
                    System.log("Device" + i.toString() + " Attach Success!");
                }
            } else if( asisGpuDeviceCount > gpuDeviceCount ){
                for( var i=gpuDeviceCount; i < asisGpuDeviceCount; i++) {
                    var deviceChange = new Array();
                    deviceChange[0] = new VcVirtualDeviceConfigSpec();
                    deviceChange[0].device = pciDevice[i];
                    deviceChange[0].operation = VcVirtualDeviceConfigSpecOperation.remove;

                    var spec = new VcVirtualMachineConfigSpec();
                    spec.deviceChange = deviceChange;
                    var task = vm.reconfigVM_Task(spec);

                    System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(task, false, 1) ;
                    System.log("Device" + i.toString() + " Detach Success!");
                    //var pciDevice = pciDevice.pop();
                }

            } 
            if (asisGpuProfile != gpuProfile){
                var vm = VcPlugin.getAllVirtualMachines(null,"xpath:name='" + machine.name + "'")[0];
                var devices = vm.config.hardware.device;
                var pciDevice = devices.filter( function(item){
                    return item instanceof VcVirtualPCIPassthrough;
                });
                for (var i=0; i < pciDevice.length; i++){
                    var deviceChange = new Array();
                    deviceChange[0] = new VcVirtualDeviceConfigSpec();
                    deviceChange[0].device = pciDevice[i];
                    deviceChange[0].device.backing.vgpu = gpuProfile
                    deviceChange[0].operation = VcVirtualDeviceConfigSpecOperation.edit;

                    var spec = new VcVirtualMachineConfigSpec();
                    spec.deviceChange = deviceChange;
                    var task = vm.reconfigVM_Task(spec);
                    System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(task, false, 1) ;
                    System.log("Device" + i.toString() + " Edit Success!");
                }
            }

            System.log("VM Power ON");
            var powerTask = vm.powerOnVM_Task();
            System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(powerTask, false, 1) ;
            System.getModule("com.vmware.library.vc.vm.tools").vim3WaitToolsStarted(vm, 1, 5);

            aa.patch("/iaas/api/machines/" + machine.id, {
                "customProperties": {
                    "gpuSize": gpuSize,
                    "gpuDeviceCount": gpuDeviceCount.toString(),
                    "gpuModel": gpuModel,
                    "gpuProfile": gpuProfile
                }
            });
            var compute = aa.getUerp("/resources/compute/" + machine.id);
            compute.customProperties.gpuSize = gpuSize;
            compute.customProperties.gpuDeviceCount = gpuDeviceCount.toString();
            compute.customProperties.gpuModel = gpuModel;
            compute.customProperties.gpuProfile = gpuProfile;
            aa.patchUerp(compute['documentSelfLink'], compute)
        } catch (e) {
            throw e;
        }

// -----------------------------------------------
        // GPU Change
        /*
        try {
            var vm = VcPlugin.getAllVirtualMachines(null,"xpath:name='" + machine.name+ "'")[0];
            var devices = vm.config.hardware.device;
            var pciDevice = devices.filter( function(item){ return item instanceof VcVirtualPCIPassthrough; });
            if(pciDevice.length == 0) { throw "Cannot found gpu device"; }
            var currentGpuModel = machine.customProperties.gpuModel;
            var currentGpuSize = machine.customProperties.gpuSize;
            var currentGpuProfile = machine.customProperties.gpuProfile;
            var currentDeviceCount = pciDevice.length;
            var gpuModel = instance.getAttributeWithKey("gpuModel").value;
            var gpuSize = instance.getAttributeWithKey("gpuSize").value;
            var targetGpuProfile = instance.getAttributeWithKey("gpuProfile").value;
            var targetDeviceCount = instance.getAttributeWithKey("deviceCount").value
            if (currentGpuProfile != targetGpuProfile) {
                System.log("Starting GPU Resize...");
                if(currentDeviceCount > targetDeviceCount){
                    System.log("Remove GPU Device...")
                    
                } else if( currentDeviceCount < targetDeviceCount){
                    System.log("Add GPU Device...")
                } 
            }
            System.log("Starting GPU resize...");
            //var vm = VcPlugin.getAllVirtualMachines(null,"xpath:name='" + machine.name+ "'")[0];
            var host = vm.runtime.host;
            var gpuProfiles = host.config.sharedGpuCapabilities;
            //var devices = vm.config.hardware.device;
            //var pciDevice = devices.filter( function(item){ return item instanceof VcVirtualPCIPassthrough; });
            //if(pciDevice.length == 0) { throw "Cannot found gpu device"; }
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
        */
    }
    // Execute workflow
    main();
    
})();
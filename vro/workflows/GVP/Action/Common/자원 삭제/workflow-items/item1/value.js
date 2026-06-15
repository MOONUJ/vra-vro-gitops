// Constants
var RESOURCE_TYPES = {
    VSPHERE_MACHINE: "Cloud.vSphere.Machine",
    CUSTOM_PROJECT: "Custom.Project",
    VRO_WORKFLOW: "vro.workflow"
};

var POLLING_CONFIG = {
    MAX_ATTEMPTS: 20,
    SLEEP_INTERVAL: 5000, // 5 seconds
    VM_STATE_POWERED_ON: "poweredOn"
};

// Initialize
var aa = System.getModule("com.gvp").AaManager(true);
var requestIds = [];

// Main execution
try {
    var resourcesToProcess = validateAndNormalizeInputs();
    var deleteRequests = processResourcesByType(resourcesToProcess);
    waitForAllRequestsToComplete(deleteRequests);
    System.log("All resources deleted successfully");
} catch (error) {
    System.error("Resource deletion failed: " + error);
    throw error;
}

/**
 * 입력값 검증 및 정규화
 */
function validateAndNormalizeInputs() {
    if (!resourceIds && !resourceId) {
        throw "Cannot Empty Resource Ids";
    }
    if (!resourceType) {
        throw "Cannot Empty Resource Type";
    }

    // 단일 resourceId를 배열로 변환하여 통일된 처리
    if (resourceId) {
        return [resourceId];
    }
    return resourceIds;
}

/**
 * 리소스 타입별 처리 분기
 */
function processResourcesByType(resources) {
    switch (resourceType) {
        case RESOURCE_TYPES.VSPHERE_MACHINE:
            return processVSphereMachines(resources);
        case RESOURCE_TYPES.CUSTOM_PROJECT:
            return processCustomProjects(resources);
        default:
            return processGenericResources(resources);
    }
}

/**
 * vSphere Machine 리소스 처리
 */
function processVSphereMachines(resources) {
    var deleteRequests = [];
    
    for each (var resourceId in resources) {
        try {
            var machine = aa.get("/deployment/api/resources/" + resourceId);
            validateVMCanBeDeleted(machine);
            
            var deploymentId = machine.deploymentId;
            var machineCount = countMachinesInDeployment(deploymentId);
            var deleteRequest = deleteMachineOrDeployment(deploymentId, resourceId, machineCount);
            
            deleteRequests.push(deleteRequest.id);
        } catch (error) {
            System.error("Failed to process vSphere machine " + resourceId + ": " + error);
            throw error;
        }
    }
    
    return deleteRequests;
}

/**
 * VM 삭제 가능 여부 검증
 */
function validateVMCanBeDeleted(machine) {
    var vm = VcPlugin.getAllVirtualMachines(null, "xpath:name='" + machine.name + "'")[0];
    if (vm && vm.state === POLLING_CONFIG.VM_STATE_POWERED_ON) {
        throw "Cannot Delete VM. VM '" + machine.name + "' is Powered ON";
    }
}

/**
 * 배포에 포함된 Machine 개수 계산
 */
function countMachinesInDeployment(deploymentId) {
    var deploymentResources = aa.get("/deployment/api/deployments/" + deploymentId + "/resources").content;
    var count = 0;
    
    for each (var resource in deploymentResources) {
        if (resource.type === RESOURCE_TYPES.VSPHERE_MACHINE) {
            count++;
        }
    }
    
    return count;
}

/**
 * Machine 또는 전체 Deployment 삭제
 */
function deleteMachineOrDeployment(deploymentId, resourceId, machineCount) {
    if (machineCount >= 2) {
        // 여러 머신이 있으면 해당 리소스만 삭제
        return aa.delete("/deployment/api/deployments/" + deploymentId + "/resources/" + resourceId);
    } else {
        // 단일 머신이면 전체 배포 삭제
        return aa.delete("/deployment/api/deployments/" + deploymentId);
    }
}

/**
 * Custom Project 리소스 처리
 */
function processCustomProjects(resources) {
    var deleteRequests = [];
    var customProjects = aa.get("/deployment/api/resources?resourceTypes=Custom.Project").content;
    
    for each (var resourceId in resources) {
        try {
            // 프로젝트의 관련 액션 리소스들을 먼저 삭제
            var actionDeleteRequests = deleteProjectActionResources(resourceId);
            if (actionDeleteRequests.length > 0) {
                waitForAllRequestsToComplete(actionDeleteRequests);
            }
            
            // 프로젝트 자체 삭제
            var project = findProjectByResourceId(customProjects, resourceId);
            var deleteRequest = aa.delete("/deployment/api/deployments/" + project.deploymentId);
            deleteRequests.push(deleteRequest.id);
            
        } catch (error) {
            System.error("Failed to process custom project " + resourceId + ": " + error);
            throw error;
        }
    }
    
    return deleteRequests;
}

/**
 * 프로젝트의 액션 리소스들 삭제
 */
function deleteProjectActionResources(projectId) {
    var actionResources = aa.get("/deployment/api/resources?resourceTypes=" + RESOURCE_TYPES.VRO_WORKFLOW + "&projects=" + projectId);
    var deleteRequests = [];
    
    if (actionResources.totalElements > 0) {
        for (var i = 0; i < actionResources.totalPages; i++) {
            var pageResources = aa.get("/deployment/api/resources?resourceTypes=" + RESOURCE_TYPES.VRO_WORKFLOW + "&page=" + i + "&projects=" + projectId).content;
            
            for each (var resource in pageResources) {
                var deleteRequest = aa.delete("/deployment/api/deployments/" + resource.deploymentId);
                deleteRequests.push(deleteRequest.id);
            }
        }
    }
    
    return deleteRequests;
}

/**
 * 리소스 ID로 프로젝트 찾기
 */
function findProjectByResourceId(projects, resourceId) {
    for each (var project in projects) {
        if (project.properties.selfId === resourceId) {
            return project;
        }
    }
    throw "Project not found for resource ID: " + resourceId;
}

/**
 * 일반 리소스 처리
 */
function processGenericResources(resources) {
    var deleteRequests = [];
    
    for each (var resourceId in resources) {
        try {
            var resource = aa.get("/deployment/api/resources/" + resourceId);
            var deleteRequest = aa.delete("/deployment/api/deployments/" + resource.deploymentId);
            deleteRequests.push(deleteRequest.id);
        } catch (error) {
            System.error("Failed to process generic resource " + resourceId + ": " + error);
            throw error;
        }
    }
    
    return deleteRequests;
}

/**
 * 모든 삭제 요청 완료 대기
 */
function waitForAllRequestsToComplete(requestIds) {
    if (!requestIds || requestIds.length === 0) {
        return;
    }
    
    var attempts = 0;
    var allSuccessful = false;
    
    while (!allSuccessful && attempts < POLLING_CONFIG.MAX_ATTEMPTS) {
        allSuccessful = true;
        var statuses = [];
        
        for (var i = 0; i < requestIds.length; i++) {
            var requestId = requestIds[i];
            var result = aa.get("/deployment/api/requests/" + requestId);
            statuses.push(result.status);
            
            if (result.status === "FAILED") {
                throw "Request failed: " + result.details;
            }
            
            if (result.status !== "SUCCESSFUL") {
                allSuccessful = false;
            }
        }
        
        if (!allSuccessful) {
            attempts++;
            System.log("Waiting for requests to complete... Attempt " + attempts + "/" + POLLING_CONFIG.MAX_ATTEMPTS);
            System.sleep(POLLING_CONFIG.SLEEP_INTERVAL);
        }
    }
    
    if (!allSuccessful) {
        throw "Timeout waiting for deletion requests to complete after " + POLLING_CONFIG.MAX_ATTEMPTS + " attempts";
    }
}
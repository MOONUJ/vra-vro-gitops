function waitForRequestCompletion(requestId, aa, resourceId) {
    var requestSuccess = false;
    var retryCount = 0;
    var maxRetries = 15;
    
    System.log("Waiting for request completion: " + requestId);
    
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
            
            if (targetAction && targetAction.status === "SUCCESSFUL") {
                requestSuccess = true;
                System.log("Request completed successfully: " + requestId);
                return targetAction.name + " - " + requestId + " Successful";
            }
            
            System.log("Request " + requestId + " not completed yet. Retry count: " + (retryCount + 1) + "/" + maxRetries);
            System.sleep(10000);
            retryCount++;
            
        } catch (error) {
            System.error("Error checking request status: " + error.message);
            throw error;
        }
    }
    
    throw new Error("Request timeout: " + requestId + " exceeded maximum retries (" + maxRetries + ")");
}

System.log("========== Disk Management Workflow Started ==========");
System.log("Resource ID: " + resourceId);

var aa = System.getModule("com.gvp").AaManager(true);

System.log("Fetching machine resource information...");
var machine = aa.get("/deployment/api/resources/" + resourceId);
var addDiskId = "Cloud.vSphere.Machine.Add.Disk";
var resizeDiskId = "Cloud.vSphere.Machine.Resize.Compute.Disk";
var resizeBootDiskId = "Cloud.vSphere.Machine.Compute.Disk.Resize";
var removeDiskId = "Cloud.vSphere.Machine.Remove.Disk";

// machine.content.properties.storage.disks로 변경 필요할 수 있음
var disks = machine.properties.storage.disks.filter(function(item) { 
    return item.type == "HDD";
});

System.log("Current disk count (HDD only): " + disks.length);

var asisDiskInfos = [];
for each(var disk in disks) {
    if(disk["bootOrder"]) {
        asisDiskInfos.push({
            name: disk.name,
            size: disk.capacityGb,
            bootDisk: true
        });
        System.log("ASIS Disk (Boot): " + disk.name + " - " + disk.capacityGb + "GB");
    } else {
        asisDiskInfos.push({
            name: disk.name,
            size: disk.capacityGb,
            bootDisk: false
        });
        System.log("ASIS Disk: " + disk.name + " - " + disk.capacityGb + "GB");
    }
}

System.log("========== Target Disk Configuration ==========");
for each(var tobeDisk in diskProperties) {
    System.log("TOBE Disk: " + tobeDisk.name + " - " + tobeDisk.size + "GB (Boot: " + tobeDisk.bootDisk + ")");
}

// 변경 유형 구분
var toAdd = [];      // 추가할 디스크
var toResize = [];   // 크기 변경할 디스크
var toRemove = [];   // 삭제할 디스크

System.log("========== Processing Disk Changes ==========");

// 1. diskProperties(TOBE)를 순회하면서 추가 또는 확장 확인
for each(var tobeDisk in diskProperties) {
    var asisDisk = asisDiskInfos.filter(function(item) {
        return item.name === tobeDisk.name;
    })[0];
    
    if (!asisDisk) {
        // ASIS에 없으면 -> 추가
        System.log("Adding new disk: " + tobeDisk.name + " (" + tobeDisk.size + "GB)");
        
        var request = aa.post("/deployment/api/resources/" + resourceId + "/requests", {
            "actionId": addDiskId,
            "inputs": {
                "name": tobeDisk.name,
                "capacityGb": tobeDisk.size
            }
        });
        
        System.log("Add disk request submitted: " + request.id);
        var result = waitForRequestCompletion(request.id, aa, resourceId);
        System.log(result);

        toAdd.push({
            name: tobeDisk.name,
            size: tobeDisk.size,
            bootDisk: tobeDisk.bootDisk,
            action: addDiskId
        });
        
        // 리소스 갱신
        machine = aa.get("/deployment/api/resources/" + resourceId);
        disks = machine.properties.storage.disks.filter(function(item) { 
            return item.type == "HDD";
        });
        System.log("Machine resource refreshed after disk addition");
        
    } else if (asisDisk.size < tobeDisk.size) {
        // ASIS보다 크기가 크면 -> 확장
        System.log("Resizing disk: " + tobeDisk.name + " from " + asisDisk.size + "GB to " + tobeDisk.size + "GB");
        
        var selectDisk = disks.filter(function(item){return item.name == tobeDisk.name})[0].resourceLink;
        var request = aa.post("/deployment/api/resources/" + resourceId + "/requests", {
            "actionId": tobeDisk.bootDisk ? resizeBootDiskId : resizeDiskId,
            "inputs": {
                "selectDisk": selectDisk,
                "capacityGb": tobeDisk.size
            }
        });
        
        System.log("Resize disk request submitted: " + request.id + " (Action: " + (tobeDisk.bootDisk ? "Boot Disk Resize" : "Data Disk Resize") + ")");
        var result = waitForRequestCompletion(request.id, aa, resourceId);
        System.log(result);
        
        toResize.push({
            name: tobeDisk.name,
            oldSize: asisDisk.size,
            newSize: tobeDisk.size,
            bootDisk: tobeDisk.bootDisk
        });
    } else {
        System.log("No change needed for disk: " + tobeDisk.name + " (" + tobeDisk.size + "GB)");
    }
}

// 2. asisDiskInfos(ASIS)를 순회하면서 삭제 확인
System.log("========== Checking for Disks to Remove ==========");

for each(var asisDisk in asisDiskInfos) {
    var tobeDisk = diskProperties.filter(function(item) {
        return item.name === asisDisk.name;
    })[0];
    
    if (!tobeDisk) {
        // 부팅 디스크는 삭제 불가
        if (asisDisk.bootDisk) {
            System.warn("Cannot remove boot disk: " + asisDisk.name + ". Skipping.");
            continue;
        }
        
        // TOBE에 없으면 -> 삭제
        System.log("Removing disk: " + asisDisk.name + " (" + asisDisk.size + "GB)");
        
        var selectDisk = disks.filter(function(item){return item.name == asisDisk.name})[0].resourceLink;
        var request = aa.post("/deployment/api/resources/" + resourceId + "/requests", {
            "actionId": removeDiskId,
            "inputs": {
                "diskId": selectDisk,
            }
        });
        
        System.log("Remove disk request submitted: " + request.id);
        var result = waitForRequestCompletion(request.id, aa, resourceId);
        System.log(result);
        
        toRemove.push({
            name: asisDisk.name,
            size: asisDisk.size
        });
        
        // 리소스 갱신
        machine = aa.get("/deployment/api/resources/" + resourceId);
        disks = machine.properties.storage.disks.filter(function(item) { 
            return item.type == "HDD";
        });
        System.log("Machine resource refreshed after disk removal");
    }
}

System.log("========== Disk Management Summary ==========");
System.log("Disks Added: " + toAdd.length);
System.log("Disks Resized: " + toResize.length);
System.log("Disks Removed: " + toRemove.length);
System.log("========== Workflow Completed Successfully ==========");
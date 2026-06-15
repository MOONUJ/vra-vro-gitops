if(!clusters){ return null }

var result = [];
for each(var computeName in clusters){
    var cluster = VcPlugin.getAllClusterComputeResources(null, "xpath:name='" + computeName + "'")[0];
    
    // cluster 존재 검증
    if (!cluster || !cluster.host) {
        System.log("Cluster or hosts not found for: " + computeName);
        continue;
    }

    var vim = cluster.sdkConnection;
    var perf = vim.PerformanceManager;
    var availableMetrics = perf.queryAvailablePerfMetric(cluster);
    if (!availableMetrics || availableMetrics.length === 0) {
        throw "No performance metrics available for cluster: " + cluster.name
        continue;
    }
    var gpuMetric = availableMetrics.filter(function(item) { return (item.counterId == 284 || item.counterId == 280); }); 
    if( gpuMetric === 0){
        throw "Cannot Found GPU in " + cluster.name
    }
    
    var hosts = cluster.host;
    for (var h in hosts){
        var configManager = hosts[h].configManager;
        if (!configManager || !configManager.graphicsManager) {
            System.log("Graphics manager not available for host: " + hosts[h].name);
            continue;
        }
        
        var gpuManager = configManager.graphicsManager;
        var vgpuProfileInfo = null;
        try {
            vgpuProfileInfo = hosts[h].config.sharedGpuCapabilities //.filter( function(item){ return item.vgpu.split("-").length == 2;}); //gpuManager.retrieveVgpuProfileInfo();
            if (!vgpuProfileInfo) {
                System.log("No vGPU profile info available for host: " + hosts[h].name);
                continue;
            }
        } catch (gpuError) {
            System.log("Failed to retrieve GPU profile info for host " + hosts[h].name + ": " + gpuError);
            continue;
        }
        
        // 지정된 GPU 크기에 맞는 프로필 필터링
        var vgpuProfile = vgpuProfileInfo
        

        
        // 매칭되는 프로필이 없으면 다음 호스트로
        if (vgpuProfile.length === 0) {
            continue;
        }
        
        // 수정: vgpuProfile 배열 사용
        for(var g in vgpuProfile){
            var profileName = vgpuProfile[g].vgpu;
            //var profileName = vgpuProfile[g].profileName;
            if(result.indexOf(profileName) === -1 ){
                result.push(profileName);
            }
        }
    }
}


// 수정: 안전한 반환
return result.length > 0 ? result : null;
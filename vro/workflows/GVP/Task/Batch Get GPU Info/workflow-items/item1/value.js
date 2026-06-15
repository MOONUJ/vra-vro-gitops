var vcenters = [];
var vcsaSdks = VcPlugin.allSdkConnections;
var currentTime = System.getCurrentTime();
var dayBeforeTime = currentTime - (24 * 60 * 60 * 1000);
var startTime = new Date(dayBeforeTime);
var endTime = new Date(currentTime - (10 * 60 * 1000));



for(var i in vcsaSdks){
    try {
        var format = {};
        var vim = vcsaSdks[i];
        
        // vCenter 연결 상태 확인
        if (!vim || !vim.PerformanceManager) {
            System.log("vCenter SDK connection invalid for: " + (vim ? vim.id : "unknown"));
            continue;
        }
        
        var perf = vim.PerformanceManager;
        format.vcenter = {};
        format.vcenter.name = vim.id;
        format.vcenter.timestamp = !time ? String(endTime) : time;
        format.vcenter.clusters = [];
        
        var clusters = vim.getAllClusterComputeResources();
        if (!clusters) {
            System.log("No clusters found for vCenter: " + vim.id);
            continue;
        }
        
        for(var c in clusters){
            try {
                // 성능 메트릭 가용성 확인
                var availableMetrics = perf.queryAvailablePerfMetric(clusters[c]);
                if (!availableMetrics || availableMetrics.length === 0) {
                    System.log("No performance metrics available for cluster: " + clusters[c].name);
                    continue;
                }
                
                var query = new Array;
                query[0] = new VcPerfQuerySpec;
                query[0].entity = clusters[c];
                query[0].startTime = startTime;
                query[0].endTime = endTime;
                query[0].intervalId = 300;
                query[0].metricId = availableMetrics.filter(function(item) {
                    return (item.counterId == 284 || item.counterId == 280); 
                }); 
                
                // GPU 메트릭이 없는 경우 스킵
                if (query[0].metricId.length === 0) {
                    System.log("No GPU metrics found for cluster: " + clusters[c].name);
                    continue;
                }
                
                var metricSeries = null;
                try {
                    var perfResult = perf.queryPerf(query);
                    metricSeries = (perfResult && perfResult.length > 0) ? perfResult[0].value : null;
                } catch (perfError) {
                    System.log("Performance query failed for cluster " + clusters[c].name + ": " + perfError);
                    continue;
                }

                if(metricSeries && metricSeries.some(function(item){return item && item.value !== null;})){
                    var totalGpuMemSeries = metricSeries.filter(function(item){return item.id.counterId == 284});
                    var usedGpuMemSeries = metricSeries.filter(function(item){return item.id.counterId == 280});
                    
                    // 메트릭 데이터 검증
                    if (totalGpuMemSeries.length === 0 || usedGpuMemSeries.length === 0) {
                        System.log("Incomplete GPU metrics for cluster: " + clusters[c].name);
                        continue;
                    }
                    
                    var totalGpuMem = totalGpuMemSeries[0].value;
                    var usedGpuMem = usedGpuMemSeries[0].value;
                    
                    if (!totalGpuMem || !usedGpuMem || totalGpuMem.length === 0 || usedGpuMem.length === 0) {
                        System.log("No GPU memory data available for cluster: " + clusters[c].name);
                        continue;
                    }
                    
                    var clusterFormat = {};
                    clusterFormat.name = clusters[c].name;
                    clusterFormat.id = clusters[c].id;
                    clusterFormat.sdk_id = clusters[c].sdkId;
                    clusterFormat.total_gpu_memory_gb = 0;
                    clusterFormat.used_gpu_memory_gb = Math.round(usedGpuMem[0] /1024 / 1024) || 0;
                    clusterFormat.total_gpus = 0;
                    clusterFormat.total_hosts = clusters[c].host ? clusters[c].host.length : 0;
                    clusterFormat.hosts_with_gpu = 0;
                    clusterFormat.total_vms_with_gpu = 0;
                    clusterFormat.hosts = [];

                    var hostList = clusters[c].host;
                    if (hostList) {
                        for (var h in hostList){
                            try {
                                if(hostList[h].state == "connected"){
                                    var configManager = hostList[h].configManager;
                                    if (!configManager || !configManager.graphicsManager) {
                                        System.log("Graphics manager not available for host: " + hostList[h].name);
                                        continue;
                                    }
                                    
                                    var gpuManager = configManager.graphicsManager;
                                    var vgpuProfileInfo = null;
                                    
                                    try {
                                        vgpuProfileInfo = gpuManager.retrieveVgpuProfileInfo();
                                    } catch (gpuError) {
                                        System.log("Failed to retrieve GPU profile info for host " + hostList[h].name + ": " + gpuError);
                                        continue;
                                    }
                                    
                                    if(vgpuProfileInfo != null) {
                                        var gpuDevices = hostList[h].config.graphicsInfo;
                                        if (!gpuDevices || gpuDevices.length === 0) {
                                            continue;
                                        }
                                        
                                        var hostFormat = {};
                                        hostFormat.name = hostList[h].name;
                                        hostFormat.id = hostList[h].id;
                                        hostFormat.sdk_id = hostList[h].sdkId;
                                        hostFormat.total_gpus = gpuDevices.length;
                                        hostFormat.gpu_profile_types = gpuManager.sharedPassthruGpuTypes || [];
                                        hostFormat.total_gpu_memory_gb = 0; // 변수명 일관성 유지
                                        hostFormat.allocated_gpu_memory_gb = 0;
                                        hostFormat.total_vms = hostList[h].vm ? hostList[h].vm.length : 0;
                                        hostFormat.vms_with_gpu = 0;
                                        hostFormat.gpu_devices = [];
                                        
                                        for(var g in gpuDevices){
                                            try {
                                                var gpuFormat = {};
                                                var vms = gpuDevices[g].vm;
                                                gpuFormat.name = gpuDevices[g].deviceName || "Unknown GPU";
                                                gpuFormat.pci_id = gpuDevices[g].pciId || "Unknown";
                                                gpuFormat.memory_size_gb = gpuDevices[g].memorySizeInKB ? 
                                                    Math.round((gpuDevices[g].memorySizeInKB / 1024) / 1024) : 0;
                                                gpuFormat.virtual_machines = [];

                                                if(vms && vms.length > 0){
                                                    for(var v in vms ){
                                                        try {
                                                            var vm = VcPlugin.toManagedObject(vim, vms[v]);
                                                            if (!vm || !vm.config || !vm.config.hardware) {
                                                                continue;
                                                            }
                                                            
                                                            var vmFormat = {};
                                                            var devices = vm.config.hardware.device;
                                                            var vgpuProfile = "Unknown";
                                                            
                                                            if (devices) {
                                                                for (var d in devices) {
                                                                    if (devices[d] instanceof VcVirtualPCIPassthrough && 
                                                                        devices[d].backing && 
                                                                        devices[d].backing.vgpu) {
                                                                        vgpuProfile = devices[d].backing.vgpu;
                                                                        break;
                                                                    }
                                                                }
                                                            }
                                                            
                                                            vmFormat.name = vm.name;
                                                            vmFormat.id = vm.id;
                                                            vmFormat.sdk_id = vm.sdkId;
                                                            vmFormat.power_state = vm.runtime && vm.runtime.powerState ? 
                                                                vm.runtime.powerState.value : "unknown";
                                                            vmFormat.gpu_allocation = {};
                                                            vmFormat.gpu_allocation.vgpu_profile = vgpuProfile;
                                                            
                                                            var match = vgpuProfile.match(/-(\d+)/);
                                                            vmFormat.gpu_allocation.allocated_memory_gb = match ? 
                                                                parseInt(match[1], 10) : null;
                                                            
                                                            gpuFormat.virtual_machines.push(vmFormat);
                                                            hostFormat.allocated_gpu_memory_gb += vmFormat.gpu_allocation.allocated_memory_gb;
                                                        } catch (vmError) {
                                                            System.log("Error processing VM: " + vmError);
                                                        }
                                                    }
                                                }

                                                hostFormat.total_gpu_memory_gb += gpuFormat.memory_size_gb;
                                                hostFormat.vms_with_gpu += gpuFormat.virtual_machines.length;
                                                clusterFormat.total_vms_with_gpu += gpuFormat.virtual_machines.length;
                                                hostFormat.gpu_devices.push(gpuFormat);
                                            } catch (gpuDeviceError) {
                                                System.log("Error processing GPU device: " + gpuDeviceError);
                                            }
                                        }

                                        clusterFormat.total_gpus += gpuDevices.length;
                                        clusterFormat.total_gpu_memory_gb += hostFormat.total_gpu_memory_gb;
                                        clusterFormat.hosts.push(hostFormat);
                                    }
                                }
                            } catch (hostError) {
                                System.log("Error processing host " + (hostList[h] ? hostList[h].name : "unknown") + ": " + hostError);
                            }
                        }
                    }
                    
                    clusterFormat.hosts_with_gpu = clusterFormat.hosts.length;
                    format.vcenter.clusters.push(clusterFormat);
                }
            } catch (clusterError) {
                System.log("Error processing cluster " + (clusters[c] ? clusters[c].name : "unknown") + ": " + clusterError);
            }
        }
        
        if(format.vcenter.clusters.length > 0){
            vcenters.push(format);
        }
    } catch (vcenterError) {
        System.log("Error processing vCenter " + (vim ? vim.id : "unknown") + ": " + vcenterError);
    }
}

output = vcenters;
var aa = System.getModule("com.gvp").AaManager(true);

var machines = aa.get("/iaas/api/machines").content.filter(function (item){ return item['deploymentId']});
for (var machine of machines ){
    var compute = aa.getUerp("/resources/compute/" + machine.id);
    var vm = VcPlugin.getAllVirtualMachines(null, "xpath:instanceId='"+ machine.customProperties.instanceUUID +"'")[0]
    compute.customProperties.createDate = vm.config.createDate;
    compute.customProperties.cloudZoneId = compute.customProperties["__vmw:provisioning:cloudZone"];
    aa.patchUerp("/resources/compute/" + machine.id, compute);
    System.log(compute.name + " Patch Complete!")
    
}
return machines
aa.getUerp("/resources/compute")
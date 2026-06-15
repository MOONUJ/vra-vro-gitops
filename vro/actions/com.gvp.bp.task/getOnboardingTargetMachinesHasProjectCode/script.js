var aa = System.getModule("com.gvp").AaManager(true);
var noneManagedVms = aa.get("/iaas/api/machines").content.filter(function(item){ return !item['owner'] });
var result = [];
for each(var noneManagedVm in noneManagedVms){
    var vm = VcPlugin.getAllVirtualMachines(null, "xpath:name='" + noneManagedVm.name + "'")[0];
    var project = aa.get("/iaas/api/projects?$filter=name eq '" + vm.parent.name + "'").content;
    if(project.length > 0 ){
        result.push({
            label: noneManagedVm.name,
            value: noneManagedVm.id
        })
    } else {
        System.log(noneManagedVm.name + " VM Folder Name's Project is not Found"); 
    }
}

return result;


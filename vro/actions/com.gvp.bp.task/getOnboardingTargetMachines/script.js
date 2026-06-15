var aa = System.getModule("com.gvp").AaManager(true);
var noneManagedVms = aa.get("/iaas/api/machines").content.filter(function(item){ return !item['owner'] });
var result = [];
for each(var noneManagedVm in noneManagedVms){
    result.push({
        label: noneManagedVm.name,
        value: noneManagedVm.id
    })
}

return result;


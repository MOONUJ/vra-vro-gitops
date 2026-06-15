var aa = System.getModule("com.gvp").AaManager(true);

var accounts = aa.get("/iaas/api/cloud-accounts-nsx-t").content;
var result = [];
for each(var account in accounts){
    result.push({
        label: account.name,
        value: account.id
    })
}

return result;
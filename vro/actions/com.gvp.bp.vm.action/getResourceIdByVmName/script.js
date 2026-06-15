if (!projectId || !vmName) {
    return null;
}

var aa = System.getModule("com.gvp").AaManager(true);
var filter = "projectId eq '" + projectId + "'";
var res = aa.get("/iaas/api/machines?$filter=" + filter);

if (!res || !res.content) {
    return null;
}

var machines = res.content;

for each (var machine in machines) {
    var reourcevmname = machine.customProperties.displayName || machine.name;
    if (reourcevmname && reourcevmname.toLowerCase() === vmName.toLowerCase()) {
        return machine.id; // resourceId 반환
    }
}

return null;
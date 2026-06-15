if (!projectId) { return []; }

var aa = System.getModule("com.gvp").AaManager(true);

var filter = "projectId eq '" + projectId + "'";
if (search && search.trim() !== "") {
    var s = search.trim().replace(/'/g, "''");
    filter += " and name eq '*" + s + "*'";
}

var machines = aa.get("/iaas/api/machines?$filter=" + filter).content;

var result = [];
for each (var machine in machines) {
    result.push({
        label: machine.customProperties.displayName || machine.name,
        value: machine.id
    });
}

return result;

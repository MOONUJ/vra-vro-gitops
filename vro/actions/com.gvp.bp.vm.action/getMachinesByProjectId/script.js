if(!projectId){ return null };

var aa = System.getModule("com.gvp").AaManager(true);
var machines = aa.get("/iaas/api/machines?$filter=projectId eq '" + projectId + "'").content;

var result = [];
for each(var machine in machines){
    result.push({
        label: machine.customProperties.displayName,
        value: machine.id
    });
}

return result;



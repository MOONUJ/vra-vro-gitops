var aa = System.getModule("com.gvp").AaManager(true);

var projects = aa.get("/iaas/api/projects").content;

var result = [];
for each(var project in projects.filter( function(item){ return item.name != "admin"})){
    result.push({
        label: project.description,
        value: project.id
    })
}

return result
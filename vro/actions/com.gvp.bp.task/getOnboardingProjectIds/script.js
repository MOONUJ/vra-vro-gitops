var aa = System.getModule("com.gvp").AaManager(true);

var projects = aa.get("/project-service/api/projects").content;
var result = [];
for each( var project in projects){
    result.push({
        label: project.description != '' || project.description != null?project.description:project.name,
        value: project.id
    })
}

return result;
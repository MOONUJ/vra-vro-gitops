var aa = System.getModule("com.gvp").AaManager(true);

var result = [];
var projects = aa.get("/project-service/api/projects").content;

for each(var pjt in projects){
    result.push({
        "label": pjt.name,
        "value": pjt.id
    })
}
return result;
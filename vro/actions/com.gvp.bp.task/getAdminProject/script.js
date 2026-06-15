var aa = System.getModule("com.gvp").AaManager(true);
var projects = aa.get("/iaas/api/projects?$filter=name eq 'admin'");

if(projects.content.length == 0){
    throw "cloud not find admin project";
} else {
    var adminProjectId = projects.content[0].id;
}

return adminProjectId
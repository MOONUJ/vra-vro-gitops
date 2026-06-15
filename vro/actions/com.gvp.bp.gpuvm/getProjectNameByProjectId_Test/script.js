if (!projectId) { return null;}

var aa = System.getModule("com.gvp").AaManager(true);
var project = aa.get("/iaas/api/projects/" + projectId);

if (project.name == "admin") {
    return null;
}

return project.name;
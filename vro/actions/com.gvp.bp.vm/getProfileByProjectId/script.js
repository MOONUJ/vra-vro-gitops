if (!projectId) { return null; }
var aa = System.getModule("com.gvp").AaManager(true);
var project = aa.get("/iaas/api/projects/" + projectId);
var profile = project.customProperties ? project.customProperties.profile : null;
return profile;
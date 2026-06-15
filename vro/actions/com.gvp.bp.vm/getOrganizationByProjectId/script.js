if (!projectId) { return null; }
var aa = System.getModule("com.gvp").AaManager(true);
var project = aa.get("/iaas/api/projects/" + projectId);
var organization = project.customProperties.organization ? project.customProperties.organization : null;
return organization;
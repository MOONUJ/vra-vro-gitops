if (!projectId) { return null;}

var aa = System.getModule("com.gvp").AaManager(true);
return aa.get("/iaas/api/projects/" + projectId).name;
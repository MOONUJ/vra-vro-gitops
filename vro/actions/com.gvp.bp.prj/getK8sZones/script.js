var aa = System.getModule("com.gvp").AaManager(true);

return aa.get("/cmx/api/resources/k8s-zones?expandTags=true").content;
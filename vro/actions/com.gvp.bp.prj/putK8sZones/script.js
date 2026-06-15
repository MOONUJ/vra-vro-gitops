var aa = System.getModule("com.gvp").AaManager(true);

return aa.put("/cmx/api/resources/k8s-zones/"+kzId+"/projects",[
    {
        "projectId": projectId
    }
]);
var aa = System.getModule("com.gvp").AaManager(true);

var kzs = aa.get("/cmx/api/resources/k8s-zones").content;

var result = [];
for each(var kz in kzs){
    kzProjects = kz.projects;
    for each( var kzProject in kzProjects){
        if(kzProject.projectId == projectId){
            kzProjects.pop(kzProject);
            result.push(aa.put("/cmx/api/resources/k8s-zones/"+kz.id+"/projects",kzProjects));
        }
    }
}
return result;
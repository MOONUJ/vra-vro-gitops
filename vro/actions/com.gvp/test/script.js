var aa = System.getModule("com.gvp").AaManager(true);
var id = "f9bdd5d9-0a5e-3f94-8f81-610fba6ae332"
var compute = aa.getUerp("/resources/compute/" + id);
compute.customProperties.gpuSize = "94";
return aa.patchUerp("/resources/compute/" + id, compute);

var aa = System.getModule("com.gvp").AaManager(true);
var context = System.getContext();
var resourceProperties = context.getParameter("__metadata_resourceProperties");

var compute = aa.getUerp("/resources/compute/" + resourceId );
if(compute.customProperties.note){
    System.log("ASIS customProperties.note = " + compute.customProperties.note );
} else {
    System.log("ASIA customProperties.note is null")
}
System.log("TOBE customProperties.note = " + note);
compute.customProperties.note = note;
aa.patchUerp("/resources/compute/" + resourceId, compute);

var vm = VcPlugin.getAllVirtualMachines(null, "xpath:instanceId='" + compute.customProperties.instanceUUID + "'")[0];
var vmSpec = new VcVirtualMachineConfigSpec();
vmSpec.annotation = note;
var vmTask = vm.reconfigVM_Task(vmSpec);
System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(vmTask, false, 1);

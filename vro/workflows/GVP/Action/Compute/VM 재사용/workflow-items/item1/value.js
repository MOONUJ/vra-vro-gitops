var aa = System.getModule("com.gvp").AaManager(true);
var resourcesLink = "/deployment/api/deployments/" + deploymentId + "/resources/" + resourceId;
var requestsLink = "/deployment/api/resources/" + resourceId + "/requests";
var data = {
  actionId: "Cloud.vSphere.Machine.PowerOn",
  reason: "VM 재사용",
  inputs: {}
};
var computeLink = aa.get(resourcesLink);
var requests = aa.post(requestsLink, data);
var endpointId = computeLink.properties.endpointId
var vmName = computeLink.properties.name;
var folderName = computeLink.properties.folderName;
var endpointLink = "/resources/endpoints/" + endpointId;
var endpointName = aa.getUerp(endpointLink).endpointProperties.hostName.split(".")[0];
var vcConf = System.getModule("com.gvp").ConfManager().load("BVP/Endpoint/" + endpointName);
var vmDirectoryMoveinvCenter = System.getModule("com.gvp").vmDirectoryMoveinvCenter;

vmDirectoryMoveinvCenter(vcConf.hostname, vcConf.username, vcConf.password, vmName, folderName);
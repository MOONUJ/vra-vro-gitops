var aa = System.getModule("com.gvp").AaManager(true);

var machine = aa.get("/iaas/api/machines/" + resourceId);
var computeName = machine.name;
var vm = VcPlugin.getAllVirtualMachines(null, "xpath:name='" + computeName + "'")[0];
var network = aa.get(segment);
var networkName = network.name;
var networkAccountId = network.cloudAccountIds[0];
var cloudAccount = aa.get("/iaas/api/cloud-accounts/" + networkAccountId);

if(cloudAccount.cloudAccountType == "nsxt") {
    var nsxHostname = cloudAccount.cloudAccountProperties.hostName.split(".")[0];
    var nsx = System.getModule("com.gvp").NsxManager(nsxHostname);
    var nsxSegment = nsx.get("/policy/api/v1/infra/segments/" + network.externalId);
    networkName = nsxSegment['display_name'];
} else {
    throw "This Network is not belong in nsx"
}


// network name encode
if(networkName.indexOf("/") > -1){
    var encodeString = encodeURIComponent("/").toLocaleLowerCase();
    var networkName = networkName.replace("/", encodeString);
}
var portGroup = VcPlugin.getAllNetworks(null, "xpath:name='" + networkName + "'")[0];
var vdsUuid = portGroup.config.distributedVirtualSwitch.uuid;
var portGroupId = portGroup.id;
var segTypeTagValue = network.tags.filter( function(item){ return item.key == "segType"})[0].value;
var additionalNetworkId = System.nextUUID();

// IP reserved
if(segTypeTagValue == "overlay"){
    if(segmentAddress == "*"){
        var ipRange = aa.get(segment + "/network-ip-ranges?apiVersion=2021-07-15").content.filter(function(item){return item.numberOfAvailableIPs > 0})[0];
        var allocateIpTaskInfo = aa.post("/iaas/api/network-ip-ranges/" + ipRange.id + "/ip-addresses/allocate?apiVersion=2021-07-15", {
            numberOfIps: 1
        });
        System.sleep(1000);
        var allocateIpTask = aa.get(allocateIpTaskInfo.selfLink);
        var allocateIp = aa.get(allocateIpTask.resources[0] + "?apiVersion=2021-07-15");
        var allocateIpAddress = allocateIp.ipAddress;
    } else {
        var ipRange = aa.get(segment + "/network-ip-ranges?apiVersion=2021-07-15").content.filter( function(item){
            var conv = System.getModule("com.gvp").Converter();
            var startIpNumeric = conv.ip.getNumeric(item.startIPAddress);
            var endIpNumeric = conv.ip.getNumeric(item.endIPAddress);
            var inputAddress = conv.ip.getNumeric(segmentAddress);
            return inputAddress >= startIpNumeric && inputAddress <= endIpNumeric;
        })[0]
        var allocateIpTaskInfo = aa.post("/iaas/api/network-ip-ranges/" + ipRange.id + "/ip-addresses/allocate?apiVersion=2021-07-15",{
            ipAddresses: [segmentAddress]
        });
        var allocateIpAddress = segmentAddress;
    }
} else if(segTypeTagValue == "bridge"){
    var ipRange = aa.get(segment + "/network-ip-ranges?apiVersion=2021-07-15").content[0];
    var allocateIpAddress = "none";
}




// ----------reconfigVM_Task----------
var spec = new VcVirtualMachineConfigSpec();
var deviceChange = new Array();
deviceChange[0] = new VcVirtualDeviceConfigSpec();
deviceChange[0].device = new VcVirtualVmxnet3();
deviceChange[0].device.macAddress = '';
deviceChange[0].device.resourceAllocation = new VcVirtualEthernetCardResourceAllocation();
deviceChange[0].device.resourceAllocation.limit = -1;
deviceChange[0].device.resourceAllocation.reservation = 0;
deviceChange[0].device.resourceAllocation.share = new VcSharesInfo();
deviceChange[0].device.resourceAllocation.share.shares = 50;
deviceChange[0].device.resourceAllocation.share.level = VcSharesLevel.normal;
deviceChange[0].device.connectable = new VcVirtualDeviceConnectInfo();
deviceChange[0].device.connectable.connected = true;
deviceChange[0].device.connectable.allowGuestControl = false;
deviceChange[0].device.connectable.startConnected = true;
deviceChange[0].device.backing = new VcVirtualEthernetCardDistributedVirtualPortBackingInfo();
deviceChange[0].device.backing.port = new VcDistributedVirtualSwitchPortConnection();
deviceChange[0].device.backing.port.switchUuid = vdsUuid;
deviceChange[0].device.backing.port.portgroupKey = portGroupId;
deviceChange[0].device.addressType = 'generated';
deviceChange[0].device.uptv2Enabled = false;
deviceChange[0].device.wakeOnLanEnabled = true;
deviceChange[0].device.deviceInfo = new VcDescription();
deviceChange[0].device.deviceInfo.summary = '새 네트워크';
deviceChange[0].device.deviceInfo.label = '새 네트워크';
deviceChange[0].device.key = -102;
deviceChange[0].operation = VcVirtualDeviceConfigSpecOperation.add;
spec.deviceChange = deviceChange;
spec.virtualNuma = new VcVirtualMachineVirtualNuma();
var task = vm.reconfigVM_Task(spec);  
var tryInt = 0;
while(task.state!="success"){
    var task = task;
    tryInt++
    if(tryInt > 30){
        throw "VM Reconfig TimeOut!"
    }
    System.sleep(1000);
}

//// nsx dhcp config create
if(segTypeTagValue == "overlay"){
    var nsx = System.getModule("com.gvp").NsxManager(aa.get("/iaas/api/cloud-accounts/" + network.cloudAccountIds[0]).cloudAccountProperties.hostName.split(".")[0]);
    var subnet = aa.get("/iaas/api/fabric-networks?$filter=externalId eq '" + network.externalId + "'").content[0];
    var devices = vm.config.hardware.device.filter( function(item){ return item instanceof VcVirtualVmxnet3});
    var device = devices.sort(function(a,b){ return a.key < b.key ? -1 : 1; })[devices.length - 1];
    var macAddress = device.macAddress;
    nsx.put("/policy/api/v1" + subnet.customProperties.path + "/dhcp-static-binding-configs/" + additionalNetworkId, {
        resource_type: "DhcpV4StaticBindingConfig",
        display_name: computeName + "-" + macAddress,
        ip_address: allocateIpAddress,
        mac_address: macAddress,
    });
 
} else if(segTypeTagValue == "bridge"){
    var subnet = aa.get("/iaas/api/fabric-networks?$filter=externalId eq '" + network.externalId + "'").content[0];
}


// machine update
var networksInfo = machine.customProperties.additionalNetworks?JSON.parse(machine.customProperties.additionalNetworks):[];
//var deviceIndex = networksInfo.length + machine._links.network-interfaces.hrefs.length - 1;

var addNetworksInfo = {
    network: segment,
    address: allocateIpAddress,
    //gateway: "",
    //deviceIndex: deviceIndex,
    primaryAddress: false,
    tags: [{
        key: "segType",
        value: segTypeTagValue
    }],
    //dns: [],
    id: additionalNetworkId,
    ipRangelink: "/iaas/api/network-ip-ranges/" + ipRange.id,
    segPath: subnet.customProperties.path
};

networksInfo.push(addNetworksInfo);

aa.patch("/iaas/api/machines/" + resourceId, {
    customProperties: {
        additionalNetworks: JSON.stringify(networksInfo)
    }
})

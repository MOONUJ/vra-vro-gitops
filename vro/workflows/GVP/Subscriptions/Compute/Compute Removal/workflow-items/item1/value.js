var computeId = inputProperties.resourceIds[0];
if (computeId && computeId != "N/A" && inputProperties.customProperties.profile) {
    var aa = System.getModule("com.gvp").AaManager(true);
    var projectId = inputProperties.projectId;
    var computeLink = "/resources/compute/" + computeId;
    var compute = aa.getUerp(computeLink);
    var additionalNetworks = compute.customProperties.additionalNetworks?JSON.parse(compute.customProperties.additionalNetworks):[];
    var nsx = null;
    for each(var intfLink in compute.networkInterfaceLinks) {
        var interfaceId = intfLink.split("/network-interfaces/")[1];
        var interface = aa.getUerp(intfLink);
        if (interface.subnetLink && interface.tagLinks) {
            var network = aa.get("/iaas/api/networks?$filter=name eq '" + interface.name + "'").content[0];
            var fabricNetwork = aa.get("/iaas/api/fabric-networks?$filter=externalId eq '" + network.externalId + "'").content[0];
            
            var subnet = aa.getUerp(interface.subnetLink);
            var tag = aa.getUerp(interface.tagLinks[0]);

            //if (!nsx) { nsx = System.getModule("com.gvp").NsxManager(aa.getUerp(subnet.endpointLink).endpointProperties.hostName.split(".")[0]);}
            if (!nsx) { nsx = System.getModule("com.gvp").NsxManager(aa.get(network._links["cloud-accounts"].hrefs[0]).cloudAccountProperties.hostName.split(".")[0]); }
            if(tag.value != "bridge") { 
                nsx.delete("/policy/api/v1" + fabricNetwork.customProperties.path + "/dhcp-static-binding-configs/" + interfaceId);
                if(compute.customProperties.dynamicNetworks && interface.address){
                    var subnetRange = aa.getUerp("/provisioning/mgmt/subnet-range?$filter=subnetLink eq '" + subnet.documentSelfLink + "'");
                    var ipRangeId = subnetRange.documentLinks[0].split("/subnet-ranges/")[1];
                    aa.post("/iaas/api/network-ip-ranges/" + ipRangeId + "/ip-addresses/release?apiVersion=2021-07-15",{ipAddresses: [interface.address]});
                } else {
                    System.log("Cannot Found dynamicNetworks Or Interface Address")
                }
            }

        }
    }
    for each(var intfLink in additionalNetworks){
        var network = aa.get(intfLink.network);
        var subnet = aa.get("/iaas/api/fabric-networks?$filter=externalId eq '" + network.externalId + "'").content[0];
        if(!nsx) { nsx = System.getModule("com.gvp").NsxManager(aa.get("/iaas/api/cloud-accounts/" + network.cloudAccountIds[0]).cloudAccountProperties.hostName.split(".")[0]);}
        var tag = intfLink.tags[0];
        if(tag.value != "bridge"){ 
            nsx.delete("/policy/api/v1" + intfLink.segPath + "/dhcp-static-binding-configs/" + intfLink.id);
            aa.post(intfLink.ipRangelink + "/ip-addresses/release?apiVersion=2021-07-15",{
                ipAddresses: [intfLink.address]
            });
        }

    }
}

// GPU License release 를 위해 VM GuestOS shutdown 진행
if(compute.customProperties["gpuModel"]) {
    var computeName = compute.name;
    vm = VcPlugin.getAllVirtualMachines(null, "xpath:name='" + computeName + "'")[0];
    if(vm.state == "poweredOn"){
        isGpu = true;
    } else {
        isGpu = false;
    }
    
}
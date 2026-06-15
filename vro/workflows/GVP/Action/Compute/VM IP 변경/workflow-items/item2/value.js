if (!resourceId) { throw "resourceId cannot be null"; }
if (!interfaceLink) { throw "interfaceLink cannot be null"; }
if (!newIpAddress) { throw "newIpAddress cannot be null"; }
if (!releaseMode) { throw "releaseMode cannot be null"; }
//if (!adminUsername) { throw "adminUsername cannot be null"; }
//if (!adminPassword) { throw "adminPassword cannot be null"; }

if( interfaceLink.indexOf("/network-interfaces/") > -1){
    var interfaceId = interfaceLink.split("/network-interfaces/")[1];
    var intfLink = "/resources/network-interfaces/" + interfaceId;
    var properties = System.getContext().getParameter("__metadata_resourceProperties");
    var context = System.getContext();
    var conv = System.getModule("com.gvp").Converter();
    var aa = System.getModule("com.gvp").AaManager(true);
    var computeLink = "/resources/compute/" + resourceId;
    var compute = aa.getUerp(computeLink);
    var projectId = compute.customProperties.project;
    var computeDesc = aa.getUerp(compute.descriptionLink);    
    var interface = aa.getUerp(intfLink);
    var ipAddress = interface.address;
    var subnet = aa.getUerp(interface.subnetLink);
    var subnetRange = aa.getUerp("/provisioning/mgmt/subnet-range?$filter=subnetLink eq '" + subnet.documentSelfLink + "'");
    var subnetRangeLink = subnetRange.documents[subnetRange.documentLinks[0]].documentSelfLink;
    var ipRangeId = subnetRangeLink.split("/subnet-ranges/")[1];
    var subnetIps = aa.getUerp("/resources/ip-addresses?expand&$filter=subnetRangeLink eq '" + subnetRangeLink + "'");
    var curIpDocument = null;
    var newIpDocument = null;
    var tag = aa.getUerp(interface.tagLinks[0]);

    if(tag.value != "bridge"){
        for each(var link in subnetIps.documentLinks) {
            var document = subnetIps.documents[link];
            if (document.ipAddress == ipAddress) { curIpDocument = document; }
            if (document.ipAddress == newIpAddress) {
                newIpDocument = document;
                if (document.ipAddressStatus == "ALLOCATED") { throw 'Error [Change IP Address] : ip address is duplicated'; }
            }
        }
        if (!curIpDocument) { throw "Error [Change IP Address] : could not find current ip address"; }
        curIpDocument.ipAddressStatus = "RELEASED";
        curIpDocument.connectedResourceLink = undefined;
        curIpDocument.ipAllocationType = "NONE";
        curIpDocument = aa.patchUerp(curIpDocument.documentSelfLink, curIpDocument);
        if (newIpDocument) {
            newIpDocument.ipAddressStatus = "ALLOCATED";
            newIpDocument.connectedResourceLink = intfLink;
            newIpDocument.ipAllocationType = "SYSTEM";
            newIpDocument = aa.patchUerp(newIpDocument.documentSelfLink, newIpDocument);
        } else {
            newIpDocument = aa.postUerp("/resources/ip-addresses", {
                subnetRangeLink: subnetRangeLink,
                connectedResourceLink: intfLink,
                ipAddress: newIpAddress,
                ipAddressStatus: "ALLOCATED",
                ipAllocationType: "SYSTEM",
                customProperties: {}
            });
        }
        var nsx = System.getModule("com.gvp").NsxManager(aa.getUerp(subnet.endpointLink).endpointProperties.hostName.split(".")[0]);
        var nsxUpdated = false;
        for each(var dhcp in nsx.get("/policy/api/v1" + subnet.customProperties.__path + "/dhcp-static-binding-configs").results) {
            if (dhcp.id == interfaceId) {
                dhcp.ip_address = newIpAddress;
                nsx.patch("/policy/api/v1" + dhcp.path, dhcp);
                nsxUpdated = true;
                break;
            }
        }
        if (!nsxUpdated) {
            curIpDocument.ipAddressStatus = "ALLOCATED";
            curIpDocument.connectedResourceLink = intfLink;
            curIpDocument.ipAllocationType = "SYSTEM";
            curIpDocument = aa.patchUerp(curIpDocument.documentSelfLink, curIpDocument);
            newIpDocument.ipAddressStatus = "AVAILABLE";
            newIpDocument.connectedResourceLink = undefined;
            newIpDocument.ipAllocationType = "NONE";
            newIpDocument = aa.patchUerp(newIpDocument.documentSelfLink, newIpDocument);
            throw 'could not find previous dhcp setting in nsx';
        }

        interface.address = newIpAddress;
        interface.addressLinks = [newIpDocument.documentSelfLink];
        aa.putUerp(intfLink, interface);
        if (interface.customProperties.primaryAddress == "true") {
            compute.address = newIpAddress;
            compute = aa.putUerp(computeLink, compute);
            computeDesc.address = newIpAddress;
            aa.putUerp(compute.descriptionLink, computeDesc);
        }
        /*
        var ipChangeScript =  Server.getResourceElementCategoryWithPath("/GVP/cloud-init-ip-replace").resourceElements[0].getContentAsMimeAttachment().content;
        ipChangeScript = ipChangeScript.replace("replaceOldIp", ipAddress);
        ipChangeScript = ipChangeScript.replace("replaceNewIp", newIpAddress);
        //scripts += "sudo /usr/bin/cloud-init clean -c network\n";
        //scripts += "sudo rm -rf /etc/sysconfig/network-scripts/ifcfg-*\n";
        //scripts += "sudo rm -rf /etc/network/interfaces\n";
        //scripts += "sudo rm -rf /etc/netplan/*\n";
        //scripts += "sudo /usr/bin/cloud-init init --local\n";
        //scripts += "sudo /usr/bin/cloud-init init\n";
        //var resourceId = computeLink.split("/compute/")[1];
        //var resourceName = compute.name;
        var vcConf = System.getModule("com.gvp").ConfManager().load("GVP/Endpoint/" + aa.getUerp(compute.endpointLink).endpointProperties.hostName.split(".")[0]);
        var stdout = System.getModule("com.gvp").execScripts(vcConf.hostname, vcConf.username, vcConf.password, compute.name, adminUsername, adminPassword, ipChangeScript);
        System.log(stdout);
        */
        aa.post("/iaas/api/machines/" + resourceId + "/operations/reboot", {});
        if (releaseMode != "RELEASED") {
            curIpDocument.ipAddressStatus = releaseMode;
            aa.patchUerp(curIpDocument.documentSelfLink, curIpDocument);
        }

    } else {
        throw "This Interface could not change IP Address. Check Interface Network Type Tag."
    }
} else {
    var aa = System.getModule("com.gvp").AaManager(true);
    var machine = aa.get("/iaas/api/machines/" + resourceId);
    var additionalNetworks = JSON.parse(machine.customProperties.additionalNetworks);
    for(var i =0; i < additionalNetworks.length; i++){
        if(additionalNetworks[i].id == interfaceLink){    
            var network = aa.get(additionalNetworks[i].network);
            var cloudAccount = aa.get("/iaas/api/cloud-accounts/" + network.cloudAccountIds[0]);
            var nsx = System.getModule("com.gvp").NsxManager(cloudAccount.cloudAccountProperties.hostName.split(".")[0]);
            var nsxUpdated = false;
            for each(var dhcp in nsx.get("/policy/api/v1" + additionalNetworks[i].segPath + "/dhcp-static-binding-configs").results) {
                if (dhcp.id == interfaceLink) {
                    dhcp.ip_address = newIpAddress;
                    nsx.patch("/policy/api/v1" + dhcp.path, dhcp);
                    nsxUpdated = true;
                    break;
                }
            }
            if(nsxUpdated){
                try{
                    aa.post(additionalNetworks[i].ipRangelink + "/ip-addresses/release?apiVersion=2021-07-15", { ipAddresses: [additionalNetworks[i].address]});
                    aa.post(additionalNetworks[i].ipRangelink + "/ip-addresses/allocate?apiVersion=2021-07-15", { ipAddresses: [newIpAddress]});
                } catch (e){
                    // DHCP Setting Roll Back
                    for each(var dhcp in nsx.get("/policy/api/v1" + additionalNetworks[i].segPath + "/dhcp-static-binding-configs").results) {
                        if (dhcp.id == interfaceLink) {
                            dhcp.ip_address = additionalNetworks[i].address;
                            nsx.patch("/policy/api/v1" + dhcp.path, dhcp);
                            nsxUpdated = true;
                            break;
                        }
                    }
                    throw "Cloud not Allocate new IP Address : " + e;
                }

                additionalNetworks[i].address = newIpAddress;
            } else{
                throw 'could not find previous dhcp setting in nsx';
            }   
        }
        aa.patch("/iaas/api/machines/" + resourceId, {
            customProperties: {
                additionalNetworks: JSON.stringify(additionalNetworks)
            }
        });
        aa.post("/iaas/api/machines/" + resourceId + "/operations/reboot", {});

    }
}



var aa = System.getModule("com.gvp").AaManager(true);

var pageable = true;
var page = 0;
while (pageable){
    
    var deployments =  aa.get("/deployment/api/deployments?resourceTypes=Cloud.vSphere.Machine&expand=resources&page=" + page);
    System.log("Total Page is " + deployments.totalPages);
    System.log("Page Number is " + deployments.pageable.pageNumber);

    for (var deployment of deployments.content){
        var resource = deployment.resources.filter(function (item) { return item.type == "Cloud.vSphere.Machine" })[0]
        System.log("Machine Display Name : " + resource.properties.displayName + "  / Machine ID : " + resource.id);
        var compute = aa.getUerp("/resources/compute/" + resource.id);
        var interfaceLinks = compute.networkInterfaceLinks
        for (var interfaceLink of interfaceLinks){
            var interface = aa.getUerp(interfaceLink);
            if(interface.address){
                var address = aa.getUerp(interface.addressLinks[0]);
                var detectedAddress = interface.address;
                var allocatedAddress = address.ipAddress;
                System.log("Machine " + compute.name + "  Interface" + interface.deviceIndex +" Detected address : " + detectedAddress + " / Allocated address : " + allocatedAddress);

                var conv = System.getModule("com.gvp").Converter();
                var cidr = interface.customProperties.__cidr;
                var subnetmask = 32 - Number(cidr.split("/")[1]);
                
                var limitLength = Math.pow(2, subnetmask);
                var networkIp = cidr.split("/")[0];
                var networkIpNum = conv.ip.getNumeric(networkIp);
                var ipNum = conv.ip.getNumeric(detectedAddress);
                var clac = Math.abs(ipNum - networkIpNum);
                if(limitLength >= clac){
                    var subnetRangeLink = address.subnetRangeLink
                } else {
                    System.log("###########Subnet CIDR MISMATCH##############")
                    System.log("###########Find CIDR from 24 bitH##############")
                    var subnetmask = 20
                    var searching = true;
                    while (searching) {
                        var networkIp = conv.ip.getNetworkIp(detectedAddress, subnetmask);
                        var cidr = networkIp + "/" + subnetmask
                        var subnetDocumentLinks =  aa.getUerp("/resources/sub-networks?$filter=subnetCIDR eq '" + cidr + "'").documentLinks;
                        if (subnetDocumentLinks.length > 1){
                            System.warn("There is one or more networks with the same CIDR subnet.")
                            searching = false;
                        } else if (subnetDocumentLinks.length == 1){
                            System.log("Found it!!");
                            System.log(subnetDocumentLinks[0]);
                            searching = false;

                            var subnetRangeLinks = aa.getUerp("/resources/subnet-ranges?$filter=subnetLink eq '" + subnetDocumentLinks[0] + "'").documentLinks;
                            
                            if(subnetRangeLinks.length == 1){
                                var subnetRangeLink = subnetRangeLinks[0];
                            } else if (subnetRangeLinks.length > 1){
                                for (var subnetRangeDocLink of subnetRangeLinks){
                                    var subnetRange = aa.getUerp(subnetRangeDocLink);
                                    var startIPAddress = conv.ip.getNumeric(subnetRange.startIPAddress);
                                    var endIPAddress =  conv.ip.getNumeric(subnetRange.endIPAddress);
                                    if(startIPAddress <= ipNum && endIPAddress >= ipNum){
                                        var subnetRangeLink = subnetRangeDocLink;
                                        break;
                                    }
                                    
                                }
                            }

                        } else {
                            subnetmask++;
                        }

                        if(subnetmask == 32){
                            System.log("Cannot Found Subnet networks");
                            searching = false;
                        }
                    }
                }
                if(detectedAddress != allocatedAddress && subnetRangeLink){
                    System.log("Detected address is mismatch with Allocated address!")
                    address.ipAddressStatus = "RELEASED";
                    address.connectedResourceLink = undefined;
                    address.ipAllocationType = "NONE";
                    address = aa.patchUerp(address.documentSelfLink, address);
                    System.log("Allocated address RELEASED!")
                    var findDetectAddress = aa.getUerp("/resources/ip-addresses?$filter=ipAddress eq '"  + detectedAddress + "'");
                    if(findDetectAddress.totalCount >= 1){
                        System.log("Found Detected address resource")
                        var newIpDocument = aa.getUerp(findDetectAddress.documentLinks[0]);
                        newIpDocument.ipAddressStatus = "ALLOCATED";
                        newIpDocument.connectedResourceLink = interfaceLink;
                        newIpDocument.ipAllocationType = "SYSTEM";
                        newIpDocument = aa.patchUerp(newIpDocument.documentSelfLink, newIpDocument);
                        System.log("Detected address resource Allocated")
                    } else {
                        newIpDocument = aa.postUerp("/resources/ip-addresses", {
                            subnetRangeLink: subnetRangeLink,
                            connectedResourceLink: interfaceLink,
                            ipAddress: detectedAddress,
                            ipAddressStatus: "ALLOCATED",
                            ipAllocationType: "SYSTEM",
                            customProperties: {}
                        });
                        System.log("Detected address resource Create and Allocated")
                    }
                    interface.addressLinks = [newIpDocument.documentSelfLink];
                    aa.putUerp(interfaceLink, interface);
                }
                
                

            }
            
            
        }
    }



    if(deployments.last == true){
        System.log("This page is last")
        pageable = false;
    } else {
        System.log("This page is not last, Add page number")
        page++
    }
}



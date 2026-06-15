var computeId = inputProperties.resourceIds[0];
if (computeId && computeId != "N/A" && inputProperties.customProperties.profile) {
    var aa = System.getModule("com.gvp").AaManager(true);
    var endpointId = inputProperties.endpointId;
    var endpointLink = "/iaas/api/cloud-accounts/" + endpointId;
    var endpointName = aa.get(endpointLink).cloudAccountProperties.hostName.split(".")[0];
    var customProperties = inputProperties.customProperties;
    var rootPassword = customProperties.rootPassword ? customProperties.rootPassword : null;
    var computeLink = "/resources/compute/" + computeId;
    var compute = aa.getUerp(computeLink);
    var computeName = compute.name;
    var nsx = null;
    var gpuCount = customProperties.gpuDeviceCount?Number(customProperties.gpuDeviceCount):1;
    var deviceIndex = [];
    var bridgeIps = "";
    var vm = VcPlugin.getAllVirtualMachines(null, "xpath:name='" + computeName + "'")[0];
    if(compute.customProperties.dynamicNetworks){
        var dynamicNetworks = JSON.parse(compute.customProperties.dynamicNetworks);
        for (var i = 0 ; i < compute.networkInterfaceLinks.length; i++ ){
            var interfaceId = compute.networkInterfaceLinks[i].split("/network-interfaces/")[1];
            var interface = aa.getUerp(compute.networkInterfaceLinks[i]);
            var tag = aa.getUerp(interface.tagLinks[0]);
            var macAddress = interface.customProperties.mac_address;
            var subnet = aa.getUerp(interface.subnetLink);
            var subnetRange = aa.getUerp("/provisioning/mgmt/subnet-range?$filter=subnetLink eq '" + subnet.documentSelfLink + "'");
            var subnetRangeLink = subnetRange.documents[subnetRange.documentLinks[0]].documentSelfLink;
            var ipRangeId = subnetRange.documentLinks[0].split("/subnet-ranges/")[1];
            var dnsServerAddresses = subnet.dnsServerAddresses;
            var gatewayAddress =subnet.gatewayAddress;
            var network = dynamicNetworks.filter(function(item){ return item.deviceIndex == interface.deviceIndex})[0];
            if (!nsx) { nsx = System.getModule("com.gvp").NsxManager(aa.getUerp(subnet.endpointLink).endpointProperties.hostName.split(".")[0]);}
            if(tag.value != "bridge"){
                if(network.address){
                    var ipResponse = aa.post("/iaas/api/network-ip-ranges/" + ipRangeId + "/ip-addresses/allocate?apiVersion=2021-07-15",{ipAddresses: [network.address]})
                    var networkAddress = network.address;
                } else {
                    var ipResponse = aa.post("/iaas/api/network-ip-ranges/" + ipRangeId + "/ip-addresses/allocate?apiVersion=2021-07-15",{numberOfIps: 1});
                    System.sleep(1000);
                    var requestTracker = aa.get(ipResponse.selfLink);
                    var ipAddressLink = requestTracker.resources[0];
                    var networkAddress = aa.get(ipAddressLink + "?apiVersion=2021-07-15").ipAddress;
                }
                deviceIndex.push(interface.deviceIndex);
                try {
                    var payload =  {
                        resource_type: "DhcpV4StaticBindingConfig",
                        display_name: computeName + "-" + macAddress,
                        //host_name: network.primaryAddress == "true"?computeName:computeName + String(interface.deviceIndex),
                        ip_address: networkAddress,
                        mac_address: macAddress,
                        //gateway_address: gatewayAddress,
                        options: dnsServerAddresses.length==0||network.primaryAddress == "false"?{}:{
                            others: [
                                {
                                    code: 6,
                                    values: dnsServerAddresses
                                }
                            ]
                        }
                    }
                    if(network.primaryAddress == "true") { 
                        payload.gateway_address = gatewayAddress
                        payload.host_name = computeName
                    };
                    nsx.put("/policy/api/v1" + subnet.customProperties.__path + "/dhcp-static-binding-configs/" + interfaceId, payload);
                } catch (e) {
                    aa.post("/iaas/api/network-ip-ranges/" + ipRangeId + "/ip-addresses/release?apiVersion=2021-07-15",{ipAddresses: [networkAddress]})
                    throw e;
                }

            } else if (tag.value == "bridge") {
                bridgeIps += interface.address + " ";
            }


        }
        if(customProperties.osName == "rocky" && dynamicNetworks.filter(function(item){return item.assignment == "static"}).length == 0){
            var powerTask = vm.powerOnVM_Task();
            System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(powerTask, false, 1) ;
            System.getModule("com.vmware.library.vc.vm.tools").vim3WaitToolsStarted(vm, 1, 5);
            if(rootPassword){
                var scripts = "/bin/bash -c '"
                scripts += 'for dev in $(nmcli -t -f DEVICE,STATE device | grep disconnected | cut -d: -f1); do nmcli connection show "$dev" 2>/dev/null || nmcli connection add type ethernet ifname "$dev" con-name "$dev" autoconnect yes; done'
                scripts += "'"
                var vcConf = System.getModule("com.gvp").ConfManager().load("GVP/Endpoint/" + endpointName);
                var execScripts = System.getModule("com.gvp").execScripts;
                var execResult = execScripts(vcConf.hostname, vcConf.username, vcConf.password, computeName, "root", rootPassword, scripts);
                System.log(execResult)
            }
        }
    } else{
        System.log("Cannot find dynamicNetworks");
    }
}
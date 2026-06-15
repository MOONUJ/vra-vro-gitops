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
    } else{
        throw "Cannot find dynamicNetworks"
    }
    
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
        if(network.address){
            var ipResponse = aa.post("/iaas/api/network-ip-ranges/" + ipRangeId + "/ip-addresses/allocate?apiVersion=2021-07-15",{ipAddresses: [network.address]})
            var networkAddress = network.address;
        } else {
            var ipResponse = aa.post("/iaas/api/network-ip-ranges/" + ipRangeId + "/ip-addresses/allocate?apiVersion=2021-07-15",{numberOfIps: 1})
            var requestTracker = aa.get(ipResponse.selfLink);
            var ipAddressLink = requestTracker.resources[0];
            var networkAddress = aa.get(ipAddressLink + "?apiVersion=2021-07-15").ipAddress;
        }
        if (!nsx) { nsx = System.getModule("com.gvp").NsxManager(aa.getUerp(subnet.endpointLink).endpointProperties.hostName.split(".")[0]);}
        if(tag.value != "bridge"){
            deviceIndex.push(interface.deviceIndex);
            nsx.put("/policy/api/v1" + subnet.customProperties.__path + "/dhcp-static-binding-configs/" + interfaceId, {
                resource_type: "DhcpV4StaticBindingConfig",
                display_name: computeName + "-" + macAddress,
                host_name: interface.customProperties.primaryAddress == "true"?computeName:"",
                ip_address: networkAddress,
                mac_address: macAddress,
                gateway_address: gatewayAddress,
                options: dnsServerAddresses.length==0?{}:{
                    others: [
                        {
                            code: 6,
                            values: dnsServerAddresses
                        }
                    ]
                }
            });
        } else if (tag.value == "bridge") {
            bridgeIps += interface.address + " ";
        }

    }

    if (rootPassword) {
        //var scripts = Server.getResourceElementCategoryWithPath("/GVP/cloud-init").resourceElements[0].getContentAsMimeAttachment().content;
        //scripts = scripts.replace("replaceKeepStatic", bridgeIps);
        //scripts += " \n";
        //scripts += 'echo "network: {config: disabled}" > /etc/cloud/cloud.cfg.d/99_network_disabled.cfg\n';
        //scripts += "rm -rf /etc/sysconfig/network-scripts/ifcfg-*\n"; // redhat, fedora, centos, rocky
        //scripts += "rm -rf /etc/network/interfaces\n"; // devian(ubuntu) older
        //scripts += "rm -rf /etc/netplan/*\n"; // devian(ubuntu) newer
        var scripts = "";
        scripts += "/usr/bin/cloud-init clean -s -l -c all\n";
        scripts += "/usr/bin/cloud-init init --local\n";
        scripts += "/usr/bin/cloud-init init\n";
        scripts += "/usr/bin/cloud-init modules --mode=config\n";
        scripts += "/usr/bin/cloud-init modules --mode=final\n";
        var vcConf = System.getModule("com.gvp").ConfManager().load("GVP/Endpoint/" + endpointName);
        var execScripts = System.getModule("com.gvp").execScripts;
        var execResult = execScripts(vcConf.hostname, vcConf.username, vcConf.password, computeName, "root", rootPassword, scripts);
        System.log(execResult)

        if(customProperties.note){
            var vmSpec = new VcVirtualMachineConfigSpec();
            vmSpec.annotation = customProperties.note;
            var vmTask = vm.reconfigVM_Task(vmSpec);
            System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(vmTask, false, 1) ;
        }


        // GPU 설정
        if(customProperties.gpuModel){
            var devices = vm.config.hardware.device;
            var pciDevice = devices.filter( function(item){
                return item instanceof VcVirtualPCIPassthrough;
            });
            try {
                System.getModule("com.vmware.library.vc.vm.tools").vim3WaitToolsStarted(vm, 1, 5);
                System.getModule("com.vmware.library.vc.vm.power").shutdownVM(vm, 10, 1);
                if(pciDevice > 0){
                    var deviceChange = new Array();
                    for(var i = 0; i < pciDevice.length; i++){
                        deviceChange[i] = new VcVirtualDeviceConfigSpec();
                        deviceChange[i].device = pciDevice[i];
                        deviceChange[i].device.backing.vgpu = customProperties.gpuProfile;
                        deviceChange[i].operation = VcVirtualDeviceConfigSpecOperation.edit;
                    }

                    var spec = new VcVirtualMachineConfigSpec();
                    spec.deviceChange = deviceChange;
                    var task = vm.reconfigVM_Task(spec);
                    //System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(task, false, 1) ;
                    //System.getModule("com.vmware.library.vc.vm.power").startVM(vm);
                    //System.getModule("com.vmware.library.vc.vm.tools").vim3WaitToolsStarted(vm, 1, 5);
                } else if(pciDevice == 0){
                    for (var key in devices) {
                        var device = devices[key];
                        if (device instanceof VcVirtualPCIController){
                            var controllerKey = device.key;
                        }
                    }

                    
                    for(var i =0; i < gpuCount; i++){
                        var deviceChange = new Array();
                        deviceChange[0] = new VcVirtualDeviceConfigSpec();
                        deviceChange[0].device = new VcVirtualPCIPassthrough();
                        deviceChange[0].device.controllerKey = controllerKey; 
                        deviceChange[0].device.backing = new VcVirtualPCIPassthroughVmiopBackingInfo();
                        deviceChange[0].device.backing.vgpu = customProperties.gpuProfile;
                        deviceChange[0].device.slotInfo = new VcVirtualDevicePciBusSlotInfo();
                        deviceChange[0].device.unitNumber = null;
                        deviceChange[0].device.key = null;
                        deviceChange[0].device.deviceInfo = new VcDescription();
                        deviceChange[0].device.deviceInfo.summary = "NVIDIA GRID vGPU";
                        deviceChange[0].device.deviceInfo.label = "PCI device " + i.toString();
                        deviceChange[0].operation = VcVirtualDeviceConfigSpecOperation.add;

                        var spec = new VcVirtualMachineConfigSpec();
                        spec.deviceChange = deviceChange;
                        var task = vm.reconfigVM_Task(spec);

                        System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(task, false, 1) ;
                        System.log("Device" + i.toString() + " Attach Success!")
                    }


                }

                var powerTask = vm.powerOnVM_Task();
                System.getModule("com.vmware.library.vc.basic").vim3WaitTaskEnd(powerTask, false, 1) ;
                //System.getModule("com.vmware.library.vc.vm.power").startVM(vm);
                System.getModule("com.vmware.library.vc.vm.tools").vim3WaitToolsStarted(vm, 1, 5);
            } catch (e) {
                throw e
            }

        } else {
            // None GPU VM Reboot
            while (true) {
                System.sleep(1000);
                System.log("try reboot");
                try {
                    aa.post("/iaas/api/machines/" + computeId + "/operations/reboot", {});
                    break;
                } catch (e) {
                    System.log("reboot error : " + e);
                }
            }
        }
        
    }
}

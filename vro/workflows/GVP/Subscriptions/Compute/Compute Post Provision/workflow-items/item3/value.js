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
    compute.customProperties.createDate = vm.config.createDate;
    compute.customProperties.cloudZoneId = compute.customProperties["__vmw:provisioning:cloudZone"];
    aa.patchUerp(computeLink, compute);
    if(!customProperties.dynamicNetworks){
        for each(var intfLink in compute.networkInterfaceLinks){
            var interfaceId = intfLink.split("/network-interfaces/")[1];
            var interface = aa.getUerp(intfLink);
            var tag = aa.getUerp(interface.tagLinks[0]);
            var macAddress = interface.customProperties.mac_address;
            var subnet = aa.getUerp(interface.subnetLink);
            var dnsServerAddresses = subnet.dnsServerAddresses;
            if (!nsx) { nsx = System.getModule("com.gvp").NsxManager(aa.getUerp(subnet.endpointLink).endpointProperties.hostName.split(".")[0]);}
            if(tag.value != "bridge"){
                deviceIndex.push(interface.deviceIndex);
                var payload = {
                    resource_type: "DhcpV4StaticBindingConfig",
                    display_name: computeName + "-" + macAddress,
                    ip_address: interface.address,
                    mac_address: macAddress,
                    gateway_address: interface.customProperties.gateways,
                }
                if(interface.customProperties.primaryAddress == "true"){ payload['host_name'] = computeName;}
                if(dnsServerAddresses.length>0){ 
                    payload.options = { 
                        others: [
                            { 
                                code: 6, 
                                values: dnsServerAddresses
                            }
                        ]
                    }
                }
                nsx.put("/policy/api/v1" + subnet.customProperties.__path + "/dhcp-static-binding-configs/" + interfaceId, payload);
            } else if (tag.value == "bridge") {
                bridgeIps += interface.address + " ";
            }

        }
    }


    if (rootPassword) {
        if(!customProperties.dynamicNetworks && customProperties.osName == "rocky"){
            var scripts = Server.getResourceElementCategoryWithPath("/GVP/cloud-init").resourceElements[0].getContentAsMimeAttachment().content;
            scripts = scripts.replace("replaceKeepStatic", bridgeIps);
            scripts += " \n";
            
            scripts += "rm -rf /etc/sysconfig/network-scripts/ifcfg-*\n"; // redhat, fedora, centos, rocky
            scripts += "rm -rf /etc/network/interfaces\n"; // devian(ubuntu) older
            scripts += "rm -rf /etc/netplan/*\n"; // devian(ubuntu) newer
            
        } else {
            var scripts = "";
        }
        //scripts += 'echo "network: {config: disabled}" > /etc/cloud/cloud.cfg.d/99_network_disabled.cfg\n';
        //scripts += "/usr/bin/cloud-init clean -s -l -c all\n";
        //scripts += "/usr/bin/cloud-init init --local\n";
        //scripts += "/usr/bin/cloud-init init\n";
        //scripts += "/usr/bin/cloud-init modules --mode=config\n";
        //scripts += "/usr/bin/cloud-init modules --mode=final\n";
        scripts += "/usr/bin/eject /dev/sr0";
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
            // Search GPU License Token File in ResourceElement
            System.log("Find License Token File")
            var conv = System.getModule("com.gvp").Converter();
            var subCategories = Server.getResourceElementCategoryWithPath("GVP/token").subCategories;
            for each(var subCategory in subCategories){
                var cidr = subCategory.name;
                var subnetmask = 32 - Number(cidr.split("|")[1]);
                
                var limitLength = Math.pow(2, subnetmask);
                var networkIp = cidr.split("|")[0];
                var networkIpNum = conv.ip.getNumeric(networkIp);
                var ipNum = conv.ip.getNumeric(compute.address);
                var clac = Math.abs(ipNum - networkIpNum);
                if(limitLength >= clac){
                    var mimeAttachment = subCategory.resourceElements[0].getContentAsMimeAttachment();
                }
                if(!mimeAttachment){
                    System.warn("Cannot Found License Token File in ResourceElement")
                }
            }

            // Upload Token File to VM  
            /*
            if(mimeAttachment){
                var guestDirPath = customProperties.osType == "LINUX"?"/etc/nvidia/ClientConfigToken": "";
                System.getModule("com.gvp").uploadFiletoVM(vm, "root", rootPassword, mimeAttachment, guestDirPath);
                execScripts(vcConf.hostname, vcConf.username, vcConf.password, computeName, "root", rootPassword, "chmod +x /etc/nvidia/ClientConfigToken/" + mimeAttachment.name);
            }
            */
            

            // Try GPU Device Attach
            System.log("Try GPU Device Attach");
            var devices = vm.config.hardware.device;
            var pciDevice = devices.filter( function(item){
                return item instanceof VcVirtualPCIPassthrough;
            });
            try {
                System.getModule("com.vmware.library.vc.vm.tools").vim3WaitToolsStarted(vm, 1, 5);
                System.getModule("com.vmware.library.vc.vm.power").shutdownVM(vm, 10, 1);
                if(pciDevice.length > 0){
                    System.log("PCI Device > 0 ");
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
                } else if(pciDevice.length  == 0){
                    for (var key in devices) {
                        System.log("PCI Device == 0");
                        var device = devices[key];
                        if (device instanceof VcVirtualPCIController){
                            var controllerKey = device.key;
                        }
                    }

                    
                    for(var i =0; i < gpuCount; i++){
                        System.log("customProperties.gpuProfile : " + customProperties.gpuProfile);
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

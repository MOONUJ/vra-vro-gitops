for each(var instance in machineInstance){
    var config = Server.createConfigurationElement(configurationPath,instance.name);
    config.setAttributeWithKey("cpu",Number(instance.cpu), String("number"));
    config.setAttributeWithKey("memory",Number(instance.memory), String("number"));
    config.setAttributeWithKey("gpuModel",String(instance.gpuModel), String("string"));
    config.setAttributeWithKey("gpuSize",String(instance.gpuSize), String("string"));
    config.setAttributeWithKey("gpuProfile",String(instance.gpuProfile), String("string"));
    config.setAttributeWithKey("deviceCount",String(instance.deviceCount), String("number"));
    config.setAttributeWithKey("vcsa_cluster",String(instance.vcsa_cluster), String("Array/string"));
}
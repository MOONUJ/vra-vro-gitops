var cec = Server.getConfigurationElementCategoryWithPath(configurationPath + "/" + vcsa);
if(cec && cec.configurationElements){
    var ce = cec.configurationElements.filter(function(item){ return item.name == name});
    if(ce.length > 0){
        throw "Already Exsist Machine Instance Name"
    }
    
}
var config = Server.createConfigurationElement(configurationPath + "/" + vcsa, name);
config.setAttributeWithKey("cpu",Number(cpu), String("number"));
config.setAttributeWithKey("memory",Number(memory), String("number"));
config.setAttributeWithKey("gpuModel",String(gpuModel), String("string"));
config.setAttributeWithKey("gpuSize",String(gpuSize), String("string"));
config.setAttributeWithKey("gpuProfile",String(gpuProfile), String("string"));
config.setAttributeWithKey("deviceCount",Number(deviceCount), String("number"));
config.setAttributeWithKey("cluster",cluster, String("Array/string"));
function getGpuMemory(profileString) {
    if (!profileString) {
        return null;
    }
    
    var lastHyphen = profileString.lastIndexOf('-');
    if (lastHyphen === -1) {
        return null;
    }
    
    var sizeStr = profileString.substring(lastHyphen + 1);
    var match = sizeStr.match(/\d+/);
    
    return match ? match[0] : null;
}

if(!gpuProfile) { return null;}

return getGpuMemory(gpuProfile);
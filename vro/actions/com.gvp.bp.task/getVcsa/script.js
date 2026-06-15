var sdkconnections = VcPlugin.allSdkConnections;

var result = [];

for each( var sdk in sdkconnections){
    result.push(sdk.id);
}

return result;
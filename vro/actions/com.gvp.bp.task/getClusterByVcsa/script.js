if(!vcsa) {return null}

var sdk = VcPlugin.allSdkConnections.filter(function(item){ return item.id == vcsa})[0];

var clusters = sdk.getAllComputeResources();

var result = [];
for each(var cluster in clusters){
    result.push(cluster.name);
}

return result;
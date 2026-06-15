if (!subnetLink) { return null; }
if (!addressType) { return null; }

var conv = System.getModule("com.gvp").Converter();
var aa = System.getModule("com.gvp").AaManager(true);

/*
var checker = "segType";
var aa = System.getModule("com.gvp").AaManager();
var network = aa.get(subnetLink);
if(network.tags){
    for each(var tagObj in network.tags){
        if(tagObj.key == checker) { var segType = tagObj.value;} 
    }
    
}
if(segType == 'bridge'){
    return null;
}
*/

var networkIpRanges = aa.get(subnetLink + "/network-ip-ranges?apiVersion=2025-08-25").content;
var result = [];



for each(var networkIpRange in networkIpRanges){
    var startIpNumeric = conv.ip.getNumeric(networkIpRange.startIPAddress);
    var endIpNumeric = conv.ip.getNumeric(networkIpRange.endIPAddress);
    var usedIpAddresses = aa.get("/iaas/api/network-ip-ranges/" + networkIpRange.id + "/ip-addresses?apiVersion=2025-08-25").content.filter(function(item){
        return item.ipAddressStatus != "AVAILABLE";
    });
    var used = [];
    for each(var usedIpAddress in usedIpAddresses){
        used.push(conv.ip.getNumeric(usedIpAddress.ipAddress));
    }
    for (var ip = startIpNumeric; ip <= endIpNumeric; ip++) {
        if(used.indexOf(ip) < 0) {
            result.push(conv.ip.getString(ip));
        }
    }
}
if(result.length == 0) {
    throw "Could not find Available IP Address"
}
return addressType == 'variable'?['*']:result;

/*
var subnetRanges = aa.getUerp("/provisioning/mgmt/subnet-range?$filter=subnetLink eq '" + subnetLink + "'")
var result = addressType == "variable"?['*']:[];
for each(var subnetRangeLink in subnetRanges.documentLinks) {
    var subnetRange = subnetRanges.documents[subnetRangeLink];
    var startIpNumeric = conv.ip.getNumeric(subnetRange.startIPAddress);
    var endIpNumeric = conv.ip.getNumeric(subnetRange.endIPAddress);
    var usedIpAddresses = aa.getUerp("/resources/ip-addresses?expand&$filter=(subnetRangeLink eq '" + subnetRangeLink + "') and (ipAddressStatus ne 'AVAILABLE')");
    var used = [];
    for each(var usedIpAddressLink in usedIpAddresses.documentLinks) {
    }
        used.push(conv.ip.getNumeric(usedIpAddresses.documents[usedIpAddressLink].ipAddress));
    for (var ip = startIpNumeric; ip <= endIpNumeric; ip++) {
        if (used.indexOf(ip) < 0) { result.push(conv.ip.getString(ip)); }
    }
}
*/
return result;
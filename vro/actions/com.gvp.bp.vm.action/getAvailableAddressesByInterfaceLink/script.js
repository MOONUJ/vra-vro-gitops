if (!interfaceLink) { return null; }
if (!resourceId) { return null; }

// /resources/network-interfaces/70415d16-8279-4398-8d1f-9e5175461c84
// 99244af2-0f7a-414a-80d3-2c13870d81de
if (interfaceLink == "permanent") { return []; }
var conv = System.getModule("com.gvp").Converter();
var aa = System.getModule("com.gvp").AaManager(true);
var result = [];
if ( interfaceLink.indexOf("/iaas/api/machines/") > -1){
    var interface = aa.get(interfaceLink + "?apiVersion=2021-07-15");
    var network = aa.get("/iaas/api/networks").content.filter( function(item){ return item.name == interface.name})[0];
    var subnetRanges = aa.get(network._links.self.href + "/network-ip-ranges?apiVersion=2021-07-15").content;
    for each( var subnetRange in subnetRanges){
        var startIpNumeric = conv.ip.getNumeric(subnetRange.startIPAddress);
        var endIpNumeric = conv.ip.getNumeric(subnetRange.endIPAddress);
        var usedIpAddresses = aa.get("/iaas/api/network-ip-ranges/" + subnetRange.id + "/ip-addresses?apiVersion=2021-07-15").content.filter(function (item){
            return item.ipAddressStatus != 'AVAILABLE';
        })
        var used = [];
        for each(var usedIpAddress in usedIpAddresses){
            used.push(conv.ip.getNumeric(usedIpAddress.ipAddress));
        }
        for (var ip = startIpNumeric; ip <= endIpNumeric; ip++) {
            if (used.indexOf(ip) < 0) { result.push(conv.ip.getString(ip)); }
        }
    }
} else {
    var machine = aa.get("/iaas/api/machines/" + resourceId);
    var additionalNetworks = JSON.parse(machine.customProperties.additionalNetworks);
    var additionalNetwork = additionalNetworks.filter( function (item){ return item.id == interfaceLink})[0]
    var subnetRanges = aa.get(additionalNetwork.network + "/network-ip-ranges?apiVersion=2021-07-15").content;
    for each( var subnetRange in subnetRanges){
        var startIpNumeric = conv.ip.getNumeric(subnetRange.startIPAddress);
        var endIpNumeric = conv.ip.getNumeric(subnetRange.endIPAddress);
        var usedIpAddresses = aa.get("/iaas/api/network-ip-ranges/" + subnetRange.id + "/ip-addresses?apiVersion=2021-07-15").content.filter(function (item){
            return item.ipAddressStatus != 'AVAILABLE';
        })
        var used = [];
        for each(var usedIpAddress in usedIpAddresses){
            used.push(conv.ip.getNumeric(usedIpAddress.ipAddress));
        }
        for (var ip = startIpNumeric; ip <= endIpNumeric; ip++) {
            if (used.indexOf(ip) < 0) { result.push(conv.ip.getString(ip)); }
        }
    }
}

return result;
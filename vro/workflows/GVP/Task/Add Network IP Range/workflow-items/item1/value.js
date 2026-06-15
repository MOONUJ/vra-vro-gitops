var aa = System.getModule("com.gvp").AaManager(true);
var conv = System.getModule("com.gvp").Converter();
var account = aa.get("/iaas/api/cloud-accounts/" + nsxManager);
var nsx = System.getModule("com.gvp").NsxManager(account.cloudAccountProperties.hostName.split(".")[0]);

var fabricNetwork = aa.get("/iaas/api/fabric-networks/" + network);
var segType = aa.get("/iaas/api/network-domains/" + fabricNetwork.networkDomainId).customProperties.__transportZoneTrafficType == "VLAN_BACKED"? "bridge": "overlay";
if(segType == "overlay"){
    var segmentPath = fabricNetwork.customProperties.path
    var segment = nsx.get("/policy/api/v1" + segmentPath);
    var t1Service = nsx.get("/policy/api/v1" + segment.connectivity_path + "/locale-services").results[0];
    if(!segment["dhcp_config_path"]){
        var subnet = segment.subnets[0].network

        var dhcpServerAddress = conv.ip.getString(conv.ip.getNumeric(startIp)) + "/" + subnet.split("/")[1];
        var dhcpServer = nsx.put("/policy/api/v1/infra/dhcp-server-configs/" + segment.id, {
            display_name: segment.id,
            edge_cluster_path: t1Service.edge_cluster_path,
            enable_standby_relocation: false,
            resource_type: "DhcpServerConfig",
            server_addresses: [dhcpServerAddress]
        });
        segment.dhcp_config_path = dhcpServer.path;
        segment.subnets[0].dhcp_config = {
            resource_type: "SegmentDhcpV4Config",
            server_address: dhcpServerAddress,
            lease_time: 86400,
            dns_servers: subnet.dnsServerAddresses
        }
        nsx.put("/policy/api/v1" + segmentPath, segment);
    }

    aa.post("/iaas/api/network-ip-ranges",{
        "name": fabricNetwork.name + "-IP-Range",
        "fabricNetworkIds": [
            network
        ],
        "ipVersion": "IPv4",
        "startIPAddress": conv.ip.getString(conv.ip.getNumeric(startIp) + 1),
        "endIPAddress": endIp,
    })
}

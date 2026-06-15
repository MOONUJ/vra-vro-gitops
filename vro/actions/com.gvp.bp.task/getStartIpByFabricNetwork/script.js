// NSX Cloud ACcount ID = 74c64b7c-be19-4086-9d92-845ff49abfd0
// Fabric Network ID = 650053fc-3644-4ade-8e95-473a2c38e672
if(!fabricNetwork){ return null};

var aa = System.getModule("com.gvp").AaManager(true);
var conv = System.getModule("com.gvp").Converter();
var fabric = aa.get("/iaas/api/fabric-networks/" + fabricNetwork);
if(fabric.cidr){
    var cidr = fabric.cidr;
} else {
    var array = fabric.name.split("-")
    if(array.length == 1 || array[array.length -1].indexOf(".") == -1) {
        return "Cloud not found CIDR"
    }
    var cidr = array[array.length -1] + "/24";
}

var networkIp = cidr.split("/")[0];
var networkIpNum = conv.ip.getNumeric(networkIp);
var startIp = conv.ip.getString(networkIpNum + 2);
//var subnetMask = Number(cidr.split("/")[1]);
//var limitLength = Math.pow(2, 32- subnetMask);
return startIp; 
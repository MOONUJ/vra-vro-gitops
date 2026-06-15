var aa = System.getModule("com.gvp").AaManager(true);
//return aa.get("/iaas/api/machines/75e4876d-5523-4f64-b0af-2e4bf5fdcb07/network-interfaces/598e36a2-04c1-4ba9-ad50-f10c542a22f2")
//var computeId = "67bd9165-e792-4bf5-bceb-9d2b93de4d93"
//var computeLink = "/resources/compute/" + computeId;
//return aa.getUerp("/resources/sub-networks/1f442179-c4a4-41ae-80ec-305a0a4cb0cd")
//return aa.getUerp("/resources/network-interfaces/598e36a2-04c1-4ba9-ad50-f10c542a22f2")
//return aa.getUerp(computeLink)
var conv = System.getModule("com.gvp").Converter();
var rm = System.getModule("com.gvp").ResourceManager();
var subCategories = Server.getResourceElementCategoryWithPath("GVP/token").subCategories;
for each(var subCategory in subCategories){
    var cidr = subCategory.name;
    var limitLength = 2 ** (32 - Number(cidr.split("|")[1]))
    var networkIpNum = conv.ip.getNumeric(cidr.split("|")[0]);
    var ipNum = conv.ip.getNumeric(address);
    var clac = Math.abs(ipNum - networkIpNum);
    if(limitLength >= clac){
        var mimeAttachment = subCategory.resourceElements[0].getContentAsMimeAttachment();
    }
    if(!mimeAttachment){
        System.warn("Cannot Found License Token File in ResourceElement")
    }
}
return mimeAttachment
return rm.load("GVP/token/172.20.100|24");
var cidr = "172.20.100.0/16";
var limitLength = 2 ** (32 - Number(cidr.split("/")[1]))
var ip = "172.20.100.0";
var networkIpNum = conv.ip.getNumeric(cidr.split("/")[0]);
var ipNum = conv.ip.getNumeric(ip);
var clac = Math.abs(ipNum - networkIpNum);
if(limitLength <= clac){
    return "Cannot include cidr"
} else {
    return "Include cidr"
}



var result =  conv.ip.getNumeric(ip) - conv.ip.getNumeric(cidr);
return result

return aa.get("/iaas/api/machines/75e4876d-5523-4f64-b0af-2e4bf5fdcb07")
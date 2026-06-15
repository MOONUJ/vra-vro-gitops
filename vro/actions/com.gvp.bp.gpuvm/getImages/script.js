if (!regionLink || !ostype || !gpuModel ) { return null; }


var aa = System.getModule("com.gvp").AaManager(true);
//var zone = aa.getUerp(placementZoneLink);

//var provisioningRegionLink = zone.provisioningRegionLink;
//if (!provisioningRegionLink) { throw "provisioningRegionLink cannot be null"; }
//var targetRegionId = provisioningRegionLink.split("/").pop();
var targetRegionId = regionLink.split("/").pop();

var images = aa.get("/iaas/api/images").content;
//var contentArray = imagesResponse.content || [];

var ostypeLower = ostype.toLowerCase();
var gpuModelLower = gpuModel.toLowerCase();

var result = [];
for (var i in images) {
    var regionHref = images[i]._links.region.href;
    var regionId = regionHref.split("/").pop();
    if (regionId === targetRegionId) {
        for (var imageName in images[i].mapping) {
            var mappingName = imageName.toString().toLowerCase();
            if(mappingName.indexOf(ostypeLower)!= -1 && mappingName.indexOf('gpu') != -1){
                result.push({
                    label: imageName.toString(),
                    value: imageName.toString()
                })
            }

            /*
            var tags = images[i].mapping[imageName].constraints;
            var hasGpuModel = tags.some(function(item) {
            return item.expression == "gpuModel:" + gpuModelLower;
            });

            if(hasGpuModel){
                result.push({
                    label: imageName.toString(),
                    value: imageName.toString()
                });
            }
            */

            /*
            var nameLower = imageName.toString().toLowerCase();
            if(nameLower.split("-").length > 2){
                var osName = nameLower.split("-").slice(0, 2).join("-");
                var gpuModelName = nameLower.split("-")[2];
                var gpuModelSize = nameLower.split("-")[3];
                if (osName.indexOf(ostypeLower) !== -1 && gpuModelName.indexOf(gpuModelLower) !== -1 && gpuModelSize.indexOf(gpuSizeLower) !== -1) {
                    result.push({
                        label: osName.toUpperCase(),
                        value: imageName.toString()
                    });
            }
            
            }
            */
        }
    }
}

return result;

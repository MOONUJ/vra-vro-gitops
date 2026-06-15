if (!resourceId){ return null};
var aa = System.getModule("com.gvp").AaManager(true);
var machine = aa.get("/deployment/api/resources/" + resourceId);
var disks = machine.properties.storage.disks.filter(function(item) { 
    return item.type == "HDD";
});

System.log("Current disk count (HDD only): " + disks.length);

var asisDiskInfos = [];
for each(var disk in disks) {
    if(disk["bootOrder"]) {
        asisDiskInfos.push({
            name: disk.name,
            size: disk.capacityGb,
            bootDisk: true
        });
        System.log("ASIS Disk (Boot): " + disk.name + " - " + disk.capacityGb + "GB");
    } else {
        asisDiskInfos.push({
            name: disk.name,
            size: disk.capacityGb,
            bootDisk: false
        });
        System.log("ASIS Disk: " + disk.name + " - " + disk.capacityGb + "GB");
    }
}
return asisDiskInfos
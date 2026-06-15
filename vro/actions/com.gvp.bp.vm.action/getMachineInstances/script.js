var instances = Server.getConfigurationElementCategoryWithPath("GVP/Instance").configurationElements;
var result = [];
for each(var instance in instances){
    result.push(instance.name);
}

result.sort(function (a, b) {
    var aGB = a.split("-")[1];
    var bGB = b.split("-")[1];
    var aNum = parseInt(aGB.split("G")[0]);
    var bNum = parseInt(bGB.split("G")[0]);
    return aNum - bNum;
    return a.toUpperCase() < b.toUpperCase() ? -1 : 1;
});

return result;
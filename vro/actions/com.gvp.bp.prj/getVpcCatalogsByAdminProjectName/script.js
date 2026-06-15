if (!adminProjectName) { throw "adminProjectName cannot be null"; }

var aa = System.getModule("com.gvp").AaManager(true);
var project = aa.get("/iaas/api/projects?$filter=name eq '" + adminProjectName + "'").content[0];
var totalElements = aa.get("/catalog/api/admin/items?projects=" + project.id).totalElements;
var catalogs = aa.get("/catalog/api/admin/items?projects=" + project.id + "&&size=" + totalElements).content;
var result = [];
for each(var catalog in catalogs) {
    var detail = aa.get("/catalog/api/admin/items/" + catalog.id);
    try {
        if (detail.schema.properties._metadata_main_catalog && detail.schema.properties._metadata_main_catalog.default != "Policy") {
            result.push({
                label: catalog.name,
                value: catalog.id,
            });
        }
    } catch (e) {}
}
return result.sort(function (a, b) {
    return a.label.toUpperCase() < b.label.toUpperCase() ? -1 : 1;
});

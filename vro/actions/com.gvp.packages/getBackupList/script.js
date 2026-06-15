var rm = System.getModule("com.gvp").ResourceManager();
var result = [];
for each(var cat in Server.getResourceElementCategoryWithPath("/GVP/Backup").subCategories) {
    result.push(cat.name);
}
return result.sort(function (a, b) {
    return a > b ? -1 : 1;
});
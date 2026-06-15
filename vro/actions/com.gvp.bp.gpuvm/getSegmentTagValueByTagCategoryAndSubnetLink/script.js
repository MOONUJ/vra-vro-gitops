if (!category) { return null; }
if (!subnetLink || subnetLink == '') { return null; }

var checker = category;
var aa = System.getModule("com.gvp").AaManager();
var network = aa.get(subnetLink);
if(network.tags){
    for each(var tagObj in network.tags){
        if(tagObj.key == checker) { return tagObj.value;} 
    }
    
}
//throw "could not find tag"
/*
for each(var tagObj in aa.getUerp(subnetLink).expandedTags) {
    if (tagObj.tag.indexOf(checker) > -1) { return tagObj.tag.split("\n")[1]; }
}
throw "could not find tag";
*/
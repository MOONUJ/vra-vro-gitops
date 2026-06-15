var aa = System.getModule("com.gvp").AaManager(true);

function extractId(href) {
    if (!href || typeof href !== "string") return "";
    var parts = href.split("/");
    return parts[parts.length - 1];
}
var targetRegionId = extractId(cloudZoneLink);

var resp  = aa.get("/iaas/api/zones?$page=0&$pageSize=500");
var zones = (resp && resp.content && resp.content.forEach) ? resp.content
          : (resp && resp.forEach ? resp : []);

System.log("[DEBUG] fetched zones: " + zones.length);

for each (var zone in zones) {
    var zoneRegionHref = zone && zone._links && zone._links.region ? zone._links.region.href : null;
    if (!zoneRegionHref) continue;

    var zoneRegionId = extractId(zoneRegionHref);
    var regionMatch = (zoneRegionHref === cloudZoneLink) || (zoneRegionId && zoneRegionId === targetRegionId);
    if (!regionMatch) continue;

    var tags = zone.tags || [];
    for each (var tag in tags) {
        if (tag && tag.key === category && tag.value !== null && tag.value !== undefined) {
            System.log("[DEBUG] matched zone: " + zone.name + ", " + category + "=" + tag.value);
            return String(tag.value);
        }
    }
}

System.log("[DEBUG] no match, return empty string");
return "";

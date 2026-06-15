// 입력 검증
if (!projectId) {
    System.log("Error: projectId cannot be null");
    throw "projectId cannot be null";
}

var aa = System.getModule("com.gvp").AaManager(true); // 모듈명 확인

var result = [];

try {
    var projectResp = aa.get("/iaas/api/projects/" + projectId);
    var project = projectResp.content ? projectResp.content : projectResp;

    if (!project || !project.zones || project.zones.length === 0) {
        System.log("No zones found for project: " + projectId);
        return [];
    }

    for (var i = 0; i < project.zones.length; i++) {
        var zoneInfo = project.zones[i];
        var zoneId = zoneInfo.zoneId || zoneInfo.id;
        if (!zoneId) continue;

        try {
            var zoneResp = aa.get("/iaas/api/zones/" + zoneId);
            var zone = zoneResp.content ? zoneResp.content : zoneResp;

            if (zone && zone.name) {
                var zoneName = zone.name;
                var regionHref = zone._links && zone._links.region ? zone._links.region.href : "";
                if (regionHref) {
                    result.push({ label: zoneName, value: regionHref });
                } else {
                    System.log("Zone " + zoneName + " has no region information");
                }
            } else {
                System.log("Zone " + zoneId + " has no name");
            }
        } catch (e) {
            System.log("Failed to get zone " + zoneId + ": " + (e.message || e));
            continue;
        }
    }

    result.sort(function(a, b) {
        return a.label.toUpperCase() < b.label.toUpperCase() ? -1 : 1;
    });

    System.log("Zones for project " + projectId + ":\n" + JSON.stringify(result, null, 2));
    return result;

} catch (e) {
    System.log("Failed to get project: " + (e.message || e));
    throw e;
}

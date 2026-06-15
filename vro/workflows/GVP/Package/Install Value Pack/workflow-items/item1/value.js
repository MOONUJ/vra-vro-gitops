var aa = System.getModule("com.gvp").AaManager(true);
var cf = System.getModule("com.gvp").ConfManager();

var vroEndpointId = null;
// Orch 확인
for each(var content in aa.get("/iaas/api/integrations?apiVersion=2021-07-15").content) {
    System.log(JSON.stringify(content, null, 2));
    // Orch Url 이 VCF9에서 embeded 로 바뀜
    if (content.integrationType == "vro" && (content.integrationProperties.hostName.indexOf(aaHostName) > -1  || content.integrationProperties.hostName.indexOf("embedded.orchestrator") > -1 ) ) {
        content = aa.getUerp("/resources/endpoints/" + content.id);
        vroEndpointId = content.documentSelfLink.split("/endpoints/")[1]
        // vro의 data collection
        aa.post("/provisioning/resource-enumeration-tasks", {
            endpointState: content,
            endpointLink: content.documentSelfLink,
            parentComputeLink: content.computeLink,
            resourcePoolLink: content.resourcePoolLink,
            tenantLinks: content.tenantLinks,
            enumerationAction: "START",
            expirationPolicy: "EXPIRE_AFTER_ONE_DAY",
            isSkipEnum: false,
            options: [
                "PRESERVE_MISSING_RESOUCES",
                "SELF_DELETE_ON_COMPLETION"
            ],
            adapterManagementReference: "",
            facadeEndpointLink: "",
            regionIds: []
        });
        break;
    }
}

//  vro integration 없으면 에러 발생
if (!vroEndpointId) { throw "could not found embedded-VRO"; }

// vro data collection이 완료 됐는지 기다림
for (var i = 0; i < 12; i++) {
    System.sleep(5000);
    var vroEndpointStatus = aa.get("/iaas/api/integrations/" + vroEndpointId + "?apiVersion=2021-07-15");
    if (vroEndpointStatus.customProperties.enumerationTaskState == "FINISHED") {
        System.log("embedded-VRO is synced");
        break;
    }
    if (i == 11) {
        throw "could not sync embedded-VRO";
    }
}


// register configurations
for each ( var content in cloudAccounts){
    try{
        cf.save("GVP/Endpoint/" + content.hostname.split(".")[0], {
            hostname: content.hostname,
            username: content.username,
            password: content.password
        });
        System.log("register GVP/Endpoint/" + content.hostname);
    } catch (e) {
        System.log("already registered GVP/Endpoint/" + content.hostname);
    }

}
/*
for each(var content in aa.get("/iaas/api/cloud-accounts").content) {
    try {
        var hostname = content.cloudAccountProperties.hostName.split(".")[0];
        var username = content.cloudAccountProperties.privateKeyId;
        cf.save("GVP/Endpoint/" + hostname, {
            hostname: content.cloudAccountProperties.hostName,
            username: username,
            password: "change_me"
        });
        System.log("register GVP/Endpoint/" + hostname);
    } catch (e) { System.log("already registered GVP/Endpoint/" + hostname); }
}
*/



// register custom naming rules
try {
    aa.post("/provisioning/naming", {
        name: "GVP",
        description: "Default Naming",
        scope: "organization",
        templates: [
            {resourceType: "COMPUTE", resourceTypeName: "Machine", name: null, pattern: "${resource.name}", startCounter: 1, incrementStep: 1, resourceDefault: true, uniqueName: true, staticPattern: "", counters: []},
            {resourceType: "NETWORK", resourceTypeName: "Network", name: null, pattern: "${resource.name}", startCounter: 1, incrementStep: 1, resourceDefault: true, uniqueName: false, staticPattern: "", counters: []},
            {resourceType: "COMPUTE_STORAGE", resourceTypeName: "Storage", name: null, pattern: "${resource.name}", startCounter: 1, incrementStep: 1, resourceDefault: true, uniqueName: false, staticPattern: "", counters: []},
            {resourceType: "LOAD_BALANCER", resourceTypeName: "Load Balancer", name: null, pattern: "${resource.name}", startCounter: 1, incrementStep: 1, resourceDefault: true, uniqueName: false, staticPattern: "", counters: []},
            {resourceType: "RESOURCE_GROUP", resourceTypeName: "Resource Group", name: null, pattern: "${resource.name}", startCounter: 1, incrementStep: 1, resourceDefault: true, uniqueName: false, staticPattern: "", counters: []},
            {resourceType: "GATEWAY", resourceTypeName: "Gateway", name: null, pattern: "${resource.name}", startCounter: 1, incrementStep: 1, resourceDefault: true, uniqueName: false, staticPattern: "", counters: []},
            {resourceType: "NAT", resourceTypeName: "NAT", name: null, pattern: "${resource.name}", startCounter: 1, incrementStep: 1, resourceDefault: true, uniqueName: false, staticPattern: "",counters: []},
            {resourceType: "SECURITY_GROUP", resourceTypeName: "Security Group", name: null, pattern: "${resource.name}", startCounter: 1, incrementStep: 1, resourceDefault: true, uniqueName: false, staticPattern: "",counters: []},
            {resourceType: "GENERIC", resourceTypeName: "Generic", name: "Generic", pattern: "${resource.name}", startCounter: 1, incrementStep: 1, resourceDefault: true, uniqueName: false, staticPattern: "",counters: []}
        ],
        projects: [{projectId: "*", projectName: "*",}]
    });
    System.log("register custom naming");
} catch (e) { System.log("already registered custom naming"); }


// zone이 꼭 필요한가? admin 프로젝트에... ok 있으면 넣는거고 없으면 없는거고
// create admin management project
var cloudZones = [];
for each(var zone in aa.get("/iaas/api/zones/").content) { cloudZones.push({zoneId: zone.id}); }
try {
    var adminProject = aa.post("/iaas/api/projects", {
        name: adminProjectName,
        description: "GVP System Project for Cloud Administrators",
        sharedResources: true,
        zoneAssignmentConfigurations: cloudZones,
        placementPolicy: "DEFAULT"
    });
    adminProjectId = adminProject.id;
} catch (e) {
    System.log("project[" + adminProjectName + "] is exists");
    for each(var adminProject in aa.get("/iaas/api/projects?$filter=(name eq '" + adminProjectName + "')").content) {
        if (adminProject.name == adminProjectName) {
            adminProjectId = adminProject.id;
            break;
        }
    }
}
if (!adminProjectId) { throw "could not found admin project"; }


var com = System.getModule("com.gvp").Common();
var currTimeStr = com.getDateTimeString();
var description = "GVP from [" + backupTimeStr + "] to [" + currTimeStr + "]";

var aa = System.getModule("com.gvp").AaManager(true);
var rm = System.getModule("com.gvp").ResourceManager();

var adminProject = aa.get("/iaas/api/projects/" + adminProjectId);

// abx ////////////////////////////////////////////////////////////////////////////////////////////////////////
System.log("start to install abx actions");
var abx = {};
for each(var back in rm.loadJson("GVP/Backup/" + backupTimeStr + "/abx.json")) {
    var action = null;
    for each(var curr in aa.get("/abx/api/resources/actions?$filter=name eq '" + back.name + "'").content) {
        if (curr.name == back.name && curr.projectId == adminProjectId) {
            curr.description = description;
            curr.runtime = back.runtime;
            curr.runtimeVersion = back.runtimeVersion;
            curr.source = back.source;
            curr.entrypoint = back.entrypoint;
            curr.inputs = back.inputs;
            curr.cpuShares = back.cpuShares;
            curr.memoryInMB = back.memoryInMB;
            curr.timeoutSeconds = back.timeoutSeconds;
            curr.deploymentTimeoutSeconds = back.deploymentTimeoutSeconds;
            curr.actionType = back.actionType;
            curr.provider = back.provider;
            curr.system = back.system;
            curr.shared = back.shared;
            curr.asyncDeployed = back.asyncDeployed;
            curr.configuration = back.configuration ? back.configuration : {};
            curr.metadata = back.metadata ? back.metadata : {};
            action = aa.put("/abx/api/resources/actions/" + curr.id, curr);
        }
    }
    if (!action) {
        action = aa.post("/abx/api/resources/actions", {
            name: back.name,
            projectId: adminProjectId,
            description: description,
            runtime: back.runtime,
            runtimeVersion: back.runtimeVersion,
            source: back.source,
            entrypoint: back.entrypoint,
            inputs: back.inputs,
            cpuShares: back.cpuShares,
            memoryInMB: back.memoryInMB,
            timeoutSeconds: back.timeoutSeconds,
            deploymentTimeoutSeconds: back.deploymentTimeoutSeconds,
            actionType: back.actionType,
            provider: back.provider,
            system: back.system,
            shared: back.shared,
            asyncDeployed: back.asyncDeployed,
            configuration: back.configuration ? back.configuration : {},
            metadata: back.metadata ? back.metadata : {}
        });
    }
    abx[action.name] = action;
}

// custom resources ///////////////////////////////////////////////////////////////////////////////////////////
System.log("start to install custom resources");
for each(var back in rm.loadJson("GVP/Backup/" + backupTimeStr + "/cr.json")) {
    var cr = null;
    for each(var curr in aa.get("/form-service/api/custom/resource-types?$filter=resourceType eq '" + back.resourceType + "'").content) {
        if (curr.resourceType == back.resourceType) {
            var additionalActions = [];
            for each(var action in back.additionalActions) {
                action.orgId = null;
                if (action.runnableItem.type == "vro.workflow") {
                    action.runnableItem.endpointLink = aa.get("/vro/workflows/" + action.runnableItem.id).integration.endpointConfigurationLink;
                } else {
                    action.runnableItem.id = abx[action.runnableItem.name].id;
                    action.runnableItem.projectId = adminProjectId;
                }
                action.formDefinition.id = null;
                action.formDefinition.tenant = null;
                action.formDefinition.externalSourceFormSchemas = null;
                action = aa.post("/form-service/api/custom/resource-actions?generateUnvalidatableExternalValuesSchema=true", action);
                additionalActions.push(action);
            }
            curr.displayName = back.displayName;
            curr.description = description;
            curr.resourceType = back.resourceType;
            curr.status = back.status;
            curr.schemaType = back.schemaType;
            curr.properties = back.properties;
            curr.additionalActions = additionalActions;
            curr.mainActions.create = {
                id: abx[back.mainActions.create.name].id,
                name: back.mainActions.create.name,
                type: back.mainActions.create.type,
                inputParameters: back.mainActions.create.inputParameters,
                projectId: adminProjectId
            }
            curr.mainActions.read = {
                id: abx[back.mainActions.read.name].id,
                name: back.mainActions.read.name,
                type: back.mainActions.read.type,
                inputParameters: back.mainActions.read.inputParameters,
                projectId: adminProjectId
            }
            curr.mainActions.delete = {
                id: abx[back.mainActions.delete.name].id,
                name: back.mainActions.delete.name,
                type: back.mainActions.delete.type,
                inputParameters: back.mainActions.delete.inputParameters,
                projectId: adminProjectId
            }
            if (back.mainActions.update) {
                curr.mainActions.update = {
                    id: abx[back.mainActions.update.name].id,
                    name: back.mainActions.update.name,
                    type: back.mainActions.update.type,
                    inputParameters: back.mainActions.update.inputParameters,
                    projectId: adminProjectId
                }
            } else {
                back.mainActions.update = null;
            }
            cr = aa.post("/form-service/api/custom/resource-types", curr);
            break;
        }
    }
    if (!cr) {
        back.id = null;
        back.orgId = null;
        back.description = description;
        for each(var action in back.additionalActions) {
            action.orgId = null;
            if (action.runnableItem.type == "vro.workflow") {
                action.runnableItem.endpointLink = aa.get("/vro/workflows/" + action.runnableItem.id).integration.endpointConfigurationLink;
            } else {
                action.runnableItem.id = abx[action.runnableItem.name].id;
                action.runnableItem.projectId = adminProjectId;
            }
            action.runnableItem.projectId = adminProjectId;
            action.formDefinition.id = null;
            action.formDefinition.tenant = null;
            action.formDefinition.externalSourceFormSchemas = null;
        }
        back.mainActions.create = {
            id: abx[back.mainActions.create.name].id,
            name: back.mainActions.create.name,
            type: back.mainActions.create.type,
            inputParameters: back.mainActions.create.inputParameters,
            projectId: adminProjectId
        }
        back.mainActions.read = {
            id: abx[back.mainActions.read.name].id,
            name: back.mainActions.read.name,
            type: back.mainActions.read.type,
            inputParameters: back.mainActions.read.inputParameters,
            projectId: adminProjectId
        }
        back.mainActions.delete = {
            id: abx[back.mainActions.delete.name].id,
            name: back.mainActions.delete.name,
            type: back.mainActions.delete.type,
            inputParameters: back.mainActions.delete.inputParameters,
            projectId: adminProjectId
        }
        if (back.mainActions.update) {
            back.mainActions.update = {
                id: abx[back.mainActions.update.name].id,
                name: back.mainActions.update.name,
                type: back.mainActions.update.type,
                inputParameters: back.mainActions.update.inputParameters,
                projectId: adminProjectId
            }
        } else {
            back.mainActions.update = null;
        }
        cr = aa.post("/form-service/api/custom/resource-types", back);
    }
}

// blueprint //////////////////////////////////////////////////////////////////////////////////////////////////
System.log("start to install blueprints");
for each(var back in rm.loadJson("GVP/Backup/" + backupTimeStr + "/blueprint.json")) {
    var blueprint = null;
    for each(var curr in aa.get("/blueprint/api/blueprints?projects=" + adminProjectId + "&name=" + back.name).content) {
        if (curr.name == back.name) {
            curr.description = back.description;
            curr.content = back.content;
            curr.requestScopeOrg = true;
            // curr.iconId
            blueprint = aa.put("/blueprint/api/blueprints/" + curr.id, curr);
            break;
        }
    }
    if (!blueprint) {
        blueprint = aa.post("/blueprint/api/blueprints", {
            projectId: adminProjectId,
            name: back.name,
            description: back.description,
            content: back.content,
            requestScopeOrg: true
        });
    }
    for each(var item in aa.get("/blueprint/api/blueprints/" + blueprint.id + "/versions").content) {
        if (item.status == "RELEASED") {
            item.status = "VERSIONED";
            aa.post("/blueprint/api/blueprints/" + blueprint.id + "/versions/" + item.id + "/actions/unrelease", item);
        }
    }
    var version = aa.post("/blueprint/api/blueprints/" + blueprint.id + "/versions", {
        version: currTimeStr,
        description: description,
        release: true
    });
}
var contentSource = null;
for each(var source in aa.get("/catalog/api/admin/sources").content) {
    if (source.projectId == adminProjectId) {
        contentSource = aa.post("/catalog/api/admin/sources", source);
        break;
    }
}
if (!contentSource) {
    contentSource = aa.post("/catalog/api/admin/sources", {
        name: adminProject.name,
        typeId: "com.vmw.blueprint",
        config: {sourceProjectId: adminProjectId}
    });
}

// resource actions ///////////////////////////////////////////////////////////////////////////////////////////
System.log("start to install resource actions");
for each(var back in rm.loadJson("GVP/Backup/" + backupTimeStr + "/ra.json")) {
    back.description = description;
    back.orgId = null;
    if (back.runnableItem.type == "vro.workflow") {
        back.runnableItem.endpointLink = aa.get("/vro/workflows/" + back.runnableItem.id).integration.endpointConfigurationLink;
    } else {
        back.runnableItem.id = abx[back.runnableItem.name].id;
        back.runnableItem.projectId = adminProjectId;
    }
    back.formDefinition.id = null;
    back.formDefinition.tenant = null;
    back.formDefinition.externalSourceFormSchemas = null;
    aa.post("/form-service/api/custom/resource-actions?generateUnvalidatableExternalValuesSchema=true", back);
}

// subscriptions //////////////////////////////////////////////////////////////////////////////////////////////
System.log("start to install subscriptions");
for each(var back in rm.loadJson("GVP/Backup/" + backupTimeStr + "/sub.json")) {
    var sub = null;
    for each(var curr in aa.get("/event-broker/api/subscriptions?$filter=name eq '" + back.name + "'").content) {
        if (curr.name == back.name) {

            // System.log(aa.get("/vro/workflows/" + back.runnableId).integration.endpointConfigurationLink);

            // System.log(JSON.stringify(aa.get("/vro/workflows/" + back.runnableId), null, 2));

            // System.log(JSON.stringify(aa.getUerp(aa.get("/vro/workflows/" + back.runnableId).integration.endpointConfigurationLink), null, 2))

            curr.description = description;
            curr.type = back.type;
            curr.disabled = false;
            curr.eventTopicId = back.eventTopicId;
            curr.blocking = back.blocking;
            curr.contextual = back.contextual;
            curr.criteria = back.criteria;
            curr.runnableType = back.runnableType;
            curr.runnableId = back.runnableId;            
            curr.timeout = back.timeout;
            curr.priority = back.priority;
            curr.recoverRunnableType = back.recoverRunnableType;
            curr.recoverRunnableId = back.recoverRunnableId;
            curr.constraints = back.constraints;
            aa.post("/event-broker/api/subscriptions", curr);
            sub = true;
            break;
        }
    }
    if (!sub) {
        back.orgId = null;
        back.subscriberId = null;
        back.description = description;
        aa.post("/event-broker/api/subscriptions", back);
    }
}

// form ///////////////////////////////////////////////////////////////////////////////////////////////////////
System.log("start to install catalog forms");
for each(var back in rm.loadJson("GVP/Backup/" + backupTimeStr + "/form.json")) {
    for each(var catalog in aa.get("/catalog/api/admin/items?search=" + back.formName).content) {
        if (back.formName == catalog.name) {
            aa.post("/form-service/api/forms?generateUnvalidatableExternalValuesSchema=true", {
                name: back.formName,
                type: "requestForm",
                sourceId: catalog.id,
                sourceType: back.sourceType,
                status: "ON",
                form: JSON.stringify(back.form)
            });
            break;
        }
    }
}

// workflow //////////////////////////////////////////
System.log("start to install workflow sources");

var workflow = null;
var wfSource = aa.get("/catalog/api/admin/sources?typeId=com.vmw.vro.workflow").content;
if(wfSource.length > 0){
    System.log("Already Exist Workflow Source");
    var backData = [];
    for each(var back in rm.loadJson("GVP/Backup/" + backupTimeStr + "/workflow.json")) {
        var wf = aa.get("/vro/workflows?$filter=name eq '" + back.name + "'").content[0];
        backData.push({
            "id": wf.id,
            "name": wf.name,
            "version": wf.version,
            "integration": wf.integration
        });

    }
    wfSource[0].config.workflows = backData 
    aa.post("/catalog/api/admin/sources", wfSource[0])
} else {
    System.log("Create New Workflow Source")
    var backData = [];
    for each(var back in rm.loadJson("GVP/Backup/" + backupTimeStr + "/workflow.json")) {
        var wf = aa.get("/vro/workflows?$filter=name eq '" + back.name + "'").content[0];
        backData.push({
            "id": wf.id,
            "name": wf.name,
            "version": wf.version,
            "integration": wf.integration
        });
    }

    var data = {
        "config": {
            "workflows": backData
        },
        "description": "GVP VRO Content Source",
        "global": true,
        "name": "GVP VRO",
        "typeId": "com.vmw.vro.workflow"
    }
    aa.post("/catalog/api/admin/sources", data);
}


// workflows forms////////////////////////////////////
System.log("start to install Workflow catalog forms");
for each(var back in rm.loadJson("GVP/Backup/" + backupTimeStr + "/workflowForm.json")) {
    for each(var catalog in aa.get("/catalog/api/admin/items?search=" + back.formName).content) {
        if (back.formName == catalog.name) {
            aa.post("/form-service/api/forms?generateUnvalidatableExternalValuesSchema=true", {
                name: back.formName,
                type: "requestForm",
                sourceId: catalog.id,
                sourceType: back.sourceType,
                status: "ON",
                form: JSON.stringify(back.form)
            });
            break;
        }
    }
}

/*
// project policy /////////////////////////////////////////////////////////////////////////////////////////////
System.log("start to register project policy");
var projectCatalogId = null;
var catalogs = aa.get("/catalog/api/admin/items").content.filter( function (i) { return i.name.indexOf("Project") > -1})
for each(var catalog in aa.get("/catalog/api/admin/items?search=ClovirONE_Project").content) {
    if (catalog.name == "Project") {
        projectCatalogId = catalog.id;
        break;
    }
}
if (!projectCatalogId) { throw "could not found project catalog"; }

var projectSharing = null;
for each(var policy in aa.get("/policy/api/policies?search=gvp-prime-project-sharing").content) {
    if (policy.name == "gvp-prime-project-sharing") {
        projectSharing = policy;
        break;
    }
}
if (!projectSharing) {
    aa.post("/policy/api/policies", {
        projectId: primeProjectId,
        name: "gvp-prime-project-sharing",
        description: "GVP System Project Policy for Project Owners",
        typeId: "com.vmware.policy.catalog.entitlement",
        enforcementType: "HARD",
        definition: {
            entitledUsers: [{
                userType: "USER",
                principals: [{
                    type: "PROJECT",
                    referenceId: ""
                }],
                items: [{
                    id: projectCatalogId,
                    type: "CATALOG_ITEM_IDENTIFIER"
                }]
            }]
        }
    });
}
*/

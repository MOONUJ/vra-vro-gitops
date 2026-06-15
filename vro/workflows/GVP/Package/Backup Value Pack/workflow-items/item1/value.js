var com = System.getModule("com.gvp").Common();
var timeStr = com.getDateTimeString();

var aa = System.getModule("com.gvp").AaManager(true);
var rm = System.getModule("com.gvp").ResourceManager();

// workflow content & catalog & form
var workflows = {};
var workflowForms = {};
for each( var wfSource in aa.get("/catalog/api/admin/sources?typeId=com.vmw.vro.workflow").content[0].config.workflows){
    workflows[wfSource.id] = wfSource;
    
    for each(var forms in aa.get("/form-service/api/forms/search?term=" + wfSource.name).content) {
        var f = aa.get("/form-service/api/forms/" + forms.formId);
        if(f.status == "ON"){
            workflowForms[wfSource.id] = forms;
        }
    }
}
rm.saveJson("GVP/Backup/" + timeStr + "/workflow.json", workflows);
rm.saveJson("GVP/Backup/" + timeStr + "/workflowForm.json", workflowForms);

// blueprint & catalog & form
var blueprints = {};
var forms = {};
for each(var blueprint in aa.get("/blueprint/api/blueprints?projects=" + projectId).content) {
    var lastVersionId = null;
    var lastUpdated = "1900-01-01T01:01:01.000000Z";
    for each(var version in aa.get("/blueprint/api/blueprints/" + blueprint.id + "/versions").content) {
        if (version.status == "RELEASED" && version.updatedAt > lastUpdated) {
            lastVersionId = version.id;
            lastUpdated = version.updatedAt;
        }
    }
    if (lastVersionId) {
        blueprints[blueprint.id] = aa.get("/blueprint/api/blueprints/" + blueprint.id + "/versions/" + lastVersionId);
        for each(var catalog in aa.get("/catalog/api/admin/items?search=" + blueprint.name).content) {
            if (catalog.name == blueprint.name) {
                for each(var form in aa.get("/form-service/api/forms/search?term=" + blueprint.name).content) {
                    if (form.formName == blueprint.name) {
                        forms[blueprint.id] = form;
                        break;
                    }
                }
                break;
            }
        }
    }
}
rm.saveJson("GVP/Backup/" + timeStr + "/blueprint.json", blueprints);
rm.saveJson("GVP/Backup/" + timeStr + "/form.json", forms);

// abx
abx = {};
for each(var action in aa.get("/abx/api/resources/actions?size=1000").content) {
    try {
        abx[action.id] = aa.get("/abx/api/resources/actions/" + action.id + "?projectId=" + projectId);
    } catch (e) {
        System.error("Could not get " + action.id + ": " + e);
    }
}
rm.saveJson("GVP/Backup/" + timeStr + "/abx.json", abx);

// custom resource
var cr = {};
for each(var resource in aa.get("/form-service/api/custom/resource-types?size=1000").content) {
    cr[resource.id] = aa.get("/form-service/api/custom/resource-types/" + resource.id);
}
rm.saveJson("GVP/Backup/" + timeStr + "/cr.json", cr);

// resource action
var ra = {};
for each(var action in aa.get("/form-service/api/custom/resource-actions?size=1000").content) {
    ra[action.id] = aa.get("/form-service/api/custom/resource-actions/" + action.id);
}
rm.saveJson("GVP/Backup/" + timeStr + "/ra.json", ra);

// subscription
var sub = {};
for each(var s in aa.get("/event-broker/api/subscriptions?size=1000&$filter=type eq 'RUNNABLE'").content) {
    sub[s.id] = aa.get("/event-broker/api/subscriptions/" + s.id);
}
rm.saveJson("GVP/Backup/" + timeStr + "/sub.json", sub);
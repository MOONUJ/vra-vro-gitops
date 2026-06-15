var adminUsername = "mujtest03";
var adminPassword = "mujtest03";
var computeName = 'mujtest03';

var aa = System.getModule("com.gvp").AaManager(true);
var vm = VcPlugin.getAllVirtualMachines(null, "xpath:name='" + computeName + "'")[0];
var guestOperationsManager = vm.sdkConnection.guestOperationsManager;
var guestAuth = new VcNamePasswordAuthentication();
guestAuth.username = adminUsername;
guestAuth.password = adminPassword;

try {
    guestOperationsManager.authManager.validateCredentialsInGuest(vm, guestAuth);
} catch (e){
    System.log(e);
    throw "Failed to authenticate with the Virtual Machine";
}

var execScripts = System.getModule("com.gvp").execScripts;
var vcConf = System.getModule("com.gvp").ConfManager().load("GVP/Endpoint/vcenter");
var scripts = '#!/bin/bash\n'
scripts += 'if sudo -n true 2>/dev/null; then\n';
scripts += '  sudo mkdir /telegraf\n';
scripts += '  sudo chown ' + adminUsername +' /telegraf\n';
scripts += '  echo "0"\n';
scripts += 'else\n';
scripts += '  echo "126"\n';
scripts += 'fi';

try{
    var result = execScripts(vcConf.hostname, vcConf.username, vcConf.password, computeName, adminUsername, adminPassword, scripts);
} catch (e) {
    System.log(e);
    throw e;
}
System.log(result);
if(result == 126){
    throw "User doesn't have sudo permission";
}

var vcoDir = System.getTempDirectory();
var fileName = "telegraf-1.35.4_linux_amd64.tar.gz"; // input으로 이동
var vcoPath = vcoDir +  "/" + fileName;
var srcFile = new File(vcoPath);
var guestFilePath = "/telegraf/" + fileName;
var overwrite = true;
var fileManager = guestOperationsManager.fileManager;
var attr = new VcGuestFileAttributes();

if(srcFile.exists == false){
    /*
    var exec = System.getModule("com.gvp").execPyUrl;

    aa.post("/vco/api/actions/com.gvp/uploadFiletoVco/executions",{
        parameters:[
            {
                "name": "mime",
                "type": "MimeAttachment",
                "value": {
                    "mime-attachment": {
                        "name": "nginx.zip",
                        "mime-type": "application/zip",
                        "content": exec("GET", "http://10.200.1.14:8081/repository/raw-hosted/app/linux/telegraf/telegraf-1.35.4_linux_amd64.tar.gz", null, {})
                    }
                }
            }
        ]
    });
    srcFile = new File(vcoPath);
    */
    var vcoTempDirPath = System.getTempDirectory()
    var file = new File(fileName="/usr/lib/vco/app-server/temp/" + mimeAttach.name);
    if(file.exists == false){
        try {
            mimeAttach.write(vcoTempDirPath);
        } catch (e) {
            throw e;
        }
    } else {
        var file = new File(fileName="/usr/lib/vco/app-server/temp/" + mimeAttach.name);
        if(file.exists == false){
            throw "Cloud not Uploaded File to VCO"
        }
    }
}
var uri = fileManager.initiateFileTransferToGuest(vm , guestAuth ,guestFilePath, attr, srcFile.length, overwrite);
var filePutResult = fileManager.putFile(vcoPath, uri);













//* ****************************************************************** */

/*
var vcoTempDirPath = System.getTempDirectory()
var file = new File(fileName="/usr/lib/vco/app-server/temp/" + mime.name);
if(file.exists == false){
    try {
        mime.write(vcoTempDirPath);
    } catch (e) {
        throw e;
    }
} else {
    var file = new File(fileName="/usr/lib/vco/app-server/temp/" + mime.name);
    if(file.exists == false){
        throw "Cloud not Uploaded File to VCO"
    }
}

return file.exists
*/
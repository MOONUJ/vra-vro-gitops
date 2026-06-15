var aa = System.getModule("com.gvp").AaManager(true);
var machine = aa.get("/iaas/api/machines/" + resourceId);
var computeName = machine.name;
var cloudAccount = aa.get("/iaas/api/cloud-accounts/" + machine.cloudAccountIds[0]);
var machineVcName = cloudAccount.cloudAccountProperties.hostName.split(".")[0];
var vm = VcPlugin.getAllVirtualMachines(null, "xpath:name='" + computeName + "'")[0];
var guestOperationsManager = vm.sdkConnection.guestOperationsManager;
var guestAuth = new VcNamePasswordAuthentication();
guestAuth.username = adminUsername;
guestAuth.password = adminPassword;

try {
    System.log("Check Account Authenticate");
    guestOperationsManager.authManager.validateCredentialsInGuest(vm, guestAuth);
} catch (e){
    System.log(e);
    throw "Failed to authenticate with the Virtual Machine";
}

System.log("Check Account Permission");
var execScripts = System.getModule("com.gvp").execScripts;
var vcConf = System.getModule("com.gvp").ConfManager().load("GVP/Endpoint/" + machineVcName);
var scripts = '#!/bin/bash\n';
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
var fileName = filePath.split("/").filter( function(item){ return item.indexOf("tar.gz") >= 0})[0]
var vcoPath = vcoDir +  "/" + fileName;
var srcFile = new File(vcoPath);
var guestFilePath = "/telegraf/" + fileName;
var overwrite = true;
var fileManager = guestOperationsManager.fileManager;
var attr = new VcGuestFileAttributes();

if(srcFile.exists == false){
    try{
        System.log("get package file from portal VM")
        var host = portalMachine.sdkConnection;

        var portalGuestOperationsManager = host.guestOperationsManager;
        var portalGuestAuth = new VcNamePasswordAuthentication();
        portalGuestAuth.username = portalUsername;
        portalGuestAuth.password = portalPassword;

        var portalFileManager = portalGuestOperationsManager.fileManager;
        result = false;
        var ftInfo = portalFileManager.initiateFileTransferFromGuest(portalMachine , portalGuestAuth ,filePath);
        result = portalFileManager.downloadFile(vcoPath, ftInfo);
        srcFile = new File(vcoPath);
    } catch(e){
        throw e;
    }

}

try{
    System.log("Upload package file to target VM")
    var uri = fileManager.initiateFileTransferToGuest(vm , guestAuth ,guestFilePath, attr, srcFile.length, overwrite);
    var filePutResult = fileManager.putFile(vcoPath, uri);
} catch (e) {
    throw e;
}

var uuid = System.nextUUID();
var installScript = '#!/bin/bash\n';
installScript += 'FILE_PATH="' + guestFilePath +'"\n';
installScript += 'tar -zxvf "$FILE_PATH" -C /telegraf\n';
installScript += 'chmod +x "/telegraf/install_telegraf.sh"\n';
installScript += 'sudo bash -c "/telegraf/install_telegraf.sh ' + cloudProxy + ' ' + computeName + ' root ' + uuid + '"\n';



try{
    System.log("start install")
    var result = execScripts(vcConf.hostname, vcConf.username, vcConf.password, computeName, adminUsername, adminPassword, installScript);
    System.log(result);
} catch (e) {
    System.log(e);
    throw e;
}














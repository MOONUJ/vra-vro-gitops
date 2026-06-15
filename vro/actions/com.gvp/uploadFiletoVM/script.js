if(!vm || !guestUsername || !guestPassword || !mimeAttachment || !guestDirPath){
    throw "cannot empty input properties";
};

// VM 상태 검증
if (vm.runtime.powerState.value != "poweredOn") {
    throw "VM이 powered on 상태가 아닙니다. 현재 상태: " + vm.runtime.powerState.value;
}

if (vm.guest.toolsRunningStatus != "guestToolsRunning") {
    throw "VMware Tools가 실행 중이 아닙니다. 상태: " + vm.guest.toolsRunningStatus;
}

// GuestOperationsManager 가져오기
var vcHost = vm.sdkConnection;
var guestOpsManager = vcHost.guestOperationsManager;
var processManager = guestOpsManager.getProcessManager();
var fileManager = guestOpsManager.fileManager;

// 인증 정보 설정
var guestAuth = new VcNamePasswordAuthentication();
guestAuth.username = guestUsername;
guestAuth.password = guestPassword;
guestAuth.interactiveSession = false;

// 게스트 OS 타입 확인
var guestFamily = vm.guest.guestFamily;
var isWindows = (guestFamily && guestFamily.toLowerCase().indexOf("windows") >= 0);

// VRO 로컬 임시 파일 경로에 write
mimeAttachment.write(System.getTempDirectory());
var vcoFilePath = System.getTempDirectory() + "/" +mimeAttachment.name


// VM에 File Upload
try {
    // 1. vRO 로컬에 업로드된 파일에 대한 File Object 생성
    var file = new File(vcoFilePath);

    // 2. 게스트 OS로 파일 업로드
    var attr = new VcGuestFileAttributes();
    var guestPath = isWindows? guestDirPath + "\\" + mimeAttachment.name : guestDirPath + "/" + mimeAttachment.name;
    System.log("GuestOS Upload Directory Path is : " + guestPath);
    var uri = fileManager.initiateFileTransferToGuest(
        vm, 
        guestAuth, 
        guestPath, 
        attr, 
        file.length, 
        true  // overwrite
    );
    var uploadResult = fileManager.putFile(vcoFilePath, uri);
    if (!uploadResult) {
        throw "파일 업로드 실패";
    }
    System.log("파일 업로드 완료");

    // 3. VRO 로컬에 업로드 된 파일 정리
    try {
        file.deleteFile();
        System.log("vRO 로컬 파일 정리 완료");
    } catch (localCleanupError) {
        System.warn("vRO 로컬 파일 정리 실패 (무시): " + localCleanupError);
    }


} catch (error) {
    // 오류 시 정리 시도
    try {
        fileManager.deleteFileInGuest(vm, guestAuth, guestDirPath);
    } catch (e) {}
    
    try {
        if (vcoScriptPath) {
            var cleanupFile = new File(vcoScriptPath);
            cleanupFile.deleteFile();
        }
    } catch (e) {}
    
    throw "스크립트 실행 오류: " + error;
} 
if(!vm || !guestUsername || !guestPassword || !scriptText){
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
var scriptType = isWindows ? "powershell" : "bash";

// 스크립트 설정
var timestamp = new Date().getTime();
var tempScriptPath, interpreterPath, interpreterArgs, outputFile;
var vcoScriptPath; // vRO 로컬 임시 파일 경로

if (scriptType.toLowerCase() == "powershell") {
    tempScriptPath = "C:\\Windows\\Temp\\vro_script_" + timestamp + ".ps1";
    outputFile = "C:\\Windows\\Temp\\vro_output_" + timestamp + ".txt";
    vcoScriptPath = System.getTempDirectory() + "/vro_script_" + timestamp + ".ps1";
    interpreterPath = "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe";
    interpreterArgs = "-ExecutionPolicy Bypass -NonInteractive -NoProfile -File \"" + tempScriptPath + "\"";
} else if (scriptType.toLowerCase() == "bash") {
    tempScriptPath = "/tmp/vro_script_" + timestamp + ".sh";
    outputFile = "/tmp/vro_output_" + timestamp + ".txt";
    vcoScriptPath = System.getTempDirectory() + "/vro_script_" + timestamp + ".sh";
    interpreterPath = "/bin/bash";
    interpreterArgs = "\"" + tempScriptPath + "\"";
} else {
    throw "지원하지 않는 스크립트 타입: " + scriptType;
}

System.log("스크립트 타입: " + scriptType);
System.log("게스트 스크립트 경로: " + tempScriptPath);
System.log("게스트 출력 경로: " + outputFile);

try {
    // 1. vRO 로컬에 임시 스크립트 파일 생성
    var scriptFile = new File(vcoScriptPath);
    if (!scriptFile) {
        throw "vRO 로컬 임시 파일 생성 실패: " + vcoScriptPath;
    }
    scriptFile.write(scriptText);
    System.log("vRO 로컬 스크립트 파일 생성 완료: " + vcoScriptPath);
    
    // 2. 게스트 OS로 스크립트 파일 업로드
    var attr = new VcGuestFileAttributes();
    var uri = fileManager.initiateFileTransferToGuest(
        vm, 
        guestAuth, 
        tempScriptPath, 
        attr, 
        scriptFile.length, 
        true  // overwrite
    );
    
    var uploadResult = fileManager.putFile(vcoScriptPath, uri);
    if (!uploadResult) {
        throw "스크립트 파일 업로드 실패";
    }
    System.log("스크립트 파일 업로드 완료");
    
    // 3. 스크립트 실행 (출력을 outputFile로 리다이렉션)
    var programSpec = new VcGuestProgramSpec();
    programSpec.programPath = interpreterPath;
    
    if (scriptType.toLowerCase() == "powershell") {
        programSpec.arguments = interpreterArgs + " | Out-File -FilePath '" + outputFile + "' -Encoding UTF8 -Force";
    } else {
        programSpec.arguments = interpreterArgs + " > " + outputFile + " 2>&1";
    }
    
    var pid = processManager.startProgramInGuest(vm, guestAuth, programSpec);
    System.log("프로세스 시작. PID: " + pid);
    
    // 4. 프로세스 완료 대기
    var maxWaitTime = 300; // 5분
    var waitInterval = 2;
    var elapsedTime = 0;
    var processInfo = null;
    
    while (elapsedTime < maxWaitTime) {
        System.sleep(waitInterval * 1000);
        elapsedTime += waitInterval;
        
        var pids = [pid];
        var processes = processManager.listProcessesInGuest(vm, guestAuth, pids);
        
        if (processes && processes.length > 0) {
            processInfo = processes[0];
            
            if (processInfo.endTime != null) {
                System.log("프로세스 완료. Exit Code: " + processInfo.exitCode);
                break;
            }
        }
    }
    
    if (!processInfo || processInfo.endTime == null) {
        throw "스크립트 실행 시간 초과 (" + maxWaitTime + "초)";
    }
    
    if (processInfo.exitCode != 0) {
        System.warn("스크립트가 0이 아닌 exit code를 반환했습니다: " + processInfo.exitCode);
    }
    
    // 5. 출력 파일 다운로드
    System.sleep(1000); // 파일 쓰기 완료 대기
    
    var vcoOutputPath = System.getTempDirectory() + "/vro_output_" + timestamp + ".txt";
    var ftInfo = fileManager.initiateFileTransferFromGuest(vm, guestAuth, outputFile);
    
    var downloadResult = fileManager.downloadFile(vcoOutputPath, ftInfo);
    if (!downloadResult) {
        throw "출력 파일 다운로드 실패";
    }
    System.log("출력 파일 다운로드 완료: " + vcoOutputPath);
    
    // 6. 다운로드한 파일 내용 읽기
    var outputFileObj = new FileReader(vcoOutputPath);
    outputFileObj.open();
    var result = outputFileObj.readAll();
    outputFileObj.close();
    System.log("결과 파일 크기: " + result.length + " bytes");
    
    // 7. 임시 파일 정리 (게스트)
    try {
        fileManager.deleteFileInGuest(vm, guestAuth, tempScriptPath);
        fileManager.deleteFileInGuest(vm, guestAuth, outputFile);
        System.log("게스트 임시 파일 정리 완료");
    } catch (cleanupError) {
        System.warn("게스트 임시 파일 정리 실패 (무시): " + cleanupError);
    }
    
    // 8. 임시 파일 정리 (vRO 로컬)
    try {
        scriptFile.deleteFile();
        outputFileObj.deleteFile();
        System.log("vRO 로컬 임시 파일 정리 완료");
    } catch (localCleanupError) {
        System.warn("vRO 로컬 임시 파일 정리 실패 (무시): " + localCleanupError);
    }
    
    return result;
    
} catch (error) {
    // 오류 시 정리 시도
    try {
        fileManager.deleteFileInGuest(vm, guestAuth, tempScriptPath);
        fileManager.deleteFileInGuest(vm, guestAuth, outputFile);
    } catch (e) {}
    
    try {
        if (vcoScriptPath) {
            var cleanupFile = new File(vcoScriptPath);
            cleanupFile.deleteFile();
        }
    } catch (e) {}
    
    throw "스크립트 실행 오류: " + error;
}
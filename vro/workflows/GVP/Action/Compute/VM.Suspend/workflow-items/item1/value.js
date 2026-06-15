var aa = System.getModule("com.gvp").AaManager(true);
var requestIds = [];
for each(var id in resourceId){
    var result = aa.post("/deployment/api/resources/"+id+"/requests",{
        "actionId": "Cloud.vSphere.Machine.Suspend",
    });
    requestIds.push(result.id);
}

var allSuccessful = false;
var count = 0;
while (!allSuccessful) {
    allSuccessful = true; // 매 루프마다 초기화
    var statuses = [];

    for (var i = 0; i < requestIds.length; i++) {
        var requestId = requestIds[i];
        var result = aa.get("/deployment/api/requests/" + requestId);
        statuses.push(result.status);

        if (result.status !== "SUCCESSFUL") {
            allSuccessful = false;
        }
        if (result.status == "FAILED"){
            throw "FAILED : " + result.details
        }
    }

    count++;
    if (count > 10) {
        throw "Waiting Time out"
    }
    // Optional: 너무 빠른 루프 방지
    System.sleep(5000); // 3초 대기 (아래에 sleep 함수 있음)
    
}


function extractGpuModel(profile) {
    // null/undefined 체크
    if (!profile) return null;
    
    // 정규표현식으로 추출
    var match = profile.match(/grid_([a-zA-Z0-9]+)-/);
    return match ? match[1].toUpperCase() : null;
}

if(!gpuProfile) { return null};


return extractGpuModel(gpuProfile);
for each(var host in VraHostManager.findHostsByType(aaConnectionType)) {
    if (host.name == "Admin") {
        return true;
    }
}

return false;
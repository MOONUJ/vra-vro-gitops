for each(var host in VraHostManager.findHostsByType(aaConnectionType)) {
    if (host.name == "Default") {
        aaUrl = host.vraHost;
        aaHostName = host.vraHost.split("://")[1];
        break;
    }
}
if (!aaHostName) { throw "could not found automation endpoint"; }
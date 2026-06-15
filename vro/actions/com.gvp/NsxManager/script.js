return {
    _config: function () {
        var conf = System.getModule("com.gvp").ConfManager().load("GVP/Endpoint/" + endpoint);
        return {
            baseUrl: "https://" + conf.hostname,
            headers: {
                "Authorization": "Basic " + System.getModule("com.gvp").Converter().base64.encode(conf.username + ":" + conf.password),
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        }
    } (),
    _restapi: System.getModule("com.gvp").RestApi(),
    get: function (url) {
        var result = this._restapi.get(this._config.baseUrl + url, this._config.headers);
        try { return JSON.parse(result); } catch(e) { return null; }
    },
    post: function (url, data) {
        var result = this._restapi.post(this._config.baseUrl + url, JSON.stringify(data), this._config.headers);
        try { return JSON.parse(result); } catch(e) { return null; }
    },
    put: function (url, data) {
        var result = this._restapi.put(this._config.baseUrl + url, JSON.stringify(data), this._config.headers);
        try { return JSON.parse(result); } catch(e) { return null; }
    },
    patch: function (url, data) {
        var result = this._restapi.patch(this._config.baseUrl + url, JSON.stringify(data), this._config.headers);
        try { return JSON.parse(result); } catch(e) { return null; }
    },
    delete: function (url) {
        var result = this._restapi.delete(this._config.baseUrl + url, this._config.headers);
        try { return JSON.parse(result); } catch(e) { return null; }
    }
}
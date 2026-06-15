return {
    _config: function () {
        if (!baseUrl) { throw "Error [RestManager] : must be set host parameter"; }
        if (!headers) { headers = new Properties(); }
        headers["Content-Type"] = "application/json";
        headers["Accept"] = "application/json";
        return {
            baseUrl: baseUrl,
            headers: headers
        }
    } (),
    _restapi: System.getModule("com.gvp").RestApi(),
    get: function (url) { return JSON.parse(this._restapi.get(this._config.baseUrl + url, this._config.headers)); },
    post: function (url, data) { return JSON.parse(this._restapi.post(this._config.baseUrl + url, JSON.stringify(data), this._config.headers)); },
    put: function (url, data) { return JSON.parse(this._restapi.put(this._config.baseUrl + url, JSON.stringify(data), this._config.headers)); },
    patch: function (url, data) { return JSON.parse(this._restapi.patch(this._config.baseUrl + url, JSON.stringify(data), this._config.headers)); },
    delete: function (url) { return JSON.parse(this._restapi.delete(this._config.baseUrl + url, this._config.headers)); }
}
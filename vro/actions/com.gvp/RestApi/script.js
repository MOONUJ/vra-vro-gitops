return {
    _pyUrl: System.getModule("com.gvp").execPyUrl,
    get: function(url, headers) {
        if (!headers) { headers = {}; }
        return this._pyUrl("GET", url, null, headers);
    },
    post: function(url, data, headers) {
        if (!headers) { headers = {}; }
        if (!data) { data = {}; }
        if (data === undefined || data == null) { data = {}; }
        return this._pyUrl("POST", url, data, headers);
    },
    put: function(url, data, headers) {
        if (!headers) { headers = {}; }
        if (!data) { data = {}; }
        return this._pyUrl("PUT", url, data, headers);
    },
    patch: function(url, data, headers) {
        if (!headers) { headers = {}; }
        if (!data) { data = {}; }
        return this._pyUrl("PATCH", url, data, headers);
    },
    delete: function(url, headers) {
        if (!headers) { headers = {}; }
        return this._pyUrl("DELETE", url, null, headers);
    }
}
for each(var ca in cloudAccounts) {
    if(ca.password == null || ca.password == undefined || ca.password == ""){
        return false;
    }
}

return true;
if(!tagValue){ return null}
/*
- title: 자동할당
const: variable
- title: 수동할당
const: permanent
*/
if(tagValue == "overlay"){
    var result = "variable"
} else {
    var result = "permanent"
}

return result;
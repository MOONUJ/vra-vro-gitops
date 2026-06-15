var defaultValue =  [
    {
        label: "자동할당",
        value: "variable"
    },
    {
        label: "수동할당",
        value: "permanent"
    }
];
if(!tagValue){ return defaultValue}
/*
- title: 자동할당
const: variable
- title: 수동할당
const: permanent
*/
if(tagValue == "overlay"){
    var result = [
        {
            label: "자동할당",
            value: "variable"
        },
        {
            label: "수동할당",
            value: "permanent"
        }
    ]
} else {
    var result = [
        {
            label: "수동할당",
            value: "permanent"
        }
    ]
}

return result;